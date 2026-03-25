"""
Engagement Scheduler — adds engagement machine jobs to the existing APScheduler.

Import this from scheduler.py or main.py to add the engagement jobs.

Usage:
    from scheduler_engagement import add_engagement_jobs
    add_engagement_jobs(scheduler)
"""

import logging
from apscheduler.triggers.cron import CronTrigger

from teams.outreach_team import (
    run_engagement_cycle,
    run_peekaboo_sequences,
    run_daily_connections,
    run_email_triggers,
    run_recurring_engagement,
)
from tools.messaging_bot import run_messaging_cycle

logger = logging.getLogger(__name__)


def add_engagement_jobs(scheduler):
    """
    Add all engagement engine jobs to an existing APScheduler instance.
    Call this from your main scheduler setup.
    """

    # ─── Engagement Cycle (replaces old engagement_loop for Unipile) ───
    # Every 2 hours, 7 AM - 9 PM ET
    # Scans posts → replies to comments → enriches profiles → starts sequences
    scheduler.add_job(
        run_engagement_cycle,
        CronTrigger(hour="7,9,11,13,15,17,19,21", minute=15, timezone="America/New_York"),
        id="engagement_cycle",
        name="Engagement Cycle (monitor + reply + enrich + sequence)",
        misfire_grace_time=900,
        replace_existing=True,
    )

    # ─── Peekaboo Sequences — Daily 8 AM ──────────────────────────────
    # Processes all active 7-day LinkedIn sequences
    scheduler.add_job(
        run_peekaboo_sequences,
        CronTrigger(hour=8, minute=0, timezone="America/New_York"),
        id="peekaboo_sequences",
        name="7-Day Peekaboo Sequences",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # ─── Daily Connections — 11 AM ────────────────────────────────────
    # Sends top 5 connection requests per day
    scheduler.add_job(
        run_daily_connections,
        CronTrigger(hour=11, minute=0, timezone="America/New_York"),
        id="daily_connections",
        name="Daily Connection Requests (Top 5)",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # ─── Email Triggers — Daily 9 AM ─────────────────────────────────
    # Fires outreach emails for 7-day-old non-responders
    scheduler.add_job(
        run_email_triggers,
        CronTrigger(hour=9, minute=0, timezone="America/New_York"),
        id="email_triggers",
        name="Email Outreach Triggers",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # ─── Recurring Engagement — Tue + Fri 1 PM ───────────────────────
    # Checks engager DB for recent posts, likes + comments
    scheduler.add_job(
        run_recurring_engagement,
        CronTrigger(day_of_week="tue,fri", hour=13, minute=0, timezone="America/New_York"),
        id="recurring_engagement",
        name="Recurring Engagement (Tue/Fri)",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # ─── Messaging Bot — Every 30 min, 7 AM - 10 PM ────────────────
    # Checks for new connections with triggers, processes sequences
    scheduler.add_job(
        run_messaging_cycle,
        CronTrigger(hour="7-22", minute="*/30", timezone="America/New_York"),
        id="messaging_bot",
        name="Messaging Bot (triggers + sequences)",
        misfire_grace_time=600,
        replace_existing=True,
    )

    logger.info("Engagement engine jobs added to scheduler:")
    logger.info("  • Engagement Cycle: every 2hrs, 7:15AM-9:15PM ET")
    logger.info("  • Peekaboo Sequences: daily 8:00AM ET")
    logger.info("  • Email Triggers: daily 9:00AM ET")
    logger.info("  • Daily Connections: daily 11:00AM ET")
    logger.info("  • Recurring Engagement: Tue+Fri 1:00PM ET")
    logger.info("  • Messaging Bot: every 30min, 7AM-10PM ET")
