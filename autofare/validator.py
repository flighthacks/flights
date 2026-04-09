"""
Validator & Scorer — deterministic, rule-based evaluation of flight proposals.

No LLM calls. Pure Python functions that check hard constraints and compute
a scalar score for each valid itinerary.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .config import (
    AutofareConfig,
    Constraints,
    ScoringWeights,
    AIRPORT_COUNTRY,
    MIDDLE_EAST_COUNTRIES,
)
from .flight_search import FlightOption, SearchResult, SearchQuery

logger = logging.getLogger("autofare.validator")


# ---------------------------------------------------------------------------
# Passport / visa transit rules (simplified lookup table)
# ---------------------------------------------------------------------------

# Countries where Indian passport holders CANNOT transit without a visa
# This is a simplified set — real-world rules are more nuanced
TRANSIT_VISA_REQUIRED: Dict[str, Set[str]] = {
    "IN": {
        "US", "CA", "GB", "AU", "NZ",  # Need visa to transit
        # Most EU Schengen countries allow airside transit for Indians
        # Middle East generally doesn't need transit visa
    },
    "CN": {
        "US", "CA", "GB", "AU",
    },
}

# Countries that allow visa-free transit (airside) for most nationalities
UNIVERSAL_TRANSIT_OK = {
    "SG",   # Singapore (96-hour transit)
    "AE",   # UAE (96-hour transit)
    "QA",   # Qatar (no transit visa needed)
    "TR",   # Turkey (for most nationalities)
    "TH",   # Thailand (airside transit ok)
    "MY",   # Malaysia (airside transit ok)
    "HK",   # Hong Kong (airside transit ok)
    "JP",   # Japan (shore pass available)
    "KR",   # South Korea (some transit programs)
    "TW",   # Taiwan (airside transit ok)
}


# ---------------------------------------------------------------------------
# Validation results
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Outcome of validating a flight proposal."""
    is_valid: bool
    reasons: List[str] = field(default_factory=list)  # why invalid
    warnings: List[str] = field(default_factory=list)  # non-blocking notes

    def add_rejection(self, reason: str) -> None:
        self.is_valid = False
        self.reasons.append(reason)

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)


