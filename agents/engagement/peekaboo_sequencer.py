"""
Peekaboo Sequencer — 7-day LinkedIn engagement sequence for new engagers.

Day-by-day actions:
  Day 1: View profile (already done by enricher), like their most recent post
  Day 2: Find a post of theirs, leave an intelligent comment
  Day 3: Endorse them for a skill, like another post
  Day 4: View profile again, like a post
  Day 5: Leave another intelligent comment on a different post
  Day 6: Like a post, view profile
  Day 7: Final comment — aim for something memorable

After day 7: Mark as linkedin_complete → triggers email sequence after check.
"""

import logging
from datetime import datetime, timezone, timedelta

from agents.base import BaseAgent
from agents.quality.quality_gate import QualityGate
from tools.unipile_client import UnipileClient
from tools.airtable_client import AirtableClient

logger = logging.getLogger(__name__)


# Day → list of actions
SEQUENCE_PLAN = {
    1: [("view_profile", None), ("like_post", "most_recent")],
    2: [("comment_post", "find_relevant")],
    3: [("endorse_skill", None), ("like_post", "recent")],
    4: [("view_profile", None), ("like_post", "recent")],
    5: [("comment_post", "find_different")],
    6: [("like_post", "recent"), ("view_profile", None)],
    7: [("comment_post", "memorable")],
}


class PeekabooSequencer(BaseAgent):
    """
    Manages 7-day LinkedIn peekaboo sequences.
    Called daily to process all active sequences.
    """

    def __init__(self):
        super().__init__(name="peekaboo_sequencer", prompt_file="strategic_commenter.md")
        self.unipile = UnipileClient()
        self.airtable = AirtableClient()
        self.quality_gate = QualityGate()

    def process_active_sequences(self) -> dict:
        """
        Process all active LinkedIn peekaboo sequences.
        Returns summary of actions taken.
        """
        active = self.airtable.get_active_sequences("linkedin_active")
        if not active:
            logger.info("No active peekaboo sequences")
            return {"processed": 0, "actions_taken": 0, "completed": 0}

        total_actions = 0
        completed = 0

        for record in active:
            fields = record.get("fields", {})
            linkedin_url = fields.get("LinkedIn URL", "")
            name = fields.get("Name", "Unknown")
            current_day = fields.get("Sequence Day", 1) or 1

            if current_day > 7:
                # Sequence complete
                self.airtable.advance_sequence(linkedin_url)
                completed += 1
                logger.info(f"Sequence complete for {name}")
                continue

            # Get today's actions
            actions = SEQUENCE_PLAN.get(current_day, [])
            actions_done = 0

            for action_type, action_param in actions:
                try:
                    success = self._execute_action(
                        action_type, action_param, linkedin_url, name
                    )
                    if success:
                        actions_done += 1
                        self.airtable.log_engagement(
                            linkedin_url=linkedin_url,
                            action=f"peekaboo_day{current_day}_{action_type}",
                            details=f"Day {current_day}: {action_type}",
                        )
                except Exception as e:
                    logger.error(f"Peekaboo action failed for {name} day {current_day}: {e}")

            # Advance to next day
            new_day = self.airtable.advance_sequence(linkedin_url)
            total_actions += actions_done

            logger.info(f"Peekaboo day {current_day} for {name}: {actions_done}/{len(actions)} actions → now day {new_day}")

        return {
            "processed": len(active),
            "actions_taken": total_actions,
            "completed": completed,
        }

    def start_sequence(self, engager: dict) -> bool:
        """
        Start a new peekaboo sequence for an engager.
        Assumes they're already in AirTable.
        """
        linkedin_url = engager.get("linkedin_url", "")
        if not linkedin_url:
            return False

        success = self.airtable.start_sequence(linkedin_url)
        if success:
            logger.info(f"Started peekaboo sequence for {engager.get('name', 'unknown')}")
        return success

    def _execute_action(self, action_type: str, param: str, linkedin_url: str, name: str) -> bool:
        """Execute a single peekaboo action."""

        if action_type == "view_profile":
            profile = self.unipile.view_profile(linkedin_url)
            return bool(profile)

        elif action_type == "like_post":
            posts = self.unipile.get_user_posts(linkedin_url, limit=5)
            if not posts:
                logger.info(f"No posts found for {name}")
                return False
            # Pick a post to like (most recent or a different one)
            target = posts[0] if param == "most_recent" else (posts[1] if len(posts) > 1 else posts[0])
            post_id = target.get("id", "")
            if post_id:
                self.unipile.react_to_post(post_id, "LIKE")
                return True
            return False

        elif action_type == "comment_post":
            posts = self.unipile.get_user_posts(linkedin_url, limit=5)
            if not posts:
                return False

            # Pick a post to comment on
            target = posts[0]
            if param == "find_different" and len(posts) > 1:
                target = posts[1]

            post_text = target.get("text", "") or target.get("body", "")
            post_id = target.get("id", "")
            if not post_id:
                return False

            # Generate comment via Claude
            style = "memorable and thoughtful" if param == "memorable" else "intelligent and relevant"
            comment_text = self._generate_comment(name, post_text, style)
            if not comment_text:
                return False

            # Quality check
            qr = self.quality_gate.check(comment_text, content_type="comment")
            if qr.get("verdict") == "FAIL":
                logger.warning(f"Comment for {name} failed quality gate")
                return False

            final_text = qr.get("final_text", comment_text)
            self.unipile.comment_on_post(post_id, final_text)
            return True

        elif action_type == "endorse_skill":
            self.unipile.endorse_skill(linkedin_url)
            return True

        return False

    def _generate_comment(self, name: str, post_text: str, style: str) -> str:
        """Generate an intelligent comment on someone's post."""
        prompt = f"""Write a {style} comment on this LinkedIn post by {name}.

THEIR POST:
---
{post_text[:800]}
---

Rules:
- 1-3 sentences max
- Add genuine value — a new perspective, relevant experience, or thoughtful question
- NEVER mention TenXVA, our services, or pitch anything
- Reference something SPECIFIC from their post
- Use natural contractions
- Pass the "Invisible Test": would this make Justin look smart even if you knew nothing about his business?

Return JSON with: comment_text, formula_used (yes_and/data_drop/contrarian/question/story/tool_insight)."""

        result = self.call_json(prompt, temperature=0.7)
        if result and result.get("comment_text"):
            return result["comment_text"]
        return ""
