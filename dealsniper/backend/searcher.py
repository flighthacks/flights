"""Flight search logic using the fast_flights library."""

import re
import sys
import os
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

# Add parent repo to path so fast_flights is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fast_flights import FlightData, Passengers, get_flights

from db import (
    Deal,
    MonitoredRoute,
    PriceObservation,
    SessionLocal,
    get_setting,
)

logger = logging.getLogger(__name__)

CABIN_MAP = {
    "economy": "economy",
    "premium-economy": "premium-economy",
    "business": "business",
    "first": "first",
}

TRIP_MAP = {
    "return": "round-trip",
    "oneway": "one-way",
}

# Popular destinations for "fly anywhere" scanning
POPULAR_DESTINATIONS = [
    "NRT", "HND", "SIN", "BKK", "HKG", "KUL", "DPS",  # Asia
    "LHR", "CDG", "FCO", "BCN", "AMS", "IST",           # Europe
    "LAX", "JFK", "SFO", "HNL",                          # Americas
    "DXB", "DOH",                                         # Middle East
    "AKL", "FJI",                                         # Oceania
]


def parse_price(price_str: str) -> Optional[float]:
    """Extract numeric price from strings like '$123', 'A$1,234', '€99'."""
    if not price_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", price_str)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def parse_duration_to_mins(duration_str: str) -> Optional[int]:
    """Parse duration like '14 hr 30 min' to minutes."""
    if not duration_str:
        return None
    total = 0
    hr_match = re.search(r"(\d+)\s*hr", duration_str)
    min_match = re.search(r"(\d+)\s*min", duration_str)
    if hr_match:
        total += int(hr_match.group(1)) * 60
    if min_match:
        total += int(min_match.group(1))
    return total if total > 0 else None


def search_flights_for_route(
    origin: str,
    destination: str,
    cabin: str,
    trip_type: str,
    outbound_date: str,
    return_date: Optional[str] = None,
) -> list[dict]:
    """Search flights for a single route and date, return parsed results."""
    seat = CABIN_MAP.get(cabin, "economy")
    trip = TRIP_MAP.get(trip_type, "round-trip")

    flight_data = [
        FlightData(
            date=outbound_date,
            from_airport=origin,
            to_airport=destination,
        )
    ]
    if trip_type == "return" and return_date:
        flight_data.append(
            FlightData(
                date=return_date,
                from_airport=destination,
                to_airport=origin,
            )
        )

    try:
        result = get_flights(
            flight_data=flight_data,
            trip=trip,
            seat=seat,
            passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
        )
    except Exception as e:
        logger.warning(f"Search failed for {origin}->{destination}: {e}")
        return []

    if result is None:
        return []

    observations = []
    for flight in result.flights:
        price = parse_price(flight.price)
        if price is None or price <= 0:
            continue
        observations.append(
            {
                "origin": origin,
                "destination": destination,
                "cabin": cabin,
                "trip_type": trip_type,
                "price": price,
                "airline": flight.name,
                "outbound_date": outbound_date,
                "return_date": return_date,
                "duration_mins": parse_duration_to_mins(flight.duration),
                "stops": flight.stops if isinstance(flight.stops, int) else None,
            }
        )
    return observations


