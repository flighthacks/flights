"""
Flight search wrapper around the fast_flights library.

Provides a clean interface for running one-way, round-trip, and multi-city
searches, extracting structured results with prices, and handling errors/retries.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

# fast_flights lives one level up in the repo
from fast_flights import (
    FlightData,
    Passengers,
    Result,
    Flight,
    get_flights,
)

from .config import AutofareConfig, RouteConfig, PassengerConfig

logger = logging.getLogger("autofare.search")


# ---------------------------------------------------------------------------
# Structured search result types
# ---------------------------------------------------------------------------

@dataclass
class FlightOption:
    """A single priced flight option returned from a search."""
    airline: str
    departure_time: str
    arrival_time: str
    arrival_time_ahead: str  # e.g., "+1" for next day
    duration: str
    stops: int
    price_raw: str  # e.g., "$2,424"
    price_usd: Optional[float] = None  # parsed numeric price
    is_best: bool = False

    @staticmethod
    def parse_price(price_str: str) -> Optional[float]:
        """Extract numeric price from strings like '$2424', '₹1,23,456', '2424'."""
        if not price_str or price_str == "0":
            return None
        cleaned = re.sub(r'[^\d.]', '', price_str)
        try:
            return float(cleaned)
        except ValueError:
            return None

    @classmethod
    def from_flight(cls, flight: Flight) -> "FlightOption":
        price_usd = cls.parse_price(flight.price)
        return cls(
            airline=flight.name,
            departure_time=flight.departure,
            arrival_time=flight.arrival,
            arrival_time_ahead=flight.arrival_time_ahead,
            duration=flight.duration,
            stops=flight.stops if isinstance(flight.stops, int) else -1,
            price_raw=flight.price,
            price_usd=price_usd,
            is_best=flight.is_best,
        )


@dataclass
class SearchResult:
    """Result of a single flight search query."""
    origin: str
    destination: str
    date: str
    cabin: str
    current_price_level: str  # "low", "typical", "high"
    options: List[FlightOption]
    cheapest: Optional[FlightOption] = None
    search_time_seconds: float = 0.0
    error: Optional[str] = None

    @property
    def cheapest_price(self) -> Optional[float]:
        if self.cheapest and self.cheapest.price_usd:
            return self.cheapest.price_usd
        return None


@dataclass
class SearchQuery:
    """Describes a single search to execute."""
    origin: str
    destination: str
    date: str
    cabin: Literal["economy", "premium-economy", "business", "first"] = "business"
    trip_type: Literal["one-way", "round-trip"] = "one-way"
    return_date: Optional[str] = None
    max_stops: Optional[int] = None
    label: str = ""  # human-readable label for logging

    def __str__(self) -> str:
        label_part = f" [{self.label}]" if self.label else ""
        ret = f" ret:{self.return_date}" if self.return_date else ""
        return f"{self.origin}→{self.destination} {self.date}{ret} {self.cabin}{label_part}"


# ---------------------------------------------------------------------------
# Search execution
# ---------------------------------------------------------------------------

class FlightSearchEngine:
    """Wraps fast_flights to execute searches with retries and rate limiting."""

    def __init__(
        self,
        config: AutofareConfig,
        rate_limit_delay: float = 1.0,
        max_retries: int = 2,
    ):
        self.config = config
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.total_searches = 0
        self.search_log: List[SearchResult] = []

    def _build_passengers(self) -> Passengers:
        pax = self.config.passengers
        return Passengers(
            adults=pax.adults,
            children=pax.children,
            infants_in_seat=pax.infants_in_seat,
            infants_on_lap=pax.infants_on_lap,
        )

    def search(self, query: SearchQuery) -> SearchResult:
        """Execute a single flight search query."""
        logger.info(f"Search #{self.total_searches + 1}: {query}")
        start_time = time.time()

        flight_data_list = [
            FlightData(
                date=query.date,
                from_airport=query.origin,
                to_airport=query.destination,
            )
        ]

        trip = query.trip_type
        if query.trip_type == "round-trip" and query.return_date:
            flight_data_list.append(
                FlightData(
                    date=query.return_date,
                    from_airport=query.destination,
                    to_airport=query.origin,
                )
            )

        result = self._execute_with_retry(
            flight_data=flight_data_list,
            trip=trip,
            seat=query.cabin,
            max_stops=query.max_stops,
        )

        elapsed = time.time() - start_time
        self.total_searches += 1

        if result is None:
            sr = SearchResult(
                origin=query.origin,
                destination=query.destination,
                date=query.date,
                cabin=query.cabin,
                current_price_level="",
                options=[],
                search_time_seconds=elapsed,
                error="No results returned",
            )
            self.search_log.append(sr)
            return sr

        options = [FlightOption.from_flight(f) for f in result.flights]

        # Find cheapest by parsed price
        priced = [o for o in options if o.price_usd is not None]
        cheapest = min(priced, key=lambda o: o.price_usd) if priced else None  # type: ignore[arg-type]

        sr = SearchResult(
            origin=query.origin,
            destination=query.destination,
            date=query.date,
            cabin=query.cabin,
            current_price_level=result.current_price or "",
            options=options,
            cheapest=cheapest,
            search_time_seconds=elapsed,
        )
        self.search_log.append(sr)

        if cheapest:
            logger.info(
                f"  → {len(options)} options, cheapest: ${cheapest.price_usd:.0f} "
                f"({cheapest.airline}, {cheapest.stops} stops, {cheapest.duration})"
            )
        else:
            logger.info(f"  → {len(options)} options, no valid prices parsed")

        return sr

    def _execute_with_retry(
        self,
        flight_data: List[FlightData],
        trip: str,
        seat: str,
        max_stops: Optional[int],
    ) -> Optional[Result]:
        """Execute a search with retry logic for transient failures."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    backoff = self.rate_limit_delay * (2 ** (attempt - 1))
                    logger.debug(f"  Retry {attempt}, waiting {backoff:.1f}s...")
                    time.sleep(backoff)

                result = get_flights(
                    flight_data=flight_data,
                    trip=trip,  # type: ignore[arg-type]
                    seat=seat,  # type: ignore[arg-type]
                    max_stops=max_stops,
                    fetch_mode=self.config.fetch_mode,  # type: ignore[arg-type]
                )
                # Rate limit between searches
                time.sleep(self.rate_limit_delay)
                return result  # type: ignore[return-value]

            except Exception as e:
                last_error = e
                logger.warning(f"  Search attempt {attempt + 1} failed: {e}")

        logger.error(f"  All {self.max_retries + 1} attempts failed: {last_error}")
        return None

    def search_batch(self, queries: List[SearchQuery]) -> List[SearchResult]:
        """Execute multiple searches sequentially."""
        results = []
        for query in queries:
            if self.total_searches >= self.config.loop.max_searches:
                logger.warning("Search budget exhausted!")
                break
            results.append(self.search(query))
        return results

    def build_baseline_queries(self) -> List[SearchQuery]:
        """Build the initial baseline search queries from the config."""
        queries = []
        route = self.config.route
        cabin = self.config.constraints.cabin

        for origin in route.origins:
            for dest in route.destinations:
                if route.trip_type == "one-way":
                    for dep_date in route.departure_date.all_dates():
                        queries.append(SearchQuery(
                            origin=origin,
                            destination=dest,
                            date=dep_date,
                            cabin=cabin,
                            trip_type="one-way",
                            max_stops=self.config.constraints.max_stops,
                            label=f"baseline {origin}→{dest} {dep_date}",
                        ))
                elif route.trip_type == "round-trip" and route.return_date:
                    # For round-trip baseline, just use target dates (not all flex combos)
                    queries.append(SearchQuery(
                        origin=origin,
                        destination=dest,
                        date=route.departure_date.target,
                        cabin=cabin,
                        trip_type="round-trip",
                        return_date=route.return_date.target,
                        max_stops=self.config.constraints.max_stops,
                        label=f"baseline RT {origin}→{dest}",
                    ))
                else:
                    # Default: one-way on target date
                    queries.append(SearchQuery(
                        origin=origin,
                        destination=dest,
                        date=route.departure_date.target,
                        cabin=cabin,
                        trip_type="one-way",
                        max_stops=self.config.constraints.max_stops,
                        label=f"baseline {origin}→{dest}",
                    ))

        return queries
