"""
Configuration system for Autofare.

Parses natural-language queries into structured YAML configs, and loads/validates
YAML config files with full search parameters, constraints, and strategy settings.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional

import yaml


# ---------------------------------------------------------------------------
# Data classes representing the full Autofare configuration
# ---------------------------------------------------------------------------

@dataclass
class PassengerConfig:
    adults: int = 1
    children: int = 0
    infants_in_seat: int = 0
    infants_on_lap: int = 0
    passport_nationality: Optional[str] = None  # ISO 3166-1 alpha-2


@dataclass
class DateRange:
    """A target date with optional flexibility window."""
    target: str  # YYYY-MM-DD
    flex_days: int = 0  # search ±N days around target

    def all_dates(self) -> List[str]:
        """Return all dates in the flex window (inclusive)."""
        base = date.fromisoformat(self.target)
        return [
            (base + timedelta(days=d)).isoformat()
            for d in range(-self.flex_days, self.flex_days + 1)
        ]


@dataclass
class RouteConfig:
    origins: List[str]  # IATA codes
    destinations: List[str]  # IATA codes
    departure_date: DateRange
    return_date: Optional[DateRange] = None  # None for one-way
    trip_type: Literal["one-way", "round-trip", "multi-city"] = "round-trip"


@dataclass
class Constraints:
    """Hard constraints that proposals must satisfy."""
    cabin: Literal["economy", "premium-economy", "business", "first"] = "business"
    max_stops: Optional[int] = None
    max_total_duration_hours: Optional[float] = None
    min_layover_minutes: int = 60  # domestic default
    min_intl_layover_minutes: int = 120  # international default
    max_layover_minutes: int = 480  # 8 hours
    forbidden_transit_countries: List[str] = field(default_factory=list)  # ISO alpha-2
    forbidden_airlines: List[str] = field(default_factory=list)  # IATA 2-letter
    allowed_airlines: Optional[List[str]] = None  # None = all allowed
    max_segments: int = 4  # max flight legs per direction


@dataclass
class ScoringWeights:
    """Weights for the scoring function. Higher = more important."""
    price: float = 1.0
    total_duration_hours: float = 0.0  # penalty per hour
    stops_penalty: float = 0.0  # penalty per stop
    positioning_cost: float = 1.0  # multiplier for extra positioning leg cost


DEFAULT_HUB_AIRPORTS: List[str] = [
    "CDG", "IST", "DOH", "SIN", "HKG", "BKK", "AMS", "FRA",
    "LHR", "NRT", "ICN", "DXB", "JFK", "LAX", "ORD",
]


@dataclass
class StrategyConfig:
    """Which creative strategies the proposal generator should explore."""
    date_shifts: bool = True
    alternate_airports: bool = True
    alternate_airport_radius_km: int = 200
    split_tickets: bool = True
    open_jaw: bool = True
    hub_routing: bool = True
    hub_airports: List[str] = field(default_factory=lambda: list(DEFAULT_HUB_AIRPORTS))
    positioning_legs: bool = True


@dataclass
class LoopConfig:
    """Controls for the autoresearch loop."""
    max_iterations: int = 50
    proposals_per_iteration: int = 8
    no_improvement_stop: int = 5  # stop after N rounds with no improvement
    max_searches: int = 200  # total search budget
    timeout_minutes: int = 30


@dataclass
class LLMConfig:
    """LLM provider settings for the proposal generator."""
    provider: Literal["anthropic", "openai"] = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key_env: str = "ANTHROPIC_API_KEY"  # env var name holding the key
    temperature: float = 0.8
    max_tokens: int = 2048

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise EnvironmentError(
                f"Set {self.api_key_env} environment variable for LLM access"
            )
        return key


@dataclass
class AutofareConfig:
    """Top-level configuration for an Autofare search session."""
    query: str  # original natural-language query
    route: RouteConfig
    passengers: PassengerConfig = field(default_factory=PassengerConfig)
    constraints: Constraints = field(default_factory=Constraints)
    scoring: ScoringWeights = field(default_factory=ScoringWeights)
    strategies: StrategyConfig = field(default_factory=StrategyConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    fetch_mode: Literal["common", "fallback", "force-fallback", "local", "bright-data"] = "common"
    currency: str = "USD"


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

def _get(d: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Nested dict access with dot notation: 'a.b.c' -> d['a']['b']['c']."""
    keys = key.split(".")
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


