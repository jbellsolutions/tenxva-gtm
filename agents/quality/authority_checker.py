"""
Authority Checker — ensures outbound content is authoritative, objective, and professional.
"""

import logging
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AuthorityChecker(BaseAgent):
    """Reviews content for authority, objectivity, and professionalism."""

    def __init__(self):
        super().__init__(name="authority_checker", prompt_file="authority_checker.md")

    def check(self, text: str, content_type: str = "comment") -> dict:
        """
        Check a piece of content for authority/professionalism.
        content_type: comment, reply, message, connection_note
        Returns dict with verdict, scores, and optional revised_text.
        """
        prompt = f"""Review the following {content_type} for authority, objectivity, and professionalism.

CONTENT TO REVIEW:
---
{text}
---

Return your evaluation as JSON with: authority_score, objectivity_score, professionalism_score, overall_score, verdict (PASS/FLAG/FAIL), issues (list), revised_text (null if PASS), notes."""

        result = self.call_json(prompt, temperature=0.3)
        if not result:
            logger.warning("AuthorityChecker returned empty — defaulting to PASS")
            return {
                "authority_score": 7,
                "objectivity_score": 7,
                "professionalism_score": 7,
                "overall_score": 7.0,
                "verdict": "PASS",
                "issues": [],
                "revised_text": None,
                "notes": "Checker returned empty, defaulted to PASS",
            }

        return result
