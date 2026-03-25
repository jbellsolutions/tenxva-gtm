"""Engagement Team orchestrator — monitors comments, drafts replies, posts strategically."""

import logging
from datetime import datetime

from agents.engagement.comment_monitor import CommentMonitor
from agents.engagement.reply_composer import ReplyComposer
from agents.engagement.reply_poster import ReplyPoster
from agents.engagement.strategic_commenter import StrategicCommenter

logger = logging.getLogger(__name__)


def run_engagement_loop():
    """Monitor for new comments and reply.

    Runs every 2 hours, 7 AM - 9 PM ET.
    """
    start = datetime.now()
    logger.info(f"[engagement_team] starting engagement loop at {start.isoformat()}")

    try:
        # Step 1: Check for new comments
        monitor = CommentMonitor()
        new_comments = monitor.run()

        if not new_comments:
            logger.info("[engagement_team] no new comments to reply to")
            return {"status": "success", "new_comments": 0, "replies_posted": 0}

        # Step 2: Draft replies
        composer = ReplyComposer()
        replies = composer.run(new_comments)

        # Step 3: Post replies
        poster = ReplyPoster()
        result = poster.run(replies)

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"[engagement_team] engagement loop complete in {elapsed:.1f}s")

        return {
            "status": "success",
            "new_comments": len(new_comments),
            "replies_drafted": len(replies),
            "replies_posted": result.get("posted", 0),
            "elapsed_seconds": elapsed,
        }

    except Exception as e:
        logger.error(f"[engagement_team] engagement loop failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def run_strategic_commenting():
    """Post strategic comments on influencer posts.

    Runs daily at 10:00 AM and 4:00 PM ET.
    """
    start = datetime.now()
    logger.info(f"[engagement_team] starting strategic commenting at {start.isoformat()}")

    try:
        commenter = StrategicCommenter()
        result = commenter.run()

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"[engagement_team] strategic commenting complete in {elapsed:.1f}s")

        return {
            "status": "success",
            "comments_posted": result.get("total", 0),
            "elapsed_seconds": elapsed,
        }

    except Exception as e:
        logger.error(f"[engagement_team] strategic commenting failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