def generate_search_dates(lookahead_days: int) -> list[tuple[str, Optional[str]]]:
    """Generate a sample of (outbound, return) date pairs to search."""
    today = date.today()
    pairs = []
    # Sample weekends across the lookahead window
    for weeks_ahead in range(2, lookahead_days // 7, 2):
        outbound = today + timedelta(weeks=weeks_ahead)
        # Make outbound a Friday
        days_until_friday = (4 - outbound.weekday()) % 7
        outbound = outbound + timedelta(days=days_until_friday)
        return_date = outbound + timedelta(days=9)  # ~9 day trip
        if (outbound - today).days <= lookahead_days:
            pairs.append((outbound.isoformat(), return_date.isoformat()))
    # Ensure at least one pair
    if not pairs:
        outbound = today + timedelta(days=30)
        pairs.append((outbound.isoformat(), (outbound + timedelta(days=7)).isoformat()))
    return pairs


def run_scan(db: Session) -> dict:
    """Run a full scan of all active monitored routes."""
    import json

    origins_str = get_setting(db, "origins")
    origins = json.loads(origins_str) if origins_str else ["PER"]
    threshold = float(get_setting(db, "deal_threshold") or "0.80")
    lookahead = int(get_setting(db, "lookahead_days") or "90")
    min_obs = int(get_setting(db, "min_observations_before_alert") or "10")

    routes = db.query(MonitoredRoute).filter(MonitoredRoute.active == True).all()

    # If no explicit routes, scan origins -> popular destinations
    search_pairs = []
    if routes:
        for route in routes:
            search_pairs.append(
                (route.origin, route.destination, route.cabin, route.trip_type)
            )
    else:
        for origin in origins:
            for dest in POPULAR_DESTINATIONS:
                if dest != origin:
                    search_pairs.append((origin, dest, "economy", "return"))

    date_pairs = generate_search_dates(lookahead)
    # Limit date pairs per scan to keep it manageable
    date_pairs = date_pairs[:3]

    total_observations = 0
    total_deals = 0
    routes_scanned = 0

    for origin, destination, cabin, trip_type in search_pairs:
        routes_scanned += 1
        for outbound, return_dt in date_pairs:
            ret = return_dt if trip_type == "return" else None
            observations = search_flights_for_route(
                origin, destination, cabin, trip_type, outbound, ret
            )
            for obs in observations:
                db.add(PriceObservation(**obs))
                total_observations += 1

                # Check for deal
                avg = _get_avg_price(db, origin, destination, cabin, trip_type)
                obs_count = _get_observation_count(
                    db, origin, destination, cabin, trip_type
                )
                if avg and obs_count >= min_obs and obs["price"] <= avg * threshold:
                    discount_pct = round((1 - obs["price"] / avg) * 100, 1)
                    booking_url = _build_booking_url(
                        origin, destination, outbound, ret, cabin
                    )
                    deal = Deal(
                        origin=origin,
                        destination=destination,
                        cabin=cabin,
                        trip_type=trip_type,
                        price=obs["price"],
                        avg_price=round(avg, 2),
                        discount_pct=discount_pct,
                        airline=obs["airline"],
                        outbound_date=outbound,
                        return_date=ret,
                        booking_url=booking_url,
                    )
                    db.add(deal)
                    total_deals += 1

        db.commit()

    return {
        "routes_scanned": routes_scanned,
        "observations_added": total_observations,
        "deals_found": total_deals,
    }


def _get_avg_price(
    db: Session, origin: str, destination: str, cabin: str, trip_type: str
) -> Optional[float]:
    """Get 30-day average price for a route."""
    from sqlalchemy import func

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = (
        db.query(func.avg(PriceObservation.price))
        .filter(
            PriceObservation.origin == origin,
            PriceObservation.destination == destination,
            PriceObservation.cabin == cabin,
            PriceObservation.trip_type == trip_type,
            PriceObservation.checked_at >= cutoff,
        )
        .scalar()
    )
    return result


def _get_observation_count(
    db: Session, origin: str, destination: str, cabin: str, trip_type: str
) -> int:
    """Count observations for a route in the last 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    return (
        db.query(PriceObservation)
        .filter(
            PriceObservation.origin == origin,
            PriceObservation.destination == destination,
            PriceObservation.cabin == cabin,
            PriceObservation.trip_type == trip_type,
            PriceObservation.checked_at >= cutoff,
        )
        .count()
    )


def _build_booking_url(
    origin: str,
    destination: str,
    outbound: str,
    return_date: Optional[str],
    cabin: str,
) -> str:
    """Build a Google Flights URL for the route."""
    try:
        flight_data = [
            FlightData(date=outbound, from_airport=origin, to_airport=destination)
        ]
        if return_date:
            flight_data.append(
                FlightData(
                    date=return_date, from_airport=destination, to_airport=origin
                )
            )
        from fast_flights import create_filter

        trip = "round-trip" if return_date else "one-way"
        f = create_filter(
            flight_data=flight_data,
            trip=trip,
            seat=CABIN_MAP.get(cabin, "economy"),
            passengers=Passengers(adults=1, children=0, infants_in_seat=0, infants_on_lap=0),
        )
        b64 = f.as_b64().decode("utf-8")
        return f"https://www.google.com/travel/flights?tfs={b64}"
    except Exception:
        return f"https://www.google.com/travel/flights"
