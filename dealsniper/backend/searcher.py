"""Flight search logic using the fli library (pip install flights)."""

import json
import logging
import time
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from fli.models import Airport, SeatType, SortBy, PassengerInfo
from fli.models.google_flights.base import FlightSegment
from fli.models.google_flights.dates import DateSearchFilters
from fli.models.google_flights.flights import FlightSearchFilters
from fli.search import SearchDates, SearchFlights

from db import Deal, MonitoredRoute, PriceObservation, SessionLocal, get_setting

logger = logging.getLogger(__name__)

# ── Airport IATA → enum mapping ─────────────────────────────────────────────
AIRPORT_MAP: dict[str, Airport] = {a.name: a for a in Airport}

# ── Cabin string → SeatType enum ────────────────────────────────────────────
SEAT_MAP = {
    "economy": SeatType.ECONOMY,
    "premium_economy": SeatType.PREMIUM_ECONOMY,
    "business": SeatType.BUSINESS,
    "first": SeatType.FIRST,
}

# ── Destinations for "ANYWHERE" scans ───────────────────────────────────────
DESTINATIONS = [
    "LHR", "CDG", "AMS", "FRA", "FCO", "BCN", "MAD", "LIS", "ATH", "PRG",
    "VIE", "ZRH", "GVA", "MUC", "BRU", "ARN", "CPH", "HEL", "DUB", "WAW",
    "BUD", "MXP", "IST", "SIN", "BKK", "HKG", "NRT", "ICN", "KUL", "MNL",
    "CGK", "DEL", "BOM", "DXB", "DOH", "AUH", "JNB", "NBO", "CMN",
    "JFK", "LAX", "SFO", "MIA", "ORD", "DFW", "YVR", "YYZ",
    "MEX", "GRU", "SCL", "BOG", "LIM",
    "AKL", "CHC", "NAN", "PPT", "SYD", "MEL", "BNE", "PER",
]

# ── Scan progress state (shared with API) ───────────────────────────────────
_scan_lock = threading.Lock()
_scan_status = {
    "running": False,
    "progress": 0.0,
    "current_route": "",
    "routes_scanned": 0,
    "total_routes": 0,
    "observations_added": 0,
    "deals_found": 0,
}


def get_scan_status() -> dict:
    with _scan_lock:
        return dict(_scan_status)


def _update_status(**kwargs):
    with _scan_lock:
        _scan_status.update(kwargs)


# ── Airport coordinates for map (lat, lng) ──────────────────────────────────
AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    "PER": (-31.94, 115.97), "SYD": (-33.95, 151.18), "MEL": (-37.67, 144.84),
    "BNE": (-27.38, 153.12), "LHR": (51.47, -0.46), "CDG": (49.01, 2.55),
    "AMS": (52.31, 4.76), "FRA": (50.03, 8.57), "FCO": (41.80, 12.25),
    "BCN": (41.30, 2.08), "MAD": (40.47, -3.57), "LIS": (38.77, -9.13),
    "ATH": (37.94, 23.94), "PRG": (50.10, 14.26), "VIE": (48.11, 16.57),
    "ZRH": (47.46, 8.55), "GVA": (46.24, 6.11), "MUC": (48.35, 11.79),
    "BRU": (50.90, 4.48), "ARN": (59.65, 17.94), "CPH": (55.62, 12.66),
    "HEL": (60.32, 24.96), "DUB": (53.43, -6.27), "WAW": (52.17, 20.97),
    "BUD": (47.43, 19.26), "MXP": (45.63, 8.72), "IST": (41.26, 28.74),
    "SIN": (1.35, 103.99), "BKK": (13.69, 100.75), "HKG": (22.31, 113.91),
    "NRT": (35.77, 140.39), "ICN": (37.46, 126.44), "KUL": (2.74, 101.70),
    "MNL": (14.51, 121.02), "CGK": (-6.13, 106.66), "DEL": (28.56, 77.10),
    "BOM": (19.09, 72.87), "DXB": (25.25, 55.36), "DOH": (25.26, 51.57),
    "AUH": (24.43, 54.65), "JNB": (-26.14, 28.25), "NBO": (-1.32, 36.93),
    "CMN": (33.37, -7.59), "JFK": (40.64, -73.78), "LAX": (33.94, -118.41),
    "SFO": (37.62, -122.38), "MIA": (25.79, -80.29), "ORD": (41.97, -87.91),
    "DFW": (32.90, -97.04), "YVR": (49.19, -123.18), "YYZ": (43.68, -79.63),
    "MEX": (19.44, -99.07), "GRU": (-23.43, -46.47), "SCL": (-33.39, -70.79),
    "BOG": (4.70, -74.15), "LIM": (-12.02, -77.11), "AKL": (-37.01, 174.79),
    "CHC": (-43.49, 172.53), "NAN": (-17.76, 177.44), "PPT": (-17.56, -149.61),
    "HND": (35.55, 139.78),
}


