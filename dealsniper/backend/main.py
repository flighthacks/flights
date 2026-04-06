"""Deal Sniper – FastAPI backend."""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import (
    Deal,
    MonitoredRoute,
    PriceObservation,
    Setting,
    get_db,
    get_setting,
    init_db,
    set_setting,
)
from models import (
    DealOut,
    MonitoredRouteCreate,
    MonitoredRouteOut,
    PriceObservationOut,
    ScanResult,
    SettingsOut,
    SettingsUpdate,
    StatsOut,
)
from scheduler import reschedule, start_scheduler, stop_scheduler
from searcher import run_scan

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Deal Sniper", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Stats ────────────────────────────────────────────────────────────────────


@app.get("/api/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    total_obs = db.query(PriceObservation).count()
    total_deals = db.query(Deal).filter(Deal.is_dismissed == False).count()
    active_routes = db.query(MonitoredRoute).filter(MonitoredRoute.active == True).count()
    avg_discount = (
        db.query(func.avg(Deal.discount_pct))
        .filter(Deal.is_dismissed == False)
        .scalar()
    )
    return StatsOut(
        total_observations=total_obs,
        total_deals=total_deals,
        active_routes=active_routes,
        avg_discount=round(avg_discount, 1) if avg_discount else None,
    )


# ── Deals ────────────────────────────────────────────────────────────────────


@app.get("/api/deals", response_model=list[DealOut])
def list_deals(
    include_dismissed: bool = False,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Deal)
    if not include_dismissed:
        q = q.filter(Deal.is_dismissed == False)
    return q.order_by(Deal.found_at.desc()).limit(limit).all()


@app.post("/api/deals/{deal_id}/dismiss")
def dismiss_deal(deal_id: int, db: Session = Depends(get_db)):
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    deal.is_dismissed = True
    db.commit()
    return {"status": "dismissed"}


# ── Monitored Routes ─────────────────────────────────────────────────────────


@app.get("/api/routes", response_model=list[MonitoredRouteOut])
def list_routes(db: Session = Depends(get_db)):
    return db.query(MonitoredRoute).order_by(MonitoredRoute.created_at.desc()).all()


@app.post("/api/routes", response_model=MonitoredRouteOut)
def create_route(route: MonitoredRouteCreate, db: Session = Depends(get_db)):
    db_route = MonitoredRoute(
        origin=route.origin.upper(),
        destination=route.destination.upper(),
        cabin=route.cabin,
        trip_type=route.trip_type,
    )
    db.add(db_route)
    db.commit()
    db.refresh(db_route)
    return db_route


@app.delete("/api/routes/{route_id}")
def delete_route(route_id: int, db: Session = Depends(get_db)):
    route = db.query(MonitoredRoute).filter(MonitoredRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    db.delete(route)
    db.commit()
    return {"status": "deleted"}


@app.patch("/api/routes/{route_id}/toggle")
def toggle_route(route_id: int, db: Session = Depends(get_db)):
    route = db.query(MonitoredRoute).filter(MonitoredRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    route.active = not route.active
    db.commit()
    return {"status": "toggled", "active": route.active}


# ── Price History ────────────────────────────────────────────────────────────


@app.get("/api/prices", response_model=list[PriceObservationOut])
def list_prices(
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    cabin: Optional[str] = None,
    days: int = Query(default=30, le=365),
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(PriceObservation).filter(PriceObservation.checked_at >= cutoff)
    if origin:
        q = q.filter(PriceObservation.origin == origin.upper())
    if destination:
        q = q.filter(PriceObservation.destination == destination.upper())
    if cabin:
        q = q.filter(PriceObservation.cabin == cabin)
    return q.order_by(PriceObservation.checked_at.desc()).limit(limit).all()


@app.get("/api/prices/chart")
def price_chart(
    origin: str,
    destination: str,
    cabin: str = "economy",
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db),
):
    """Return aggregated daily avg prices for charting."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            func.date(PriceObservation.checked_at).label("date"),
            func.avg(PriceObservation.price).label("avg_price"),
            func.min(PriceObservation.price).label("min_price"),
            func.max(PriceObservation.price).label("max_price"),
            func.count(PriceObservation.id).label("count"),
        )
        .filter(
            PriceObservation.origin == origin.upper(),
            PriceObservation.destination == destination.upper(),
            PriceObservation.cabin == cabin,
            PriceObservation.checked_at >= cutoff,
        )
        .group_by(func.date(PriceObservation.checked_at))
        .order_by(func.date(PriceObservation.checked_at))
        .all()
    )
    return [
        {
            "date": str(row.date),
            "avg_price": round(row.avg_price, 2),
            "min_price": round(row.min_price, 2),
            "max_price": round(row.max_price, 2),
            "count": row.count,
        }
        for row in rows
    ]


# ── Settings ─────────────────────────────────────────────────────────────────


@app.get("/api/settings", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    origins = json.loads(get_setting(db, "origins") or '["PER"]')
    return SettingsOut(
        origins=origins,
        deal_threshold=float(get_setting(db, "deal_threshold") or "0.80"),
        scan_interval_hours=int(get_setting(db, "scan_interval_hours") or "6"),
        lookahead_days=int(get_setting(db, "lookahead_days") or "90"),
        min_observations_before_alert=int(
            get_setting(db, "min_observations_before_alert") or "10"
        ),
    )


@app.put("/api/settings", response_model=SettingsOut)
def update_settings(updates: SettingsUpdate, db: Session = Depends(get_db)):
    if updates.origins is not None:
        set_setting(db, "origins", json.dumps(updates.origins))
    if updates.deal_threshold is not None:
        set_setting(db, "deal_threshold", str(updates.deal_threshold))
    if updates.scan_interval_hours is not None:
        set_setting(db, "scan_interval_hours", str(updates.scan_interval_hours))
        reschedule(updates.scan_interval_hours)
    if updates.lookahead_days is not None:
        set_setting(db, "lookahead_days", str(updates.lookahead_days))
    if updates.min_observations_before_alert is not None:
        set_setting(
            db, "min_observations_before_alert",
            str(updates.min_observations_before_alert),
        )
    return get_settings(db)


# ── Manual Scan ──────────────────────────────────────────────────────────────


@app.post("/api/scan", response_model=ScanResult)
def trigger_scan(db: Session = Depends(get_db)):
    """Trigger an immediate scan."""
    result = run_scan(db)
    return ScanResult(**result)


# ── Health ───────────────────────────────────────────────────────────────────


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Deal Sniper"}