@dataclass
class ScoredItinerary:
    """A validated and scored itinerary that can be compared."""
    query: SearchQuery
    result: SearchResult
    option: FlightOption
    score: float  # lower is better
    effective_cost: float  # total cost including positioning
    positioning_cost: float = 0.0  # estimated cost of getting to/from alternate airports
    validation: ValidationResult = field(default_factory=lambda: ValidationResult(is_valid=True))
    strategy_label: str = ""  # what strategy produced this

    @property
    def price(self) -> float:
        return self.option.price_usd or float('inf')

    def summary(self) -> str:
        stops_str = f"{self.option.stops} stop{'s' if self.option.stops != 1 else ''}"
        return (
            f"${self.effective_cost:.0f} | {self.query.origin}→{self.query.destination} "
            f"{self.query.date} | {self.option.airline} | {stops_str} | "
            f"{self.option.duration} | [{self.strategy_label}]"
        )


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class Validator:
    """Rule-based validator that checks hard constraints."""

    def __init__(self, config: AutofareConfig):
        self.config = config
        self.constraints = config.constraints
        self.passport = config.passengers.passport_nationality

    def validate(
        self,
        query: SearchQuery,
        option: FlightOption,
    ) -> ValidationResult:
        """Validate a single flight option against all hard constraints."""
        result = ValidationResult(is_valid=True)

        self._check_price(option, result)
        self._check_stops(option, result)
        self._check_duration(option, result)
        self._check_airline(option, result)
        self._check_transit_countries(query, option, result)
        self._check_passport_rules(query, option, result)

        return result

    def _check_price(self, option: FlightOption, result: ValidationResult) -> None:
        if option.price_usd is None:
            result.add_rejection("No parseable price")

    def _check_stops(self, option: FlightOption, result: ValidationResult) -> None:
        if self.constraints.max_stops is not None:
            if isinstance(option.stops, int) and option.stops > self.constraints.max_stops:
                result.add_rejection(
                    f"Too many stops: {option.stops} > max {self.constraints.max_stops}"
                )

    def _check_duration(self, option: FlightOption, result: ValidationResult) -> None:
        if self.constraints.max_total_duration_hours is None:
            return
        duration_hours = self._parse_duration_hours(option.duration)
        if duration_hours is not None and duration_hours > self.constraints.max_total_duration_hours:
            result.add_rejection(
                f"Duration {duration_hours:.1f}h > max {self.constraints.max_total_duration_hours}h"
            )

    def _check_airline(self, option: FlightOption, result: ValidationResult) -> None:
        airline_name = option.airline.upper() if option.airline else ""

        # Check forbidden airlines
        for forbidden in self.constraints.forbidden_airlines:
            if forbidden.upper() in airline_name:
                result.add_rejection(f"Forbidden airline: {forbidden}")
                return

        # Check allowed airlines (if whitelist is set)
        if self.constraints.allowed_airlines is not None:
            found = any(
                allowed.upper() in airline_name
                for allowed in self.constraints.allowed_airlines
            )
            if not found:
                result.add_rejection(
                    f"Airline '{option.airline}' not in allowed list"
                )

    def _check_transit_countries(
        self,
        query: SearchQuery,
        option: FlightOption,
        result: ValidationResult,
    ) -> None:
        """Check if any transit countries are forbidden."""
        if not self.constraints.forbidden_transit_countries:
            return

        forbidden_set = set(self.constraints.forbidden_transit_countries)

        # Check origin and destination countries
        origin_country = AIRPORT_COUNTRY.get(query.origin, "")
        dest_country = AIRPORT_COUNTRY.get(query.destination, "")

        # For transit, we care about intermediate stops, not origin/dest themselves.
        # Since fast_flights doesn't give us layover airports directly,
        # we use heuristics based on airline name and route.
        # If the option has stops > 0, we check known hub patterns.
        if option.stops == 0:
            return  # nonstop, no transit

        # Heuristic: certain airlines hub through specific countries
        airline_hubs = self._infer_transit_countries(option.airline, query.origin, query.destination)
        for country in airline_hubs:
            if country in forbidden_set:
                result.add_warning(
                    f"Airline {option.airline} likely transits through "
                    f"country {country} (forbidden)"
                )
                # Make it a rejection if we're fairly confident
                result.add_rejection(
                    f"Likely transit through forbidden country {country} "
                    f"via {option.airline} hub"
                )
                return

    def _check_passport_rules(
        self,
        query: SearchQuery,
        option: FlightOption,
        result: ValidationResult,
    ) -> None:
        """Check if passport nationality allows transit through route countries."""
        if not self.passport:
            return

        visa_required = TRANSIT_VISA_REQUIRED.get(self.passport, set())
        if not visa_required:
            return

        # Check if destination requires a visa we might not have
        dest_country = AIRPORT_COUNTRY.get(query.destination, "")
        # Don't check destination — user presumably has authorization to enter
        # Only check transit countries
        if option.stops > 0:
            transit_countries = self._infer_transit_countries(
                option.airline, query.origin, query.destination
            )
            for country in transit_countries:
                if country in visa_required and country not in UNIVERSAL_TRANSIT_OK:
                    result.add_warning(
                        f"Transit through {country} may require visa for "
                        f"{self.passport} passport"
                    )

    def _infer_transit_countries(
        self,
        airline: str,
        origin: str,
        destination: str,
    ) -> List[str]:
        """
        Heuristic: infer likely transit countries based on airline hub patterns.
        Returns list of ISO country codes.
        """
        airline_lower = airline.lower() if airline else ""
        countries = []

        # Map airlines to their primary hub countries
        airline_hub_map = {
            "emirates": ["AE"],
            "etihad": ["AE"],
            "qatar": ["QA"],
            "turkish": ["TR"],
            "air france": ["FR"],
            "klm": ["NL"],
            "lufthansa": ["DE"],
            "swiss": ["CH"],
            "british": ["GB"],
            "cathay": ["HK"],
            "singapore": ["SG"],
            "thai": ["TH"],
            "ana": ["JP"],
            "jal": ["JP"],
            "japan airlines": ["JP"],
            "korean air": ["KR"],
            "asiana": ["KR"],
            "eva air": ["TW"],
            "china airlines": ["TW"],
            "air china": ["CN"],
            "china eastern": ["CN"],
            "china southern": ["CN"],
            "delta": ["US"],
            "united": ["US"],
            "american": ["US"],
            "air india": ["IN"],
            "air canada": ["CA"],
            "qantas": ["AU"],
            "finnair": ["FI"],
            "sas": ["SE", "DK", "NO"],
            "lot": ["PL"],
            "ethiopian": ["ET"],
            "royal jordanian": ["JO"],
            "gulf air": ["BH"],
            "oman air": ["OM"],
            "saudia": ["SA"],
            "kuwait": ["KW"],
        }

        for pattern, hub_countries in airline_hub_map.items():
            if pattern in airline_lower:
                # Only add if hub country differs from origin and destination
                origin_country = AIRPORT_COUNTRY.get(origin, "")
                dest_country = AIRPORT_COUNTRY.get(destination, "")
                for hc in hub_countries:
                    if hc != origin_country and hc != dest_country:
                        countries.append(hc)

        return countries

    @staticmethod
    def _parse_duration_hours(duration_str: str) -> Optional[float]:
        """Parse duration strings like '14 hr 30 min', '5h 45m', '14hr'."""
        if not duration_str:
            return None
        hours = 0.0
        h_match = re.search(r'(\d+)\s*(?:hr|h)', duration_str.lower())
        m_match = re.search(r'(\d+)\s*(?:min|m)', duration_str.lower())
        if h_match:
            hours += int(h_match.group(1))
        if m_match:
            hours += int(m_match.group(1)) / 60
        return hours if (h_match or m_match) else None


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class Scorer:
    """Computes a scalar score for itineraries. Lower score = better."""

    def __init__(self, config: AutofareConfig):
        self.weights = config.scoring

    def score(
        self,
        option: FlightOption,
        positioning_cost: float = 0.0,
    ) -> Tuple[float, float]:
        """
        Score a flight option.

        Returns:
            (score, effective_cost) where:
            - score: weighted combination of all factors (lower = better)
            - effective_cost: total estimated cost in USD
        """
        price = option.price_usd or float('inf')
        effective_cost = price + (positioning_cost * self.weights.positioning_cost)

        score = effective_cost * self.weights.price

        # Duration penalty
        duration_hours = Validator._parse_duration_hours(option.duration)
        if duration_hours and self.weights.total_duration_hours > 0:
            score += duration_hours * self.weights.total_duration_hours

        # Stops penalty
        if isinstance(option.stops, int) and self.weights.stops_penalty > 0:
            score += option.stops * self.weights.stops_penalty

        return score, effective_cost

    def rank(
        self,
        itineraries: List[ScoredItinerary],
    ) -> List[ScoredItinerary]:
        """Rank itineraries by score (ascending = best first)."""
        return sorted(itineraries, key=lambda it: it.score)