def load_config(path: str) -> AutofareConfig:
    """Load an AutofareConfig from a YAML file."""
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return parse_config_dict(raw)


def load_config_from_string(yaml_string: str) -> AutofareConfig:
    """Load an AutofareConfig from a YAML string."""
    raw = yaml.safe_load(yaml_string)
    return parse_config_dict(raw)


def parse_config_dict(raw: Dict[str, Any]) -> AutofareConfig:
    """Parse a raw dict (from YAML or otherwise) into AutofareConfig."""
    # --- Route ---
    route_raw = raw.get("route", {})
    origins = route_raw.get("origins", [])
    if isinstance(origins, str):
        origins = [origins]
    destinations = route_raw.get("destinations", [])
    if isinstance(destinations, str):
        destinations = [destinations]

    dep_raw = route_raw.get("departure_date", {})
    if isinstance(dep_raw, str):
        dep_raw = {"target": dep_raw}
    departure_date = DateRange(
        target=str(dep_raw.get("target", "")),
        flex_days=int(dep_raw.get("flex_days", 0)),
    )

    ret_raw = route_raw.get("return_date")
    return_date = None
    if ret_raw is not None:
        if isinstance(ret_raw, str):
            ret_raw = {"target": ret_raw}
        return_date = DateRange(
            target=str(ret_raw.get("target", "")),
            flex_days=int(ret_raw.get("flex_days", 0)),
        )

    trip_type = route_raw.get("trip_type", "round-trip" if return_date else "one-way")

    route = RouteConfig(
        origins=origins,
        destinations=destinations,
        departure_date=departure_date,
        return_date=return_date,
        trip_type=trip_type,
    )

    # --- Passengers ---
    pax_raw = raw.get("passengers", {})
    passengers = PassengerConfig(
        adults=int(pax_raw.get("adults", 1)),
        children=int(pax_raw.get("children", 0)),
        infants_in_seat=int(pax_raw.get("infants_in_seat", 0)),
        infants_on_lap=int(pax_raw.get("infants_on_lap", 0)),
        passport_nationality=pax_raw.get("passport_nationality"),
    )

    # --- Constraints ---
    cons_raw = raw.get("constraints", {})
    constraints = Constraints(
        cabin=cons_raw.get("cabin", "business"),
        max_stops=cons_raw.get("max_stops"),
        max_total_duration_hours=cons_raw.get("max_total_duration_hours"),
        min_layover_minutes=int(cons_raw.get("min_layover_minutes", 60)),
        min_intl_layover_minutes=int(cons_raw.get("min_intl_layover_minutes", 120)),
        max_layover_minutes=int(cons_raw.get("max_layover_minutes", 480)),
        forbidden_transit_countries=cons_raw.get("forbidden_transit_countries", []),
        forbidden_airlines=cons_raw.get("forbidden_airlines", []),
        allowed_airlines=cons_raw.get("allowed_airlines"),
        max_segments=int(cons_raw.get("max_segments", 4)),
    )

    # --- Scoring ---
    sc_raw = raw.get("scoring", {})
    scoring = ScoringWeights(
        price=float(sc_raw.get("price", 1.0)),
        total_duration_hours=float(sc_raw.get("total_duration_hours", 0.0)),
        stops_penalty=float(sc_raw.get("stops_penalty", 0.0)),
        positioning_cost=float(sc_raw.get("positioning_cost", 1.0)),
    )

    # --- Strategies ---
    strat_raw = raw.get("strategies", {})
    strategies = StrategyConfig(
        date_shifts=strat_raw.get("date_shifts", True),
        alternate_airports=strat_raw.get("alternate_airports", True),
        alternate_airport_radius_km=int(strat_raw.get("alternate_airport_radius_km", 200)),
        split_tickets=strat_raw.get("split_tickets", True),
        open_jaw=strat_raw.get("open_jaw", True),
        hub_routing=strat_raw.get("hub_routing", True),
        hub_airports=strat_raw.get("hub_airports", list(DEFAULT_HUB_AIRPORTS)),
        positioning_legs=strat_raw.get("positioning_legs", True),
    )

    # --- Loop ---
    loop_raw = raw.get("loop", {})
    loop = LoopConfig(
        max_iterations=int(loop_raw.get("max_iterations", 50)),
        proposals_per_iteration=int(loop_raw.get("proposals_per_iteration", 8)),
        no_improvement_stop=int(loop_raw.get("no_improvement_stop", 5)),
        max_searches=int(loop_raw.get("max_searches", 200)),
        timeout_minutes=int(loop_raw.get("timeout_minutes", 30)),
    )

    # --- LLM ---
    llm_raw = raw.get("llm", {})
    llm = LLMConfig(
        provider=llm_raw.get("provider", "anthropic"),
        model=llm_raw.get("model", "claude-sonnet-4-20250514"),
        api_key_env=llm_raw.get("api_key_env", "ANTHROPIC_API_KEY"),
        temperature=float(llm_raw.get("temperature", 0.8)),
        max_tokens=int(llm_raw.get("max_tokens", 2048)),
    )

    return AutofareConfig(
        query=raw.get("query", ""),
        route=route,
        passengers=passengers,
        constraints=constraints,
        scoring=scoring,
        strategies=strategies,
        loop=loop,
        llm=llm,
        fetch_mode=raw.get("fetch_mode", "common"),
        currency=raw.get("currency", "USD"),
    )


