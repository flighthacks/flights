#!/usr/bin/env python3
"""
Autofare CLI — autonomous flight search optimizer.

Usage:
    # Natural language query:
    python -m autofare "business class DEL to SFO, April 12-14, no Middle East transit, Indian passport"

    # From YAML config:
    python -m autofare --config search.yaml

    # Query with overrides:
    python -m autofare "DEL to SFO business" --flex-days 3 --max-searches 100

    # Generate YAML from query (dry run):
    python -m autofare "DEL to SFO business April 12" --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import (
    AutofareConfig,
    load_config,
    parse_query,
    config_to_yaml,
)
from .autofare_loop import run_autofare, format_report


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger("autofare")
    root.setLevel(level)
    root.addHandler(handler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autofare",
        description="Autofare: Autonomous flight search optimizer",
        epilog="Example: python -m autofare 'business class DEL to SFO April 12-14'",
    )

    parser.add_argument(
        "query",
        nargs="?",
        help="Natural language flight search query",
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse query and print YAML config without searching",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    # Override options
    overrides = parser.add_argument_group("Search overrides")
    overrides.add_argument(
        "--cabin",
        choices=["economy", "premium-economy", "business", "first"],
        help="Override cabin class",
    )
    overrides.add_argument(
        "--flex-days",
        type=int,
        help="Override date flexibility (±N days)",
    )
    overrides.add_argument(
        "--max-searches",
        type=int,
        help="Override max search budget",
    )
    overrides.add_argument(
        "--max-iterations",
        type=int,
        help="Override max loop iterations",
    )
    overrides.add_argument(
        "--max-stops",
        type=int,
        help="Maximum number of stops",
    )
    overrides.add_argument(
        "--fetch-mode",
        choices=["common", "fallback", "force-fallback", "local", "bright-data"],
        help="Override fetch mode for Google Flights",
    )
    overrides.add_argument(
        "--currency",
        help="Currency code (e.g., USD, EUR, INR)",
    )
    overrides.add_argument(
        "--llm-provider",
        choices=["anthropic", "openai"],
        help="LLM provider for proposal generation",
    )
    overrides.add_argument(
        "--llm-model",
        help="LLM model name",
    )
    overrides.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM proposals (use only built-in strategies)",
    )
    overrides.add_argument(
        "--output", "-o",
        help="Save report to file",
    )

    return parser


def apply_overrides(config: AutofareConfig, args: argparse.Namespace) -> None:
    """Apply CLI argument overrides to the config."""
    if args.cabin:
        config.constraints.cabin = args.cabin
    if args.flex_days is not None:
        config.route.departure_date.flex_days = args.flex_days
        if config.route.return_date:
            config.route.return_date.flex_days = args.flex_days
    if args.max_searches is not None:
        config.loop.max_searches = args.max_searches
    if args.max_iterations is not None:
        config.loop.max_iterations = args.max_iterations
    if args.max_stops is not None:
        config.constraints.max_stops = args.max_stops
    if args.fetch_mode:
        config.fetch_mode = args.fetch_mode
    if args.currency:
        config.currency = args.currency
    if args.llm_provider:
        config.llm.provider = args.llm_provider
    if args.llm_model:
        config.llm.model = args.llm_model
    if args.no_llm:
        # Set max iterations to 1 to only use built-in strategies
        config.loop.max_iterations = 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.query and not args.config:
        parser.print_help()
        return 1

    setup_logging(verbose=args.verbose)
    logger = logging.getLogger("autofare")

    # Load config
    if args.config:
        logger.info(f"Loading config from {args.config}")
        config = load_config(args.config)
    else:
        logger.info(f"Parsing query: {args.query}")
        config = parse_query(args.query)

    # Apply CLI overrides
    apply_overrides(config, args)

    # Dry run: just print the YAML
    if args.dry_run:
        print("# Autofare Configuration (parsed from query)")
        print("# Edit and re-run with: python -m autofare --config <file.yaml>")
        print()
        print(config_to_yaml(config))
        return 0

    # Run the optimization
    logger.info("Starting Autofare optimization...")
    session = run_autofare(config)

    # Print report
    report = format_report(session)
    print(report)

    # Save to file if requested
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        logger.info(f"Report saved to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