# ---------------------------------------------------------------------------
# Positioning cost estimator
# ---------------------------------------------------------------------------

# Simple heuristic: estimated one-way positioning cost between airports
# More sophisticated version would do a quick search
POSITIONING_COST_ESTIMATES: Dict[Tuple[str, str], float] = {
    # US West Coast
    ("SFO", "OAK"): 0, ("SFO", "SJC"): 0, ("OAK", "SJC"): 0,
    ("SFO", "SMF"): 50, ("SFO", "SEA"): 120, ("SFO", "LAX"): 100,
    ("SFO", "PDX"): 100,
    # US East Coast
    ("JFK", "EWR"): 0, ("JFK", "LGA"): 0, ("EWR", "LGA"): 0,
    # US Midwest
    ("ORD", "MDW"): 0,
    # DC area
    ("DCA", "IAD"): 0, ("DCA", "BWI"): 0, ("IAD", "BWI"): 0,
    # India
    ("DEL", "BOM"): 80, ("DEL", "BLR"): 100, ("DEL", "HYD"): 90,
    ("DEL", "MAA"): 100, ("DEL", "CCU"): 80,
    ("BOM", "BLR"): 60, ("BOM", "HYD"): 70, ("BOM", "PNQ"): 30,
    # London
    ("LHR", "LGW"): 0, ("LHR", "STN"): 0, ("LHR", "LTN"): 0,
    # Paris
    ("CDG", "ORY"): 0,
    # Tokyo
    ("NRT", "HND"): 0,
    # Seoul
    ("ICN", "GMP"): 0,
}


