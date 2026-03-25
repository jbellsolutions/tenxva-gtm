"""
Recurring Engager — checks our database of engagers for recent posts
and leaves intelligent likes + comments.

Runs: Tuesday + Friday (twice a week)
For each engager in our database:
  1. Check their profile for recent posts (last 3 days)
  2. Like their most recent post
  3. Leave an intelligent, relevant, authoritative comment
"""

import logging
from datetime import datetime, timezone

from agents.base import BaseAgent
from agents.quality.quality_gate import QualityGate
from tools.unipile_client import UnipileClient
from tools.airtable_client import AirtableClient

logger = logging.getLogger(__name__)

# Max engagers to process per run (avoid rate limits)
MAX_PER_RUN = 25


class RecurringEngager(BaseAgent):
    """
    Periodic engagement with people in our database.
    Checks their profiles for new posts, likes and comments.
    """

    def __init__(self):
        super().__init__(name="recurring_engager", prompt_file="strategic_commenter.md")
        self.unipile = UnipileClient()
        self.airtable = AirtableClient()
        self.quality_gate = QualityGate()

    def run_engagement_pass(self) -> dict:
        """
        Process engagers from our database.
        Returns summary of actions taken.
        """
        engagers = self.airtable.get_engagers_for_recurring()
        if not engagers:
            logger.info("No engagers in database for recurring engagement")
            return {"processed": 0, "liked": 0, "commented": 0}

        # Limit to MAX_PER_RUN
        batch = engagers[:MAX_PER_RUN]
        liked = 0
        commented = 0

        for record in batch:
            fields = record.get("fields", {})
            linkedin_url = fields.get("LinkedIn URL", "")
            name = fields.get("Name", "Unknown")

            if not linkedin_url:
                continue

            try:
                # Get their recent posts
                posts = self.unipile.get_user_posts(linkedin_url, limit=3)
                if not posts:
                    continue

                target_post = posts[0]
                post_id = target_post.get("id", "")
                post_text = target_post.get("text", "") or target_post.get("body", "")

                if not post_id:
                    continue

                # Like the post
                self.unipile.react_to_post(post_id, "LIKE")
                liked += 1

                # Generate and post a comment (not on every post — roughly 60% get comments)
                import random
                if random.random() < 0.6 and post_text:
                    comment = self._generate_comment(name, post_text)
                    if comment:
                        # Quality gate
                        qr = self.quality_gate.check(comment, content_type="comment")
                        if qr.get("verdict") != "FAIL":
                            final = qr.get("final_text", comment)
                            self.unipile.comment_on_post(post_id, final)
                            commented += 1

                            self.airtable.log_engagement(
                                linkedin_url=linkedin_url,
                                action="recurring_comment",
                                post_url=target_post.get("url", ""),
                                details=f"Comment: {final[:100]}",
                            )

                # Log the like
                self.airtable.log_engagement(
                    linkedin_url=linkedin_url,
                    action="recurring_like",
                    post_url=target_post.get("url", ""),
                )

            except Exception as e:
                logger.error(f"Recurring engagement failed for {name}: {e}")

        logger.info(f"Recurring engagement: {len(batch)} processed, {liked} liked, {commented} commented")
        return {
            "processed": len(batch),
            "liked": liked,
            "commented": commented,
        }

    def _generate_comment(self, name: str, post_text: str) -> str:
        """Generate an intelligent comment on someone's post."""
        prompt = f"""Write a brief, intelligent comment on this LinkedIn post by {name}.

THEIR POST:
---
{post_text[:800]}
---

Rules:
- 1-3 sentences max
- Add genuine value — a new angle, specific experience, or thoughtful question
- NEVER mention TenXVA, services, or anything promotional
- Reference something SPECIFIC from their post
- Use natural contractions (I'm, we've, that's)
- Sound like a knowledgeable peer, not a fan or a salesperson
- Pass the Invisible Test: would this make Justin look smart knowing nothing about his business?

Return JSON with: comment_text, formula_used."""

        result = self.call_json(prompt, temperature=0.7)
        if result and result.get("comment_text"):
            return result["comment_text"]
        return ""
