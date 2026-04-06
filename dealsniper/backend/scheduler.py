"""APScheduler setup for periodic flight scanning."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from db import SessionLocal, get_setting
from searcher import run_scan

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def scan_job():
    logger.info("Starting scheduled scan...")
    db = SessionLocal()
    try:
        result = run_scan(db)
        logger.info(
            f"Scan complete: {result['routes_scanned']} routes, "
            f"{result['observations_added']} observations, "
            f"{result['deals_found']} deals, {result['errors']} errors"
        )
    except Exception as e:
        logger.error(f"Scan job failed: {e}", exc_info=True)
    finally:
        db.close()


def start_scheduler():
    db = SessionLocal()
    try:
        hours = int(get_setting(db, "scan_interval_hours") or "6")
    finally:
        db.close()

    scheduler.add_job(
        scan_job,
        trigger=IntervalTrigger(hours=hours),
        id="flight_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started with {hours}h interval")


def reschedule(hours: int):
    try:
        scheduler.reschedule_job("flight_scan", trigger=IntervalTrigger(hours=hours))
        logger.info(f"Rescheduled scan to every {hours}h")
    except Exception:
        scheduler.add_job(
            scan_job,
            trigger=IntervalTrigger(hours=hours),
            id="flight_scan",
            replace_existing=True,
        )


def stop_scheduler():
    scheduler.shutdown(wait=False)