# ---------------------------------------------------------------------------
# Quick query parser — extracts structured config from plain English
# ---------------------------------------------------------------------------

# Nearby airport lookup: maps an IATA code to its metro-area alternatives
NEARBY_AIRPORTS: Dict[str, List[str]] = {
    "SFO": ["OAK", "SJC", "SMF"],
    "OAK": ["SFO", "SJC"],
    "SJC": ["SFO", "OAK"],
    "LAX": ["BUR", "LGB", "SNA", "ONT"],
    "JFK": ["EWR", "LGA"],
    "EWR": ["JFK", "LGA"],
    "LGA": ["JFK", "EWR"],
    "ORD": ["MDW"],
    "MDW": ["ORD"],
    "DCA": ["IAD", "BWI"],
    "IAD": ["DCA", "BWI"],
    "DEL": ["BOM", "BLR", "HYD", "MAA", "CCU"],
    "BOM": ["DEL", "BLR", "HYD", "PNQ"],
    "SEA": ["PDX"],
    "PDX": ["SEA"],
    "LHR": ["LGW", "STN", "LTN"],
    "CDG": ["ORY"],
    "NRT": ["HND"],
    "HND": ["NRT"],
    "ICN": ["GMP"],
    "SIN": ["KUL"],
    "HKG": ["MFM", "SZX"],
    "BKK": ["DMK"],
}

# Country codes for common transit hubs (for passport rule lookups)
AIRPORT_COUNTRY: Dict[str, str] = {
    "DXB": "AE", "AUH": "AE", "DOH": "QA", "BAH": "BH", "MCT": "OM",
    "RUH": "SA", "JED": "SA", "KWI": "KW", "AMM": "JO", "BEY": "LB",
    "IST": "TR", "CDG": "FR", "ORY": "FR", "AMS": "NL", "FRA": "DE",
    "MUC": "DE", "LHR": "GB", "LGW": "GB", "ZRH": "CH", "FCO": "IT",
    "MAD": "ES", "BCN": "ES", "HEL": "FI", "CPH": "DK", "OSL": "NO",
    "ARN": "SE", "VIE": "AT", "BRU": "BE", "LIS": "PT",
    "SIN": "SG", "HKG": "HK", "BKK": "TH", "DMK": "TH",
    "NRT": "JP", "HND": "JP", "KIX": "JP", "ICN": "KR", "GMP": "KR",
    "TPE": "TW", "KUL": "MY", "CGK": "ID",
    "DEL": "IN", "BOM": "IN", "BLR": "IN", "MAA": "IN", "HYD": "IN",
    "CCU": "IN", "PNQ": "IN",
    "JFK": "US", "EWR": "US", "LGA": "US", "LAX": "US", "SFO": "US",
    "OAK": "US", "SJC": "US", "SEA": "US", "ORD": "US", "MDW": "US",
    "DCA": "US", "IAD": "US", "BWI": "US", "ATL": "US", "DFW": "US",
    "DEN": "US", "MIA": "US", "BOS": "US", "MSP": "US", "DTW": "US",
    "PHL": "US", "CLT": "US", "PHX": "US", "SLC": "US", "SMF": "US",
    "BUR": "US", "LGB": "US", "SNA": "US", "ONT": "US", "PDX": "US",
    "YYZ": "CA", "YVR": "CA", "YUL": "CA",
    "SYD": "AU", "MEL": "AU", "AKL": "NZ",
    "GRU": "BR", "EZE": "AR", "SCL": "CL", "BOG": "CO", "LIM": "PE",
    "MEX": "MX", "CUN": "MX",
    "JNB": "ZA", "CPT": "ZA", "NBO": "KE", "ADD": "ET", "CAI": "EG",
    "CMN": "MA", "LOS": "NG",
}

