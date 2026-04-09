"""
Autofare SaaS Backend — FastAPI application.

Wraps the autofare search engine with user auth, search job management,
real-time progress streaming, and Stripe subscription billing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .database import Database, get_db
from .auth import (
    get_current_user,
    create_access_token,
    hash_password,
    verify_password,
    AuthUser,
)
from .search_worker import SearchWorker, search_jobs
from .stripe_billing import StripeBilling

logger = logging.getLogger("autofare.web")

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database()
    await db.initialize()
    app.state.db = db
    app.state.stripe = StripeBilling()
    yield
    await db.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Autofare",
    description="Autonomous flight search optimizer — find the cheapest business class flights",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language search query")
    config_yaml: Optional[str] = Field(None, description="Optional YAML config override")
    # Quick overrides
    cabin: Optional[str] = None
    flex_days: Optional[int] = None
    max_searches: Optional[int] = None
    currency: str = "USD"


class SearchJobResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    query: str


class SearchResultResponse(BaseModel):
    job_id: str
    status: str
    query: str
    created_at: str
    completed_at: Optional[str] = None
    baseline_price: Optional[float] = None
    best_price: Optional[float] = None
    savings: Optional[float] = None
    savings_pct: Optional[float] = None
    best_route: Optional[str] = None
    best_airline: Optional[str] = None
    total_searches: int = 0
    top_results: List[Dict[str, Any]] = []
    progress: Optional[Dict[str, Any]] = None


class PriceAlertRequest(BaseModel):
    query: str
    target_price: float
    cabin: str = "business"
    currency: str = "USD"


class SubscriptionTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


TIER_LIMITS = {
    SubscriptionTier.FREE: {"searches_per_month": 2, "max_results": 5, "alerts": 0},
    SubscriptionTier.PRO: {"searches_per_month": 999, "max_results": 50, "alerts": 10},
    SubscriptionTier.BUSINESS: {"searches_per_month": 999, "max_results": 999, "alerts": 50},
}


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: Database = Depends(get_db)):
    existing = await db.get_user_by_email(req.email)
    if existing:
        raise HTTPException(400, "Email already registered")

    user = await db.create_user(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
    )
    token = create_access_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"]},
    )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Database = Depends(get_db)):
    user = await db.get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "name": user["name"]},
    )


@app.get("/api/auth/me")
async def get_me(user: AuthUser = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "tier": user.tier,
    }


# ---------------------------------------------------------------------------
# Search endpoints
# ---------------------------------------------------------------------------

@app.post("/api/search", response_model=SearchJobResponse)
async def create_search(
    req: SearchRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    # Check tier limits
    limits = TIER_LIMITS[SubscriptionTier(user.tier)]
    month_count = await db.count_user_searches_this_month(user.id)
    if month_count >= limits["searches_per_month"]:
        raise HTTPException(
            403,
            f"Monthly search limit reached ({limits['searches_per_month']}). "
            f"Upgrade to Pro for unlimited searches.",
        )

    # Create job
    job_id = str(uuid.uuid4())
    await db.create_search_job(
        job_id=job_id,
        user_id=user.id,
        query=req.query,
        config_yaml=req.config_yaml,
        cabin=req.cabin,
        flex_days=req.flex_days,
        max_searches=req.max_searches,
        currency=req.currency,
    )

    # Launch background search
    worker = SearchWorker(job_id=job_id, db=db)
    background_tasks.add_task(
        worker.run,
        query=req.query,
        config_yaml=req.config_yaml,
        cabin=req.cabin,
        flex_days=req.flex_days,
        max_searches=req.max_searches,
        currency=req.currency,
    )

    return SearchJobResponse(
        job_id=job_id,
        status="running",
        created_at=datetime.utcnow().isoformat(),
        query=req.query,
    )


@app.get("/api/search/{job_id}", response_model=SearchResultResponse)
async def get_search_result(
    job_id: str,
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    job = await db.get_search_job(job_id, user.id)
    if not job:
        raise HTTPException(404, "Search not found")

    # Apply tier result limits
    limits = TIER_LIMITS[SubscriptionTier(user.tier)]
    top_results = job.get("top_results", [])[:limits["max_results"]]

    return SearchResultResponse(
        job_id=job["job_id"],
        status=job["status"],
        query=job["query"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        baseline_price=job.get("baseline_price"),
        best_price=job.get("best_price"),
        savings=job.get("savings"),
        savings_pct=job.get("savings_pct"),
        best_route=job.get("best_route"),
        best_airline=job.get("best_airline"),
        total_searches=job.get("total_searches", 0),
        top_results=top_results,
        progress=search_jobs.get(job_id, {}).get("progress"),
    )


@app.get("/api/search/{job_id}/stream")
async def stream_search_progress(
    job_id: str,
    user: AuthUser = Depends(get_current_user),
):
    """Server-Sent Events endpoint for real-time search progress."""

    async def event_stream():
        last_update = 0
        while True:
            job_state = search_jobs.get(job_id)
            if not job_state:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                return

            progress = job_state.get("progress", {})
            update_id = progress.get("update_id", 0)

            if update_id > last_update:
                last_update = update_id
                yield f"data: {json.dumps(progress)}\n\n"

            if job_state.get("status") in ("completed", "failed"):
                yield f"data: {json.dumps({'status': job_state['status'], 'final': True})}\n\n"
                return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/searches", response_model=List[SearchJobResponse])
async def list_searches(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    jobs = await db.list_user_searches(user.id, limit=limit, offset=offset)
    return [
        SearchJobResponse(
            job_id=j["job_id"],
            status=j["status"],
            created_at=j["created_at"],
            query=j["query"],
        )
        for j in jobs
    ]


# ---------------------------------------------------------------------------
# Price alerts
# ---------------------------------------------------------------------------

@app.post("/api/alerts")
async def create_alert(
    req: PriceAlertRequest,
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    limits = TIER_LIMITS[SubscriptionTier(user.tier)]
    if limits["alerts"] == 0:
        raise HTTPException(403, "Price alerts require a Pro or Business subscription")

    alert_count = await db.count_user_alerts(user.id)
    if alert_count >= limits["alerts"]:
        raise HTTPException(403, f"Alert limit reached ({limits['alerts']})")

    alert = await db.create_alert(
        user_id=user.id,
        query=req.query,
        target_price=req.target_price,
        cabin=req.cabin,
        currency=req.currency,
    )
    return alert


@app.get("/api/alerts")
async def list_alerts(
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    return await db.list_user_alerts(user.id)


@app.delete("/api/alerts/{alert_id}")
async def delete_alert(
    alert_id: str,
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    await db.delete_alert(alert_id, user.id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

@app.post("/api/billing/checkout")
async def create_checkout(
    tier: SubscriptionTier = Query(...),
    user: AuthUser = Depends(get_current_user),
):
    stripe = app.state.stripe
    session = stripe.create_checkout_session(
        user_id=user.id,
        user_email=user.email,
        tier=tier.value,
    )
    return {"checkout_url": session.url}


@app.post("/api/billing/webhook")
async def stripe_webhook(
    request: Any,
    db: Database = Depends(get_db),
):
    """Handle Stripe webhook events (subscription created/updated/cancelled)."""
    stripe = app.state.stripe
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    event = stripe.verify_webhook(body, sig)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"]["user_id"]
        tier = session["metadata"]["tier"]
        await db.update_user_tier(user_id, tier)

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        user_id = sub["metadata"].get("user_id")
        if user_id:
            await db.update_user_tier(user_id, "free")

    return {"ok": True}


@app.get("/api/billing/status")
async def billing_status(
    user: AuthUser = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    limits = TIER_LIMITS[SubscriptionTier(user.tier)]
    month_count = await db.count_user_searches_this_month(user.id)
    return {
        "tier": user.tier,
        "searches_used": month_count,
        "searches_limit": limits["searches_per_month"],
        "alerts_limit": limits["alerts"],
        "max_results": limits["max_results"],
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
