"""
Outreach Team — orchestrates the full LinkedIn engagement machine.

This is the master orchestrator that ties together:
1. Engagement Monitor (detect new likes/comments on our posts)
2. Smart Replier (quality-checked replies to comments)
3. Contact Enricher (profile view + data enrichment → AirTable)
4. Peekaboo Sequencer (7-day LinkedIn engagement sequence)
5. Connection Manager (top 5/day connection requests)
6. Email Outreach (7-day trigger for non-converters)
7. Recurring Engager (Tue/Fri engagement with database)

Scheduler entry points:
- run_engagement_cycle()       — every 2 hours (monitor + reply + enrich + start sequences)
- run_peekaboo_sequences()     — daily 8 AM (process active 7-day sequences)
- run_daily_connections()      — daily 11 AM (top 5 connection requests)
- run_email_triggers()         — daily 9 AM (fire emails for 7-day-old non-responders)
- run_recurring_engagement()   — Tue + Fri 1 PM (like + comment on engager posts)
"""

import logging
from datetime import datetime, timezone

from agents.engagement.engagement_monitor import EngagementMonitor
from agents.engagement.smart_replier import SmartReplier
from agents.engagement.contact_enricher import ContactEnricher
from agents.engagement.peekaboo_sequencer import PeekabooSequencer
from agents.engagement.connection_manager import ConnectionManager
from agents.engagement.email_outreach import EmailOutreach
from agents.engagement.recurring_engager import RecurringEngager
from tools.unipile_client import UnipileClient
from tools.airtable_client import AirtableClient

logger = logging.getLogger(__name__)


def run_engagement_cycle():
    """
    Main engagement cycle — runs every 2 hours.
    1. Scan our posts for new likes/comments
    2. Reply to new comments (quality-checked)
    3. View profiles + enrich contacts → AirTable
    4. Start peekaboo sequences for new engagers
    """
    logger.info("=" * 60)
    logger.info("ENGAGEMENT CYCLE STARTED")
    logger.info("=" * 60)

    start = datetime.now(timezone.utc)
    unipile = UnipileClient()
    airtable = AirtableClient()
    airtable.ensure_base_exists()

    # Step 1: Monitor for new engagement
    logger.info("Step 1: Scanning posts for engagement...")
    monitor = EngagementMonitor()
    scan_result = monitor.scan(lookback_posts=10)
    new_likers = scan_result.get("new_likers", [])
    new_commenters = scan_result.get("new_commenters", [])
    logger.info(f"Found {len(new_likers)} new likers, {len(new_commenters)} new commenters")

    # Step 2: Reply to comments
    replies_posted = 0
    if new_commenters:
        logger.info("Step 2: Drafting replies to comments...")
        replier = SmartReplier()
        for commenter in new_commenters:
            reply_result = replier.draft_reply(commenter)
            if reply_result.get("approved") and reply_result.get("reply_text"):
                # Post the reply via Unipile
                post_id = commenter.get("post_id", "")
                comment_id = commenter.get("comment_id", "")
                if post_id and comment_id:
                    unipile.reply_to_comment(post_id, comment_id, reply_result["reply_text"])
                    replies_posted += 1
                    logger.info(f"Replied to {commenter.get('name', 'unknown')}")
    else:
        logger.info("Step 2: No new comments to reply to")

    # Step 3: Enrich all new engagers (likers + commenters)
    logger.info("Step 3: Enriching new engager profiles...")
    enricher = ContactEnricher()
    all_new = new_likers + new_commenters
    enriched = enricher.enrich_batch(all_new) if all_new else []
    logger.info(f"Enriched {len(enriched)} profiles")

    # Step 4: Start peekaboo sequences for new engagers
    logger.info("Step 4: Starting peekaboo sequences...")
    sequencer = PeekabooSequencer()
    sequences_started = 0
    for engager in enriched:
        if engager.get("linkedin_url"):
            if sequencer.start_sequence(engager):
                sequences_started += 1

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()

    result = {
        "status": "success",
        "timestamp": start.isoformat(),
        "posts_scanned": scan_result.get("posts_scanned", 0),
        "new_likers": len(new_likers),
        "new_commenters": len(new_commenters),
        "replies_posted": replies_posted,
        "profiles_enriched": len(enriched),
        "sequences_started": sequences_started,
        "elapsed_seconds": round(elapsed, 1),
    }

    logger.info(f"ENGAGEMENT CYCLE COMPLETE: {result}")
    return result


def run_peekaboo_sequences():
    """
    Process active 7-day LinkedIn peekaboo sequences.
    Runs daily at 8 AM.
    """
    logger.info("=" * 60)
    logger.info("PEEKABOO SEQUENCES STARTED")
    logger.info("=" * 60)

    sequencer = PeekabooSequencer()
    result = sequencer.process_active_sequences()
    logger.info(f"PEEKABOO COMPLETE: {result}")
    return result


def run_daily_connections():
    """
    Send top 5 connection requests per day.
    Runs daily at 11 AM.
    """
    logger.info("=" * 60)
    logger.info("DAILY CONNECTIONS STARTED")
    logger.info("=" * 60)

    manager = ConnectionManager()
    result = manager.send_daily_connections()
    logger.info(f"CONNECTIONS COMPLETE: {result}")
    return result


def run_email_triggers():
    """
    Check for engagers who completed LinkedIn sequence and send emails.
    Runs daily at 9 AM.
    """
    logger.info("=" * 60)
    logger.info("EMAIL TRIGGERS STARTED")
    logger.info("=" * 60)

    outreach = EmailOutreach()
    result = outreach.process_email_triggers()
    logger.info(f"EMAIL TRIGGERS COMPLETE: {result}")
    return result


def run_recurring_engagement():
    """
    Engage with people in our database — like + comment on their recent posts.
    Runs Tuesday + Friday at 1 PM.
    """
    logger.info("=" * 60)
    logger.info("RECURRING ENGAGEMENT STARTED")
    logger.info("=" * 60)

    engager = RecurringEngager()
    result = engager.run_engagement_pass()
    logger.info(f"RECURRING ENGAGEMENT COMPLETE: {result}")
    return result