# Middle East country codes (common exclusion set)
MIDDLE_EAST_COUNTRIES = {"AE", "QA", "BH", "OM", "SA", "KW", "JO", "LB", "IQ", "IR", "SY", "YE"}


def parse_query(query: str) -> AutofareConfig:
    """
    Best-effort parse of a natural-language flight query into AutofareConfig.

    Examples:
        "business class DEL to SFO, April 12-14, no Middle East transit, Indian passport"
        "first class JFK to NRT round trip May 1 return May 15"
    """
    q = query.strip()

    # --- Cabin ---
    cabin = "business"
    for c in ["first", "business", "premium-economy", "economy"]:
        if c in q.lower():
            cabin = c
            break

    # --- Airports: look for "XXX to YYY" ---
    airport_match = re.search(r'\b([A-Z]{3})\s+to\s+([A-Z]{3})\b', q)
    origin = airport_match.group(1) if airport_match else "DEL"
    destination = airport_match.group(2) if airport_match else "SFO"

    # --- Dates ---
    # Try patterns like "April 12-14", "May 1 return May 15", "2025-04-12"
    dep_date = None
    ret_date = None
    flex = 1  # default flex

    # ISO dates
    iso_dates = re.findall(r'\d{4}-\d{2}-\d{2}', q)
    if len(iso_dates) >= 2:
        dep_date = iso_dates[0]
        ret_date = iso_dates[1]
    elif len(iso_dates) == 1:
        dep_date = iso_dates[0]

    # Named month patterns: "April 12" or "April 12-14"
    if dep_date is None:
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }
        month_pat = '|'.join(month_names.keys())
        range_match = re.search(
            rf'({month_pat})\s+(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})',
            q.lower(),
        )
        if range_match:
            month = month_names[range_match.group(1)]
            day1 = int(range_match.group(2))
            day2 = int(range_match.group(3))
            year = date.today().year
            dep_date = date(year, month, day1).isoformat()
            ret_date = date(year, month, day2).isoformat()
        else:
            single_match = re.search(
                rf'({month_pat})\s+(\d{{1,2}})',
                q.lower(),
            )
            if single_match:
                month = month_names[single_match.group(1)]
                day = int(single_match.group(2))
                year = date.today().year
                dep_date = date(year, month, day).isoformat()

    # "this weekend" heuristic
    if dep_date is None and "this weekend" in q.lower():
        today = date.today()
        # Next Saturday
        days_until_sat = (5 - today.weekday()) % 7
        if days_until_sat == 0:
            days_until_sat = 7
        saturday = today + timedelta(days=days_until_sat)
        sunday = saturday + timedelta(days=1)
        dep_date = saturday.isoformat()
        ret_date = sunday.isoformat()
        flex = 2

    # Fallback: tomorrow
    if dep_date is None:
        dep_date = (date.today() + timedelta(days=7)).isoformat()

    # "return" keyword for return date
    if ret_date is None:
        ret_match = re.search(r'return\s+(\w+\s+\d{1,2})', q.lower())
        if ret_match:
            # Try parsing
            month_names_map = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }
            parts = ret_match.group(1).split()
            if len(parts) == 2 and parts[0] in month_names_map:
                year = date.today().year
                ret_date = date(year, month_names_map[parts[0]], int(parts[1])).isoformat()

    # --- Trip type ---
    trip_type: Literal["one-way", "round-trip", "multi-city"] = "one-way"
    if ret_date is not None:
        trip_type = "round-trip"
    if "one way" in q.lower() or "one-way" in q.lower():
        trip_type = "one-way"
        ret_date = None
    if "round trip" in q.lower() or "round-trip" in q.lower():
        trip_type = "round-trip"

    # --- Forbidden transit ---
    forbidden = []
    if "no middle east" in q.lower():
        forbidden = list(MIDDLE_EAST_COUNTRIES)

    # Parse "no <country> transit"
    no_transit_match = re.findall(r'no\s+(\w+)\s+transit', q.lower())
    for country_name in no_transit_match:
        if country_name == "middle" or country_name in ("east",):
            continue  # handled above

    # --- Passport ---
    passport = None
    passport_match = re.search(r'(indian|us|american|british|canadian|chinese|japanese|korean|australian)\s+passport', q.lower())
    if passport_match:
        nationality_map = {
            "indian": "IN", "us": "US", "american": "US", "british": "GB",
            "canadian": "CA", "chinese": "CN", "japanese": "JP",
            "korean": "KR", "australian": "AU",
        }
        passport = nationality_map.get(passport_match.group(1))

    # --- Build config ---
    route = RouteConfig(
        origins=[origin],
        destinations=[destination],
        departure_date=DateRange(target=dep_date, flex_days=flex),
        return_date=DateRange(target=ret_date, flex_days=flex) if ret_date else None,
        trip_type=trip_type,
    )

    return AutofareConfig(
        query=query,
        route=route,
        passengers=PassengerConfig(adults=1, passport_nationality=passport),
        constraints=Constraints(
            cabin=cabin,
            forbidden_transit_countries=forbidden,
        ),
        strategies=StrategyConfig(
            hub_airports=[
                h for h in DEFAULT_HUB_AIRPORTS
                if AIRPORT_COUNTRY.get(h, "") not in set(forbidden)
            ] if forbidden else list(DEFAULT_HUB_AIRPORTS),
        ),
    )


