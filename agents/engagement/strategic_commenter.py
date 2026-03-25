"""Strategic Commenter agent — comments on influencer posts to build visibility."""

from __future__ import annotations

import os
import json
import logging

from agents.base import BaseAgent
from tools import phantombuster_client

logger = logging.getLogger(__name__)


class StrategicCommenter(BaseAgent):
    def __init__(self):
        super().__init__("strategic_commenter")
        self.comment_phantom_id = os.environ.get("PB_COMMENT_PHANTOM_ID", "")

    def _get_todays_targets(self) -> list[dict]:
        """Get influencer posts to comment on today."""
        # Load latest influencer scrape data
        scraped = self.load_latest("influencers/content")
        if not scraped:
            return []

        targets = []
        for inf in scraped if isinstance(scraped, list) else []:
            for post in inf.get("posts", [])[:2]:  # Top 2 posts per influencer
                post_url = post.get("postUrl", post.get("url", ""))
                if post_url:
                    targets.append({
                        "influencer": inf["name"],
                        "post_url": post_url,
                        "post_text": post.get("text", "")[:300],
                        "likes": post.get("likesCount", post.get("likes", 0)),
                    })

        # Sort by engagement, take top 10
        targets.sort(key=lambda x: x.get("likes", 0), reverse=True)
        return targets[:10]

    def _load_recent_comments(self) -> set:
        """Load URLs we've already commented on recently."""
        data = self.load_latest("engagement/outbound")
        if not data:
            return set()
        return {c.get("post_url") for c in data.get("comments", []) if c.get("post_url")}

    def run(self) -> dict:
        """Generate and post strategic comments on influencer posts."""
        targets = self._get_todays_targets()
        if not targets:
            logger.info("[strategic_commenter] no targets found")
            return {"comments": []}

        # Filter out already-commented posts
        recent = self._load_recent_comments()
        targets = [t for t in targets if t["post_url"] not in recent][:5]

        logger.info(f"[strategic_commenter] generating comments for {len(targets)} posts")

        # Generate comments
        prompt = (
            f"Generate strategic comments for these influencer posts. "
            f"Each comment should position Justin Bellware as an AI/team training expert.\n\n"
            f"## Posts to Comment On\n```json\n{json.dumps(targets, indent=2)}\n```\n\n"
            f"## Context\n"
            f"- Justin runs TenXVA / Using AI to Scale\n"
            f"- Expert in AI-powered team training for remote staff\n"
            f"- NEVER pitch. Add genuine value as a peer.\n\n"
            f"Return a JSON array of comment objects."
        )

        comments = self.call_json(prompt)

        # Post comments
        posted = []
        for comment in comments:
            post_url = comment.get("post_url", "")
            comment_text = comment.get("comment", "")
            if not post_url or not comment_text:
                continue

            if not self.comment_phantom_id:
                logger.info(f"[strategic_commenter] dry run: {comment_text[:50]}...")
                comment["status"] = "dry_run"
                posted.append(comment)
                continue

            try:
                result = phantombuster_client.post_comment(
                    self.comment_phantom_id, post_url, comment_text
                )
                comment["status"] = "posted"
                comment["result"] = result
                posted.append(comment)
            except Exception as e:
                logger.warning(f"[strategic_commenter] failed: {e}")
                comment["status"] = "error"
                posted.append(comment)

        output = {"date": self.today_str(), "comments": posted, "total": len(posted)}
        self.save_output(output, "engagement/outbound", f"{self.today_str()}_comments.json")
        logger.info(f"[strategic_commenter] posted {len(posted)} comments")
        return output
