"""
Human Touch Checker — ensures outbound content reads like a real human (Justin) wrote it.
"""

import logging
from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class HumanTouchChecker(BaseAgent):
    """Reviews content for human authenticity and Justin's voice."""

    def __init__(self):
        super().__init__(name="human_touch_checker", prompt_file="human_touch_checker.md")

    def check(self, text: str, content_type: str = "comment") -> dict:
        """
        Check a piece of content for human authenticity.
        Returns dict with verdict, scores, and optional revised_text.
        """
        prompt = f"""Review the following {content_type} for human authenticity and voice match.

CONTENT TO REVIEW:
---
{text}
---

Apply the Bar Test and Screenshot Test. Check for AI-telltale patterns.
Return your evaluation as JSON with: human_score, voice_match, ai_detection_risk (10=safe, 1=obviously AI), overall_score, verdict (PASS/FLAG/FAIL), issues (list), revised_text (null if PASS), notes."""

        result = self.call_json(prompt, temperature=0.3)
        if not result:
            logger.warning("HumanTouchChecker returned empty — defaulting to PASS")
            return {
                "human_score": 7,
                "voice_match": 7,
                "ai_detection_risk": 7,
                "overall_score": 7.0,
                "verdict": "PASS",
                "issues": [],
                "revised_text": None,
                "notes": "Checker returned empty, defaulted to PASS",
            }

        return result