def estimate_positioning_cost(airport_a: str, airport_b: str) -> float:
    """
    Estimate the cost of a positioning leg between two airports.
    Returns 0 if same airport, uses lookup table, or falls back to
    a distance-based heuristic.
    """
    if airport_a == airport_b:
        return 0.0

    # Check both directions in the lookup
    key1 = (airport_a, airport_b)
    key2 = (airport_b, airport_a)
    if key1 in POSITIONING_COST_ESTIMATES:
        return POSITIONING_COST_ESTIMATES[key1]
    if key2 in POSITIONING_COST_ESTIMATES:
        return POSITIONING_COST_ESTIMATES[key2]

    # Same-country heuristic
    country_a = AIRPORT_COUNTRY.get(airport_a, "??")
    country_b = AIRPORT_COUNTRY.get(airport_b, "??")
    if country_a == country_b and country_a != "??":
        return 100.0  # generic domestic positioning

    # International positioning fallback
    return 250.0


def validate_and_score(
    config: AutofareConfig,
    query: SearchQuery,
    result: SearchResult,
    strategy_label: str = "",
    actual_origin: Optional[str] = None,
    actual_destination: Optional[str] = None,
) -> List[ScoredItinerary]:
    """
    Validate and score all options from a search result.

    Args:
        config: The autofare configuration.
        query: The search query that produced the result.
        result: The search result with flight options.
        strategy_label: Label describing which strategy produced this.
        actual_origin: The user's actual origin (for positioning cost calc).
        actual_destination: The user's actual destination (for positioning cost calc).

    Returns:
        List of valid, scored itineraries (may be empty if all rejected).
    """
    validator = Validator(config)
    scorer = Scorer(config)

    # Calculate positioning cost if using alternate airports
    origin_positioning = 0.0
    dest_positioning = 0.0
    if actual_origin and actual_origin != query.origin:
        origin_positioning = estimate_positioning_cost(actual_origin, query.origin)
    if actual_destination and actual_destination != query.destination:
        dest_positioning = estimate_positioning_cost(actual_destination, query.destination)
    total_positioning = origin_positioning + dest_positioning

    scored = []
    for option in result.options:
        validation = validator.validate(query, option)
        if not validation.is_valid:
            logger.debug(
                f"  Rejected: {option.airline} ${option.price_usd} — "
                f"{', '.join(validation.reasons)}"
            )
            continue

        score, effective_cost = scorer.score(option, total_positioning)

        scored.append(ScoredItinerary(
            query=query,
            result=result,
            option=option,
            score=score,
            effective_cost=effective_cost,
            positioning_cost=total_positioning,
            validation=validation,
            strategy_label=strategy_label,
        ))

    return scorer.rank(scored)
