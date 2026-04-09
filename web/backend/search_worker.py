"""
Search Worker — runs autofare searches in background tasks with progress tracking.

Bridges the autofare engine with the web API, providing real-time progress
updates via an in-memory job store (consumed by the SSE endpoint).
"""

from __future__ import annotations

import logging
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("autofare.worker")

# In-memory job state for SSE streaming.
# In production, use Redis for multi-process support.
search_jobs: Dict[str, Dict[str, Any]] = {}


class SearchWorker:
    """Runs an autofare search and streams progress to the SSE store."""

    def __init__(self, job_id: str, db: Any):
        self.job_id = job_id
        self.db = db
        self._update_counter = 0

    async def run(
        self,
        query: str,
        config_yaml: Optional[str] = None,
        cabin: Optional[str] = None,
        flex_days: Optional[int] = None,
        max_searches: Optional[int] = None,
        currency: str = "USD",
    ):
        """Execute the autofare search loop with progress reporting."""
        import asyncio

        # Initialize job state
        search_jobs[self.job_id] = {
            "status": "running",
            "progress": {
                "update_id": 0,
                "status": "initializing",
                "message": "Parsing search query...",
                "searches_done": 0,
                "searches_total": 0,
                "best_price": None,
                "current_results": [],
            },
        }

        try:
            # Run the CPU-bound search in a thread to not block the event loop
            result = await asyncio.to_thread(
                self._run_sync, query, config_yaml, cabin, flex_days, max_searches, currency
            )

            # Update DB with final results
            now = datetime.now(timezone.utc).isoformat()
            await self.db.update_search_job(
                self.job_id,
                status="completed",
                completed_at=now,
                baseline_price=result.get("baseline_price"),
                best_price=result.get("best_price"),
                savings=result.get("savings"),
                savings_pct=result.get("savings_pct"),
                best_route=result.get("best_route"),
                best_airline=result.get("best_airline"),
                total_searches=result.get("total_searches", 0),
                top_results=result.get("top_results", []),
            )

            search_jobs[self.job_id]["status"] = "completed"
            self._emit_progress(
                status="completed",
                message="Search complete!",
                **result,
            )

        except Exception as e:
            logger.error(f"Search job {self.job_id} failed: {e}", exc_info=True)
            search_jobs[self.job_id]["status"] = "failed"
            self._emit_progress(status="failed", message=str(e)[:200])

            await self.db.update_search_job(
                self.job_id,
                status="failed",
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

    def _run_sync(
        self,
        query: str,
        config_yaml: Optional[str],
        cabin: Optional[str],
        flex_days: Optional[int],
        max_searches: Optional[int],
        currency: str,
    ) -> Dict[str, Any]:
        """Synchronous search execution (runs in thread)."""
        import sys
        sys.path.insert(0, "/home/user/flights")

        from autofare.config import parse_query, load_config_from_string, AutofareConfig
        from autofare.flight_search import FlightSearchEngine, SearchQuery
        from autofare.validator import validate_and_score, ScoredItinerary
        from autofare.proposer import ProposalGenerator

        # Build config
        if config_yaml:
            config = load_config_from_string(config_yaml)
        else:
            config = parse_query(query)

        # Apply overrides
        if cabin:
            config.constraints.cabin = cabin
        if flex_days is not None:
            config.route.departure_date.flex_days = flex_days
            if config.route.return_date:
                config.route.return_date.flex_days = flex_days
        if max_searches is not None:
            config.loop.max_searches = max_searches
        if currency:
            config.currency = currency

        # Initialize engine
        engine = FlightSearchEngine(config)
        proposer = ProposalGenerator(config)
        all_valid: List[ScoredItinerary] = []
        best: Optional[ScoredItinerary] = None
        baseline: Optional[ScoredItinerary] = None

        actual_origin = config.route.origins[0]
        actual_dest = config.route.destinations[0]

        # --- Phase 1: Baseline ---
        self._emit_progress(
            status="searching",
            message="Running baseline searches...",
            phase="baseline",
        )

        baseline_queries = engine.build_baseline_queries()
        total_budget = config.loop.max_searches

        for i, bq in enumerate(baseline_queries):
            if engine.total_searches >= total_budget:
                break

            result = engine.search(bq)

            self._emit_progress(
                status="searching",
                message=f"Baseline: {bq.origin}→{bq.destination} {bq.date}",
                phase="baseline",
                searches_done=engine.total_searches,
                searches_total=total_budget,
                current_query=str(bq),
            )

            if result.error:
                continue

            scored = validate_and_score(
                config, bq, result,
                strategy_label="baseline",
                actual_origin=actual_origin,
                actual_destination=actual_dest,
            )
            all_valid.extend(scored)

        # Set baseline
        if all_valid:
            all_valid.sort(key=lambda x: x.score)
            baseline = all_valid[0]
            best = all_valid[0]

        self._emit_progress(
            status="searching",
            message=f"Baseline done. Best so far: ${best.effective_cost:.0f}" if best else "Baseline done. No results.",
            phase="optimizing",
            searches_done=engine.total_searches,
            searches_total=total_budget,
            best_price=best.effective_cost if best else None,
            baseline_price=baseline.effective_cost if baseline else None,
        )

        # --- Phase 2: Optimization ---
        no_improvement_count = 0
        start_time = time.time()

        for iteration in range(config.loop.max_iterations):
            if engine.total_searches >= total_budget:
                break
            if no_improvement_count >= config.loop.no_improvement_stop:
                break
            if (time.time() - start_time) / 60 >= config.loop.timeout_minutes:
                break

            budget_remaining = total_budget - engine.total_searches
            proposals = proposer.generate(
                iteration=iteration,
                best_so_far=best,
                budget_remaining=budget_remaining,
            )

            if not proposals:
                break

            improved = False
            for proposal in proposals:
                if engine.total_searches >= total_budget:
                    break

                for pq in proposal.queries:
                    result = engine.search(pq)

                    self._emit_progress(
                        status="searching",
                        message=f"[{proposal.strategy}] {pq.origin}→{pq.destination}",
                        phase="optimizing",
                        iteration=iteration + 1,
                        searches_done=engine.total_searches,
                        searches_total=total_budget,
                        best_price=best.effective_cost if best else None,
                        strategy=proposal.strategy,
                    )

                    if result.error or not result.cheapest:
                        continue

                    scored = validate_and_score(
                        config, pq, result,
                        strategy_label=proposal.strategy,
                        actual_origin=actual_origin,
                        actual_destination=actual_dest,
                    )
                    all_valid.extend(scored)

                    for opt in scored:
                        if best is None or opt.effective_cost < best.effective_cost:
                            best = opt
                            improved = True
                            no_improvement_count = 0

                            self._emit_progress(
                                status="searching",
                                message=f"New best! ${opt.effective_cost:.0f} via {opt.option.airline}",
                                phase="optimizing",
                                searches_done=engine.total_searches,
                                searches_total=total_budget,
                                best_price=opt.effective_cost,
                                new_best=True,
                            )

            if not improved:
                no_improvement_count += 1

        # --- Build results ---
        all_valid.sort(key=lambda x: x.score)
        top_results = []
        seen = set()
        for opt in all_valid[:50]:
            key = f"{opt.query.origin}-{opt.query.destination}-{opt.option.airline}-{opt.option.price_usd}"
            if key in seen:
                continue
            seen.add(key)
            top_results.append({
                "origin": opt.query.origin,
                "destination": opt.query.destination,
                "date": opt.query.date,
                "airline": opt.option.airline,
                "price": opt.effective_cost,
                "stops": opt.option.stops,
                "duration": opt.option.duration,
                "departure_time": opt.option.departure_time,
                "arrival_time": opt.option.arrival_time,
                "strategy": opt.strategy_label,
            })

        savings = (baseline.effective_cost - best.effective_cost) if baseline and best else 0
        savings_pct = (savings / baseline.effective_cost * 100) if baseline and savings > 0 else 0

        return {
            "baseline_price": baseline.effective_cost if baseline else None,
            "best_price": best.effective_cost if best else None,
            "savings": savings if savings > 0 else 0,
            "savings_pct": savings_pct,
            "best_route": f"{best.query.origin}→{best.query.destination}" if best else None,
            "best_airline": best.option.airline if best else None,
            "total_searches": engine.total_searches,
            "top_results": top_results,
        }

    def _emit_progress(self, **kwargs):
        """Update the in-memory progress store for SSE streaming."""
        self._update_counter += 1
        kwargs["update_id"] = self._update_counter
        kwargs["timestamp"] = time.time()

        if self.job_id in search_jobs:
            search_jobs[self.job_id]["progress"] = kwargs
