"""APScheduler configuration — defines all recurring jobs for the GTM system."""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from teams.content_team import run_content_production
from teams.influencer_team import run_influencer_scrape, run_lead_extraction
from teams.engagement_team import run_engagement_loop, run_strategic_commenting
from teams.profile_team import run_monthly_audit
from tools.auto_poster import run_auto_poster

logger = logging.getLogger(__name__)


def create_scheduler() -> BlockingScheduler:
    """Create and configure the APScheduler with all jobs."""
    scheduler = BlockingScheduler(timezone="America/New_York")

    # ── Team 1: Content Production ──────────────────────────────
    # Daily at 5:30 AM ET
    scheduler.add_job(
        run_content_production,
        CronTrigger(hour=5, minute=30, timezone="America/New_York"),
        id="content_production",
        name="Daily Content Production",
        misfire_grace_time=3600,
    )

    # ── Team 2: Influencer Intelligence ─────────────────────────
    # Scrape + Analyze: Daily at 6:00 AM ET
    scheduler.add_job(
        run_influencer_scrape,
        CronTrigger(hour=6, minute=0, timezone="America/New_York"),
        id="influencer_scrape",
        name="Influencer Scrape + Analysis",
        misfire_grace_time=3600,
    )

    # Lead Extraction: Daily at 2:00 PM ET
    scheduler.add_job(
        run_lead_extraction,
        CronTrigger(hour=14, minute=0, timezone="America/New_York"),
        id="lead_extraction",
        name="Lead Extraction",
        misfire_grace_time=3600,
    )

    # ── Team 3: Engagement ──────────────────────────────────────
    # Comment monitoring + reply: Every 2 hours, 7 AM - 9 PM ET
    scheduler.add_job(
        run_engagement_loop,
        CronTrigger(hour="7,9,11,13,15,17,19,21", minute=0, timezone="America/New_York"),
        id="engagement_loop",
        name="Engagement Loop (Monitor + Reply)",
        misfire_grace_time=1800,
    )

    # Strategic commenting: 10:00 AM and 4:00 PM ET
    scheduler.add_job(
        run_strategic_commenting,
        CronTrigger(hour="10,16", minute=0, timezone="America/New_York"),
        id="strategic_commenting",
        name="Strategic Commenting",
        misfire_grace_time=3600,
    )

    # ── Auto-Poster (checks queue every 15 min) ────────────────
    # Runs 7 AM - 10 PM ET, every 15 minutes
    scheduler.add_job(
        run_auto_poster,
        CronTrigger(hour="7-22", minute="*/15", timezone="America/New_York"),
        id="auto_poster",
        name="Auto-Poster (Queue → LinkedIn)",
        misfire_grace_time=900,
    )

    # ── Team 4: Profile Optimization ────────────────────────────
    # Monthly audit: 1st of month at 9:00 AM ET
    scheduler.add_job(
        run_monthly_audit,
        CronTrigger(day=1, hour=9, minute=0, timezone="America/New_York"),
        id="monthly_audit",
        name="Monthly Profile Audit",
        misfire_grace_time=86400,
    )

    # Log all scheduled jobs
    jobs = scheduler.get_jobs()
    logger.info(f"Scheduler configured with {len(jobs)} jobs:")
    for job in jobs:
        logger.info(f"  - {job.name} ({job.id}): {job.trigger}")

    return scheduler
