"""
Smart Replier — generates intelligent, quality-checked replies to comments on our posts.

Uses Claude to draft the reply, then runs it through the 3-agent quality gate
(Fact Check → Authority → Human Touch) before returning the approved text.
"""

import logging
from agents.base import BaseAgent
from agents.quality.quality_gate import QualityGate

logger = logging.getLogger(__name__)


class SmartReplier(BaseAgent):
    """
    Generates quality-checked replies to comments on our LinkedIn posts.
    Every reply goes through the 3-agent quality gate before posting.
    """

    def __init__(self):
        super().__init__(name="smart_replier", prompt_file="reply_composer.md")
        self.quality_gate = QualityGate()

    def draft_reply(self, comment: dict, post_context: str = "") -> dict:
        """
        Generate a quality-checked reply to a comment.

        Args:
            comment: {
                "name": str,
                "comment_text": str,
                "linkedin_url": str,
                "post_url": str,
            }
            post_context: the text of our original post (for context)

        Returns:
            {
                "reply_text": str,      # quality-checked text to post
                "quality_result": dict, # full quality gate output
                "approved": bool,       # whether it passed quality gate
                "commenter": dict,      # original comment data
            }
        """
        commenter_name = comment.get("name", "someone")
        comment_text = comment.get("comment_text", "")

        prompt = f"""Someone commented on our LinkedIn post. Draft a reply.

COMMENTER: {commenter_name}
THEIR COMMENT: "{comment_text}"

OUR POST CONTEXT: {post_context[:500] if post_context else "(not available)"}

Rules:
- Make them feel SEEN and VALUED
- 1-3 sentences max
- Add genuine value — a new angle, specific detail, or thoughtful follow-up question
- NEVER pitch services, mention TenXVA, or self-promote
- Match their energy — if they're enthusiastic, match it; if they're thoughtful, be thoughtful
- Reference something SPECIFIC from their comment
- Use natural contractions (I'm, we've, that's)
- Be warm but genuine — not sycophantic

Return JSON with: reply_text, reply_type (supportive/question/experience/disagreement/tag/interest/thoughtful), reasoning."""

        # Draft the reply
        draft = self.call_json(prompt, temperature=0.7)
        if not draft or not draft.get("reply_text"):
            logger.warning(f"Failed to draft reply to {commenter_name}")
            return {
                "reply_text": None,
                "quality_result": None,
                "approved": False,
                "commenter": comment,
            }

        reply_text = draft["reply_text"]

        # Run through quality gate
        quality_result = self.quality_gate.check(reply_text, content_type="reply")

        approved = quality_result.get("verdict") in ("PASS", "FLAG")
        final_text = quality_result.get("final_text", reply_text)

        if not approved:
            logger.warning(f"Reply to {commenter_name} REJECTED by quality gate: {quality_result.get('reason', 'unknown')}")

        return {
            "reply_text": final_text if approved else None,
            "quality_result": quality_result,
            "approved": approved,
            "commenter": comment,
        }

    def draft_batch_replies(self, comments: list, post_context: str = "") -> list:
        """
        Draft quality-checked replies for a batch of comments.
        Returns list of reply dicts (same format as draft_reply).
        """
        results = []
        for comment in comments:
            result = self.draft_reply(comment, post_context)
            results.append(result)
        return results
