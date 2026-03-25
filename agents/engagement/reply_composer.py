"""Reply Composer agent — drafts personalized replies to comments."""

from __future__ import annotations

import json
import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ReplyComposer(BaseAgent):
    def __init__(self):
        super().__init__("reply_composer")

    def run(self, comments: list[dict]) -> list[dict]:
        """Draft replies for new comments."""
        if not comments:
            logger.info("[reply_composer] no comments to reply to")
            return []

        logger.info(f"[reply_composer] drafting replies for {len(comments)} comments")

        prompt = (
            f"Draft personalized replies to these comments on Justin Bellware's "
            f"LinkedIn posts. Follow your reply style guidelines.\n\n"
            f"## Comments\n```json\n{json.dumps(comments, indent=2)[:8000]}\n```\n\n"
            f"## Context\n"
            f"- Justin runs TenXVA / Using AI to Scale\n"
            f"- 30-Day AI VA Bootcamp for remote teams\n"
            f"- Never pitch directly. Be helpful and expert.\n\n"
            f"Return a JSON array of reply objects."
        )

        replies = self.call_json(prompt)

        self.save_output(
            {"date": self.today_str(), "replies": replies},
            "engagement/replies",
            f"{self.today_str()}_replies.json",
        )

        logger.info(f"[reply_composer] drafted {len(replies)} replies")
        return replies
