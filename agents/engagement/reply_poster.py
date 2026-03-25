"""Reply Poster agent — posts approved replies via PhantomBuster."""

from __future__ import annotations

import os
import logging
from datetime import datetime

from agents.base import BaseAgent
from tools import phantombuster_client

logger = logging.getLogger(__name__)


class ReplyPoster(BaseAgent):
    def __init__(self):
        super().__init__("reply_poster", prompt_file=None)
        self.reply_phantom_id = os.environ.get("PB_REPLY_PHANTOM_ID", "")

    def run(self, replies: list[dict]) -> dict:
        """Post replies to LinkedIn comments."""
        if not replies:
            return {"posted": 0}

        logger.info(f"[reply_poster] posting {len(replies)} replies")
        posted = []

        for reply in replies:
            comment_id = reply.get("comment_id", "")
            reply_text = reply.get("reply", "")
            if not reply_text:
                continue

            if not self.reply_phantom_id:
                logger.info(f"[reply_poster] dry run: would reply to {comment_id}")
                posted.append({"comment_id": comment_id, "status": "dry_run"})
                continue

            try:
                # Use comment URL if available, otherwise skip
                comment_url = reply.get("comment_url", "")
                if comment_url:
                    result = phantombuster_client.reply_to_comment(
                        self.reply_phantom_id, comment_url, reply_text
                    )
                    posted.append({"comment_id": comment_id, "status": "posted", "result": result})
                else:
                    posted.append({"comment_id": comment_id, "status": "skipped", "reason": "no URL"})
            except Exception as e:
                logger.warning(f"[reply_poster] failed to post reply: {e}")
                posted.append({"comment_id": comment_id, "status": "error", "error": str(e)})

        output = {"date": self.today_str(), "posted": len(posted), "results": posted}
        self.save_output(output, "engagement/replies", f"{self.today_str()}_posted.json")
        logger.info(f"[reply_poster] posted {len(posted)} replies")
        return output
