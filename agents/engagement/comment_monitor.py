"""Comment Monitor agent — checks for new comments on Justin's posts."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from agents.base import BaseAgent, load_config
from tools import apify_client

logger = logging.getLogger(__name__)


class CommentMonitor(BaseAgent):
    def __init__(self):
        super().__init__("comment_monitor", prompt_file=None)
        self.business = load_config("business.yaml")
        self.profile_url = self.business.get("linkedin", "")

    def _load_replied_ids(self) -> set:
        """Load IDs of comments we've already replied to."""
        data = self.load_latest("engagement/replies")
        if not data:
            return set()
        if isinstance(data, list):
            return {r.get("comment_id") for r in data if r.get("comment_id")}
        return {r.get("comment_id") for r in data.get("replies", []) if r.get("comment_id")}

    def run(self) -> list[dict]:
        """Check for new comments on Justin's recent posts."""
        logger.info("[comment_monitor] checking for new comments")

        try:
            comments = apify_client.scrape_own_post_comments(self.profile_url)
        except Exception as e:
            logger.error(f"[comment_monitor] scrape failed: {e}")
            return []

        # Filter out already-replied comments
        replied_ids = self._load_replied_ids()
        new_comments = []
        for c in comments:
            cid = c.get("commentId", c.get("id", ""))
            if cid and cid not in replied_ids:
                new_comments.append({
                    "comment_id": cid,
                    "commenter_name": c.get("authorName", c.get("name", "Unknown")),
                    "commenter_url": c.get("authorProfileUrl", c.get("profileUrl", "")),
                    "comment_text": c.get("text", c.get("comment", "")),
                    "post_url": c.get("source_post_url", ""),
                    "timestamp": c.get("timestamp", datetime.now().isoformat()),
                })

        self.save_output(
            {"date": self.today_str(), "new_comments": new_comments},
            "engagement/incoming",
            f"{self.today_str()}_{datetime.now().strftime('%H%M')}_comments.json",
        )

        logger.info(f"[comment_monitor] found {len(new_comments)} new comments")
        return new_comments
