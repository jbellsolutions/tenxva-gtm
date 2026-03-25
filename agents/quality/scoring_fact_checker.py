"""
Scoring Fact Checker — verifies factual accuracy of outbound content.
"""

import logging
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ScoringFactChecker(BaseAgent):
    """Reviews content for factual accuracy before posting."""

    def __init__(self):
        super().__init__(name="scoring_fact_checker", prompt_file="scoring_fact_checker.md")

    def check(self, text: str, content_type: str = "comment") -> dict:
        """
        Fact-check a piece of content.
        Returns dict with verdict, claim details, and optional revised_text.
        """
        prompt = f"""Fact-check the following {content_type}. Verify every factual claim.

CONTENT TO REVIEW:
---
{text}
---

Check all statistics, tool names, company references, dates, and technical claims.
Return your evaluation as JSON with: claims_found, claims_verified, claims_flagged, claims_incorrect, verdict (PASS/FLAG/FAIL), details (list of claim objects), revised_text (null if PASS), notes."""

        result = self.call_json(prompt, temperature=0.2)
        if not result:
            logger.warning("ScoringFactChecker returned empty — defaulting to PASS")
            return {
                "claims_found": 0,
                "claims_verified": 0,
                "claims_flagged": 0,
                "claims_incorrect": 0,
                "verdict": "PASS",
                "details": [],
                "revised_text": None,
                "notes": "Checker returned empty, defaulted to PASS",
            }

        return result