def config_to_yaml(config: AutofareConfig) -> str:
    """Serialize an AutofareConfig back to YAML string."""
    d = {
        "query": config.query,
        "route": {
            "origins": config.route.origins,
            "destinations": config.route.destinations,
            "departure_date": {
                "target": config.route.departure_date.target,
                "flex_days": config.route.departure_date.flex_days,
            },
            "trip_type": config.route.trip_type,
        },
        "passengers": {
            "adults": config.passengers.adults,
            "children": config.passengers.children,
            "passport_nationality": config.passengers.passport_nationality,
        },
        "constraints": {
            "cabin": config.constraints.cabin,
            "max_stops": config.constraints.max_stops,
            "max_total_duration_hours": config.constraints.max_total_duration_hours,
            "min_layover_minutes": config.constraints.min_layover_minutes,
            "min_intl_layover_minutes": config.constraints.min_intl_layover_minutes,
            "forbidden_transit_countries": config.constraints.forbidden_transit_countries,
            "forbidden_airlines": config.constraints.forbidden_airlines,
            "max_segments": config.constraints.max_segments,
        },
        "scoring": {
            "price": config.scoring.price,
            "total_duration_hours": config.scoring.total_duration_hours,
            "stops_penalty": config.scoring.stops_penalty,
            "positioning_cost": config.scoring.positioning_cost,
        },
        "strategies": {
            "date_shifts": config.strategies.date_shifts,
            "alternate_airports": config.strategies.alternate_airports,
            "split_tickets": config.strategies.split_tickets,
            "open_jaw": config.strategies.open_jaw,
            "hub_routing": config.strategies.hub_routing,
            "hub_airports": config.strategies.hub_airports,
            "positioning_legs": config.strategies.positioning_legs,
        },
        "loop": {
            "max_iterations": config.loop.max_iterations,
            "proposals_per_iteration": config.loop.proposals_per_iteration,
            "no_improvement_stop": config.loop.no_improvement_stop,
            "max_searches": config.loop.max_searches,
            "timeout_minutes": config.loop.timeout_minutes,
        },
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "api_key_env": config.llm.api_key_env,
            "temperature": config.llm.temperature,
        },
        "fetch_mode": config.fetch_mode,
        "currency": config.currency,
    }

    if config.route.return_date:
        d["route"]["return_date"] = {
            "target": config.route.return_date.target,
            "flex_days": config.route.return_date.flex_days,
        }

    return yaml.dump(d, default_flow_style=False, sort_keys=False)