def _resolve_airport(iata: str) -> Optional[Airport]:
    ap = AIRPORT_MAP.get(iata.upper())
    if ap is None:
        logger.warning(f"Airport {iata} not found in fli enum, skipping")
    return ap


def search_dates_for_route(
    origin_iata: str,
    dest_iata: str,
    lookahead_days: int,
    cabin: str = "economy",
) -> list[dict]:
    """Use SearchDates to find cheapest dates for a route."""
    origin = _resolve_airport(origin_iata)
    dest = _resolve_airport(dest_iata)
    if not origin or not dest:
        return []

    from_date = date.today().isoformat()
    to_date = (date.today() + timedelta(days=lookahead_days)).isoformat()

    filters = DateSearchFilters(
        passenger_info=PassengerInfo(adults=1),
        flight_segments=[
            FlightSegment(
                departure_airport=[[origin, 0]],
                arrival_airport=[[dest, 0]],
                travel_date=from_date,
            )
        ],
        seat_type=SEAT_MAP.get(cabin, SeatType.ECONOMY),
        from_date=from_date,
        to_date=to_date,
    )

    try:
        results = SearchDates().search(filters)
        time.sleep(2)
    except Exception as e:
        logger.warning(f"SearchDates failed {origin_iata}->{dest_iata}: {e}")
        return []

    if not results:
        logger.info(f"  No results for {origin_iata}->{dest_iata}")
        return []

    observations = []
    for dp in results[:3]:  # top 3 cheapest dates
        logger.info(f"  {origin_iata}->{dest_iata}: ${dp.price} on {dp.date}")
        observations.append({
            "origin": origin_iata.upper(),
            "destination": dest_iata.upper(),
            "cabin": cabin,
            "trip_type": "oneway",
            "price": dp.price,
            "airline": None,
            "outbound_date": dp.date,
            "return_date": None,
            "duration_mins": None,
            "stops": None,
        })
    return observations


def search_flights_for_route(
    origin_iata: str,
    dest_iata: str,
    travel_date: str,
    cabin: str = "economy",
) -> list[dict]:
    """Use SearchFlights for specific flights on a date."""
    origin = _resolve_airport(origin_iata)
    dest = _resolve_airport(dest_iata)
    if not origin or not dest:
        return []

    filters = FlightSearchFilters(
        passenger_info=PassengerInfo(adults=1),
        flight_segments=[
            FlightSegment(
                departure_airport=[[origin, 0]],
                arrival_airport=[[dest, 0]],
                travel_date=travel_date,
            )
        ],
        seat_type=SEAT_MAP.get(cabin, SeatType.ECONOMY),
        sort_by=SortBy.CHEAPEST,
    )

    try:
        results = SearchFlights().search(filters)
        time.sleep(2)
    except Exception as e:
        logger.warning(f"SearchFlights failed {origin_iata}->{dest_iata} on {travel_date}: {e}")
        return []

    if not results:
        return []

    observations = []
    for fr in results[:5]:
        airline = "Unknown"
        if fr.legs:
            try:
                airline = fr.legs[0].airline.value
            except Exception:
                pass
        observations.append({
            "origin": origin_iata.upper(),
            "destination": dest_iata.upper(),
            "cabin": cabin,
            "trip_type": "oneway",
            "price": fr.price,
            "airline": airline,
            "outbound_date": travel_date,
            "return_date": None,
            "duration_mins": fr.duration,
            "stops": fr.stops,
        })
    return observations


