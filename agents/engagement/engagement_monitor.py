"""
Engagement Monitor — scans our LinkedIn posts for new likes, comments, and shares via Unipile.

Replaces the old Apify-based CommentMonitor for detecting engagement.
Runs every 2 hours. Returns list of new engagers with their engagement type.
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from tools.unipile_client import UnipileClient
from tools.airtable_client import AirtableClient

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
ENGAGEMENT_DIR = DATA_DIR / "engagement" / "monitor"


class EngagementMonitor:
    """
    Monitors our LinkedIn posts for new engagement (likes, comments, shares).
    Tracks seen engagers to avoid processing the same person twice per cycle.
    """

    def __init__(self):
        self.unipile = UnipileClient()
        self.airtable = AirtableClient()
        ENGAGEMENT_DIR.mkdir(parents=True, exist_ok=True)

    def scan(self, lookback_posts: int = 10) -> dict:
        """
        Scan recent posts for new engagement.
        Returns:
        {
            "posts_scanned": int,
            "new_likers": [...],
            "new_commenters": [...],
            "total_new_engagers": int,
        }
        """
        seen = self._load_seen()
        new_likers = []
        new_commenters = []

        # Get our recent posts
        posts = self.unipile.get_my_posts(limit=lookback_posts)
        if not posts:
            logger.info("No posts found to scan")
            return {"posts_scanned": 0, "new_likers": [], "new_commenters": [], "total_new_engagers": 0}

        for post in posts:
            post_id = post.get("id", "")
            post_url = post.get("url", "") or post.get("provider_id", "")

            # Get reactions (likers)
            reactions = self.unipile.get_post_reactions(post_id, limit=100)
            for reaction in reactions:
                user_id = reaction.get("user_id", "") or reaction.get("provider_id", "")
                if not user_id or user_id in seen:
                    continue
                seen.add(user_id)
                engager = {
                    "user_id": user_id,
                    "name": reaction.get("name", "") or f"{reaction.get('first_name', '')} {reaction.get('last_name', '')}".strip(),
                    "linkedin_url": reaction.get("public_identifier", "") or reaction.get("url", ""),
                    "reaction_type": reaction.get("type", "LIKE"),
                    "post_id": post_id,
                    "post_url": post_url,
                    "engagement_type": "like",
                }
                new_likers.append(engager)

            # Get comments
            comments = self.unipile.get_post_comments(post_id, limit=100)
            for comment in comments:
                user_id = comment.get("user_id", "") or comment.get("author", {}).get("provider_id", "")
                comment_id = comment.get("id", "")
                if not user_id or f"comment_{comment_id}" in seen:
                    continue
                seen.add(f"comment_{comment_id}")

                author = comment.get("author", {})
                engager = {
                    "user_id": user_id,
                    "name": author.get("name", "") or f"{author.get('first_name', '')} {author.get('last_name', '')}".strip(),
                    "linkedin_url": author.get("public_identifier", "") or author.get("url", ""),
                    "comment_id": comment_id,
                    "comment_text": comment.get("text", ""),
                    "post_id": post_id,
                    "post_url": post_url,
                    "engagement_type": "comment",
                }
                new_commenters.append(engager)

        # Save seen state
        self._save_seen(seen)

        # Save scan results
        result = {
            "posts_scanned": len(posts),
            "new_likers": new_likers,
            "new_commenters": new_commenters,
            "total_new_engagers": len(new_likers) + len(new_commenters),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        date_str = datetime.now().strftime("%Y-%m-%d")
        scan_file = ENGAGEMENT_DIR / f"{date_str}_scan.json"
        # Append to existing scans for today
        existing_scans = []
        if scan_file.exists():
            try:
                existing_scans = json.loads(scan_file.read_text())
            except Exception:
                existing_scans = []
        existing_scans.append(result)
        scan_file.write_text(json.dumps(existing_scans, indent=2))

        logger.info(f"Engagement scan: {len(posts)} posts, {len(new_likers)} new likers, {len(new_commenters)} new commenters")
        return result

    def _load_seen(self) -> set:
        """Load set of already-processed engager IDs."""
        seen_file = ENGAGEMENT_DIR / "seen_engagers.json"
        if seen_file.exists():
            try:
                data = json.loads(seen_file.read_text())
                # Prune entries older than 30 days
                cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                return set(k for k, v in data.items() if v > cutoff)
            except Exception:
                return set()
        return set()

    def _save_seen(self, seen: set):
        """Save seen engager IDs with timestamp."""
        seen_file = ENGAGEMENT_DIR / "seen_engagers.json"
        now = datetime.now(timezone.utc).isoformat()
        # Load existing to preserve timestamps
        existing = {}
        if seen_file.exists():
            try:
                existing = json.loads(seen_file.read_text())
            except Exception:
                pass
        for item in seen:
            if item not in existing:
                existing[item] = now
        seen_file.write_text(json.dumps(existing, indent=2))
