"""
Main Autofare Loop — Karpathy-style autoresearch applied to flight search.

Separates creativity (LLM proposals) from trustworthy evaluation (deterministic
validation). Loops until no improvements are found or budget is exhausted.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import AutofareConfig
from .flight_search import FlightSearchEngine, FlightOption, SearchQuery, SearchResult
from .validator import ScoredItinerary, validate_and_score
from .proposer import ProposalGenerator, Proposal

logger = logging.getLogger("autofare")


# ---------------------------------------------------------------------------
# Session state — tracks the full history of the optimization run
# ---------------------------------------------------------------------------

@dataclass
class IterationLog:
    """Log entry for one loop iteration."""
    iteration: int
    proposals: List[Proposal]
    searches_run: int
    results: List[SearchResult]
    best_found: Optional[ScoredItinerary]
    improved: bool
    duration_seconds: float


@dataclass
class AutofareSession:
    """Full state of an Autofare optimization run."""
    config: AutofareConfig
    best: Optional[ScoredItinerary] = None
    baseline: Optional[ScoredItinerary] = None
    all_valid: List[ScoredItinerary] = field(default_factory=list)
    iteration_logs: List[IterationLog] = field(default_factory=list)
    total_searches: int = 0
    total_proposals: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def elapsed_minutes(self) -> float:
        end = self.end_time or time.time()
        return (end - self.start_time) / 60.0

    @property
    def savings(self) -> float:
        if self.baseline and self.best:
            return self.baseline.effective_cost - self.best.effective_cost
        return 0.0

    @property
    def savings_pct(self) -> float:
        if self.baseline and self.baseline.effective_cost > 0 and self.savings > 0:
            return (self.savings / self.baseline.effective_cost) * 100
        return 0.0

    def top_n(self, n: int = 5) -> List[ScoredItinerary]:
        """Return the top N itineraries by score."""
        return sorted(self.all_valid, key=lambda x: x.score)[:n]


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_autofare(config: AutofareConfig) -> AutofareSession:
    """
    Run the full Autofare optimization loop.

    1. Execute baseline searches.
    2. In each iteration: generate proposals → search → validate → score.
    3. Keep the best valid itinerary.
    4. Stop when budget exhausted or no improvement for N rounds.
    """
    session = AutofareSession(config=config, start_time=time.time())
    engine = FlightSearchEngine(config)
    proposer = ProposalGenerator(config)

    # Logging header
    logger.info("=" * 70)
    logger.info("AUTOFARE — Autonomous Flight Search Optimizer")
    logger.info("=" * 70)
    logger.info(f"Query: {config.query}")
    logger.info(f"Route: {config.route.origins} → {config.route.destinations}")
    logger.info(f"Dates: {config.route.departure_date.target} "
                f"(±{config.route.departure_date.flex_days} days)")
    logger.info(f"Cabin: {config.constraints.cabin}")
    logger.info(f"Budget: {config.loop.max_searches} searches, "
                f"{config.loop.max_iterations} iterations")
    logger.info("=" * 70)

    # ---- Phase 1: Baseline ----
    logger.info("\n[PHASE 1] Running baseline searches...")
    baseline_queries = engine.build_baseline_queries()
    baseline_results = engine.search_batch(baseline_queries)

    # Validate and score baseline results
    actual_origin = config.route.origins[0]
    actual_dest = config.route.destinations[0]

    for query, result in zip(baseline_queries, baseline_results):
        if result.error:
            continue
        scored = validate_and_score(
            config, query, result,
            strategy_label="baseline",
            actual_origin=actual_origin,
            actual_destination=actual_dest,
        )
        session.all_valid.extend(scored)

    # Set baseline best
    if session.all_valid:
        session.all_valid.sort(key=lambda x: x.score)
        session.baseline = session.all_valid[0]
        session.best = session.all_valid[0]
        logger.info(f"\nBaseline best: {session.best.summary()}")
    else:
        logger.warning("No valid baseline results found!")

    session.total_searches = engine.total_searches

    # ---- Phase 2: Optimization loop ----
    logger.info(f"\n[PHASE 2] Starting optimization loop...")
    no_improvement_count = 0

    for iteration in range(config.loop.max_iterations):
        iter_start = time.time()

        # Check stop conditions
        if engine.total_searches >= config.loop.max_searches:
            logger.info(f"Search budget exhausted ({engine.total_searches} searches)")
            break

        if no_improvement_count >= config.loop.no_improvement_stop:
            logger.info(
                f"No improvement for {no_improvement_count} rounds — stopping"
            )
            break

        elapsed_min = (time.time() - session.start_time) / 60.0
        if elapsed_min >= config.loop.timeout_minutes:
            logger.info(f"Time budget exhausted ({elapsed_min:.1f} min)")
            break

        budget_remaining = config.loop.max_searches - engine.total_searches
        best_str = f"${session.best.effective_cost:.0f}" if session.best else "N/A"
        logger.info(
            f"\n--- Iteration {iteration + 1} "
            f"(searches: {engine.total_searches}/{config.loop.max_searches}, "
            f"best: {best_str}) ---"
        )

        # Generate proposals
        proposals = proposer.generate(
            iteration=iteration,
            best_so_far=session.best,
            budget_remaining=budget_remaining,
        )

        if not proposals:
            logger.info("No more proposals to try — stopping")
            break

        session.total_proposals += len(proposals)

        # Execute each proposal
        iter_results = []
        iter_searches = 0
        iteration_best: Optional[ScoredItinerary] = None
        improved = False

        for proposal in proposals:
            if engine.total_searches >= config.loop.max_searches:
                break

            logger.info(f"  [{proposal.strategy}] {proposal.reasoning}")

            # A proposal may have multiple queries (e.g., hub routing = 2 legs)
            proposal_total_price = 0.0
            proposal_valid = True
            proposal_options = []

            is_multi_leg = len(proposal.queries) > 1
            leg_options: List[List[ScoredItinerary]] = []

            for pq in proposal.queries:
                result = engine.search(pq)
                iter_results.append(result)
                iter_searches += 1

                if result.error or not result.cheapest:
                    proposal_valid = False
                    break

                scored = validate_and_score(
                    config, pq, result,
                    strategy_label=proposal.strategy,
                    actual_origin=actual_origin,
                    actual_destination=actual_dest,
                )

                if scored:
                    leg_options.append(scored)
                    # Only add individual legs to all_valid for single-leg proposals
                    if not is_multi_leg:
                        proposal_options.extend(scored)
                        session.all_valid.extend(scored)
                else:
                    proposal_valid = False
                    break

            # For multi-leg proposals (hub routing, split tickets),
            # compute combined cost using cheapest option from each leg
            if proposal_valid and is_multi_leg and leg_options:
                cheapest_per_leg = [min(leg, key=lambda x: x.effective_cost) for leg in leg_options]
                combined_cost = sum(opt.effective_cost for opt in cheapest_per_leg)

                # Build a descriptive summary for the combined itinerary
                route_parts = [f"{opt.query.origin}→{opt.query.destination}" for opt in cheapest_per_leg]
                airlines = [opt.option.airline for opt in cheapest_per_leg if opt.option.airline]
                combined_airline = " + ".join(airlines) if airlines else ""

                first_leg = cheapest_per_leg[0]
                combined = ScoredItinerary(
                    query=first_leg.query,
                    result=first_leg.result,
                    option=FlightOption(
                        airline=combined_airline,
                        departure_time=first_leg.option.departure_time,
                        arrival_time=cheapest_per_leg[-1].option.arrival_time,
                        arrival_time_ahead=cheapest_per_leg[-1].option.arrival_time_ahead,
                        duration=" + ".join(opt.option.duration for opt in cheapest_per_leg if opt.option.duration),
                        stops=sum(opt.option.stops for opt in cheapest_per_leg if isinstance(opt.option.stops, int)),
                        price_raw=f"${combined_cost:.0f}",
                        price_usd=combined_cost,
                        is_best=False,
                    ),
                    score=combined_cost,
                    effective_cost=combined_cost,
                    positioning_cost=first_leg.positioning_cost,
                    validation=first_leg.validation,
                    strategy_label=f"{proposal.strategy} ({' → '.join(route_parts)})",
                )
                session.all_valid.append(combined)
                proposal_options = [combined]

            # Check if any option in this proposal beats current best
            for opt in proposal_options:
                if session.best is None or opt.effective_cost < session.best.effective_cost:
                    was_str = f"${session.best.effective_cost:.0f}" if session.best else "N/A"
                    logger.info(
                        f"  ★ NEW BEST: {opt.summary()} (was: {was_str})"
                    )
                    session.best = opt
                    improved = True
                    no_improvement_count = 0

                if iteration_best is None or opt.effective_cost < iteration_best.effective_cost:
                    iteration_best = opt

        if not improved:
            no_improvement_count += 1

        iter_duration = time.time() - iter_start
        session.iteration_logs.append(IterationLog(
            iteration=iteration + 1,
            proposals=proposals,
            searches_run=iter_searches,
            results=iter_results,
            best_found=iteration_best,
            improved=improved,
            duration_seconds=iter_duration,
        ))
        session.total_searches = engine.total_searches

        logger.info(
            f"  Iteration {iteration + 1} done: "
            f"{iter_searches} searches, "
            f"{'improved!' if improved else 'no improvement'} "
            f"({iter_duration:.1f}s)"
        )

    # ---- Finalize ----
    session.end_time = time.time()
    session.total_searches = engine.total_searches

    _print_summary(session)
    return session


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------

def _print_summary(session: AutofareSession) -> None:
    """Print the final optimization summary."""
    logger.info("\n" + "=" * 70)
    logger.info("AUTOFARE — RESULTS SUMMARY")
    logger.info("=" * 70)

    logger.info(f"Total searches executed: {session.total_searches}")
    logger.info(f"Total proposals evaluated: {session.total_proposals}")
    logger.info(f"Total valid itineraries found: {len(session.all_valid)}")
    logger.info(f"Time elapsed: {session.elapsed_minutes:.1f} minutes")

    if session.baseline:
        logger.info(f"\nBaseline: {session.baseline.summary()}")

    if session.best:
        logger.info(f"Best found: {session.best.summary()}")

        if session.savings > 0:
            logger.info(
                f"\n★ SAVINGS: ${session.savings:.0f} "
                f"({session.savings_pct:.1f}% cheaper than baseline)"
            )
        elif session.baseline:
            logger.info("\nNo improvement over baseline found.")

    logger.info(f"\nTop 5 options:")
    for i, opt in enumerate(session.top_n(5), 1):
        logger.info(f"  {i}. {opt.summary()}")

    # Strategy effectiveness
    strategy_hits: Dict[str, int] = {}
    for opt in session.all_valid:
        strategy_hits[opt.strategy_label] = strategy_hits.get(opt.strategy_label, 0) + 1

    if strategy_hits:
        logger.info(f"\nStrategy effectiveness (valid results):")
        for strat, count in sorted(strategy_hits.items(), key=lambda x: -x[1])[:10]:
            logger.info(f"  {strat}: {count} valid options")

    logger.info("=" * 70)


def format_report(session: AutofareSession) -> str:
    """Generate a human-readable text report of the optimization."""
    lines = []
    lines.append("=" * 70)
    lines.append("AUTOFARE — Flight Search Optimization Report")
    lines.append("=" * 70)
    lines.append(f"Query: {session.config.query}")
    lines.append(f"Route: {' / '.join(session.config.route.origins)} → "
                 f"{' / '.join(session.config.route.destinations)}")
    lines.append(f"Dates: {session.config.route.departure_date.target}")
    lines.append(f"Cabin: {session.config.constraints.cabin}")
    lines.append("")
    lines.append(f"Searches: {session.total_searches}")
    lines.append(f"Proposals: {session.total_proposals}")
    lines.append(f"Valid options: {len(session.all_valid)}")
    lines.append(f"Time: {session.elapsed_minutes:.1f} min")
    lines.append("")

    if session.baseline:
        lines.append(f"BASELINE: {session.baseline.summary()}")
    if session.best:
        lines.append(f"BEST:     {session.best.summary()}")
    if session.savings > 0:
        lines.append(f"SAVINGS:  ${session.savings:.0f} ({session.savings_pct:.1f}%)")

    lines.append("")
    lines.append("Top 10 options:")
    for i, opt in enumerate(session.top_n(10), 1):
        lines.append(f"  {i}. {opt.summary()}")

    lines.append("")
    lines.append("Iteration history:")
    for log in session.iteration_logs:
        status = "★" if log.improved else " "
        best_str = f"${log.best_found.effective_cost:.0f}" if log.best_found else "N/A"
        lines.append(
            f"  {status} Iter {log.iteration}: "
            f"{log.searches_run} searches, "
            f"best={best_str}, "
            f"{log.duration_seconds:.1f}s"
        )

    lines.append("=" * 70)
    return "\n".join(lines)