def check_for_deal(
    db: Session,
    origin: str,
    dest: str,
    cabin: str,
    trip_type: str,
    price: float,
    threshold: float,
    min_obs: int,
    airline: Optional[str],
    outbound_date: Optional[str],
    return_date: Optional[str],
) -> Optional[Deal]:
    """Check if a price qualifies as a deal based on 30-day average."""
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    obs_count = (
        db.query(func.count(PriceObservation.id))
        .filter(
            PriceObservation.origin == origin,
            PriceObservation.destination == dest,
            PriceObservation.cabin == cabin,
            PriceObservation.trip_type == trip_type,
            PriceObservation.checked_at >= thirty_days_ago,
        )
        .scalar()
    )

    if obs_count < min_obs:
        return None

    avg_price = (
        db.query(func.avg(PriceObservation.price))
        .filter(
            PriceObservation.origin == origin,
            PriceObservation.destination == dest,
            PriceObservation.cabin == cabin,
            PriceObservation.trip_type == trip_type,
            PriceObservation.checked_at >= thirty_days_ago,
        )
        .scalar()
    )

    if avg_price is None or avg_price <= 0:
        return None

    if price <= avg_price * threshold:
        discount_pct = round((1 - price / avg_price) * 100, 1)
        return Deal(
            origin=origin,
            destination=dest,
            cabin=cabin,
            trip_type=trip_type,
            price=price,
            avg_price=round(avg_price, 2),
            discount_pct=discount_pct,
            airline=airline,
            outbound_date=outbound_date,
            return_date=return_date,
            booking_url=f"https://www.google.com/travel/flights?q=flights+from+{origin}+to+{dest}",
        )
    return None


def run_scan(db: Session) -> dict:
    """Execute a full scan of all active monitored routes."""
    origins = json.loads(get_setting(db, "origins") or '["PER"]')
    threshold = float(get_setting(db, "deal_threshold") or "0.80")
    lookahead = int(get_setting(db, "lookahead_days") or "90")
    min_obs = int(get_setting(db, "min_observations") or "10")

    routes = db.query(MonitoredRoute).filter(MonitoredRoute.active == True).all()

    # Build search pairs: (origin, destination, cabin, trip_type)
    search_pairs = []
    for route in routes:
        if route.destination == "ANYWHERE":
            for dest in DESTINATIONS:
                if dest != route.origin:
                    search_pairs.append((route.origin, dest, route.cabin, route.trip_type))
        else:
            search_pairs.append((route.origin, route.destination, route.cabin, route.trip_type))

    # If no routes, scan origins → popular destinations in economy
    if not search_pairs:
        for origin in origins:
            for dest in DESTINATIONS:
                if dest != origin:
                    search_pairs.append((origin, dest, "economy", "oneway"))

    total = len(search_pairs)
    _update_status(
        running=True, progress=0.0, current_route="", routes_scanned=0,
        total_routes=total, observations_added=0, deals_found=0,
    )

    total_obs = 0
    total_deals = 0
    errors = 0

    for i, (origin, dest, cabin, trip_type) in enumerate(search_pairs):
        route_label = f"{origin} → {dest} ({cabin})"
        logger.info(f"[{i+1}/{total}] Scanning {route_label}...")
        _update_status(
            current_route=route_label,
            routes_scanned=i,
            progress=round(i / max(total, 1) * 100, 1),
        )

        try:
            observations = search_dates_for_route(origin, dest, lookahead, cabin)

            for obs in observations:
                db.add(PriceObservation(**obs))
                total_obs += 1

                deal = check_for_deal(
                    db, origin, dest, cabin, trip_type,
                    obs["price"], threshold, min_obs,
                    obs.get("airline"), obs.get("outbound_date"), obs.get("return_date"),
                )
                if deal:
                    db.add(deal)
                    total_deals += 1

            db.commit()
        except Exception as e:
            logger.error(f"Error scanning {route_label}: {e}", exc_info=True)
            errors += 1
            db.rollback()

    _update_status(
        running=False, progress=100.0, routes_scanned=total,
        current_route="", observations_added=total_obs, deals_found=total_deals,
    )

    return {
        "routes_scanned": total,
        "observations_added": total_obs,
        "deals_found": total_deals,
        "errors": errors,
    }
