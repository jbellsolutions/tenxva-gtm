"""
Quality Gate — orchestrates all three quality checkers on outbound content.

Flow: Content → Fact Check → Authority Check → Human Touch → PASS/REVISE/REJECT
"""

import logging
from agents.quality.authority_checker import AuthorityChecker
from agents.quality.human_touch_checker import HumanTouchChecker
from agents.quality.scoring_fact_checker import ScoringFactChecker

logger = logging.getLogger(__name__)


class QualityGate:
    """
    Three-agent quality gate for all outbound engagement content.
    Runs fact checker → authority checker → human touch checker.
    If any agent flags content, uses the revised text for the next check.
    """

    def __init__(self):
        self.fact_checker = ScoringFactChecker()
        self.authority_checker = AuthorityChecker()
        self.human_touch_checker = HumanTouchChecker()

    def check(self, text: str, content_type: str = "comment", max_revisions: int = 2) -> dict:
        """
        Run content through all three quality gates.
        Returns:
        {
            "verdict": "PASS" | "FLAG" | "FAIL",
            "final_text": str,         # the text to post (original or revised)
            "original_text": str,       # what was submitted
            "revisions": int,           # how many revision rounds
            "fact_check": {...},        # full fact check result
            "authority_check": {...},   # full authority check result
            "human_touch_check": {...}, # full human touch result
        }
        """
        original_text = text
        current_text = text
        revisions = 0

        for attempt in range(max_revisions + 1):
            # Stage 1: Fact Check
            fact_result = self.fact_checker.check(current_text, content_type)
            if fact_result.get("verdict") == "FAIL":
                if fact_result.get("revised_text"):
                    current_text = fact_result["revised_text"]
                    revisions += 1
                    logger.info(f"Fact checker revised content (attempt {attempt + 1})")
                    continue
                else:
                    return self._build_result(
                        "FAIL", current_text, original_text, revisions,
                        fact_result, {}, {},
                        reason="Fact check failed with no revision available"
                    )
            elif fact_result.get("verdict") == "FLAG" and fact_result.get("revised_text"):
                current_text = fact_result["revised_text"]
                revisions += 1

            # Stage 2: Authority Check
            auth_result = self.authority_checker.check(current_text, content_type)
            if auth_result.get("verdict") == "FAIL":
                if auth_result.get("revised_text"):
                    current_text = auth_result["revised_text"]
                    revisions += 1
                    logger.info(f"Authority checker revised content (attempt {attempt + 1})")
                    continue
                else:
                    return self._build_result(
                        "FAIL", current_text, original_text, revisions,
                        fact_result, auth_result, {},
                        reason="Authority check failed with no revision available"
                    )
            elif auth_result.get("verdict") == "FLAG" and auth_result.get("revised_text"):
                current_text = auth_result["revised_text"]
                revisions += 1

            # Stage 3: Human Touch Check
            human_result = self.human_touch_checker.check(current_text, content_type)
            if human_result.get("verdict") == "FAIL":
                if human_result.get("revised_text"):
                    current_text = human_result["revised_text"]
                    revisions += 1
                    logger.info(f"Human touch checker revised content (attempt {attempt + 1})")
                    continue
                else:
                    return self._build_result(
                        "FAIL", current_text, original_text, revisions,
                        fact_result, auth_result, human_result,
                        reason="Human touch check failed with no revision available"
                    )
            elif human_result.get("verdict") == "FLAG" and human_result.get("revised_text"):
                current_text = human_result["revised_text"]
                revisions += 1

            # All passed
            return self._build_result(
                "PASS", current_text, original_text, revisions,
                fact_result, auth_result, human_result
            )

        # Exhausted revision attempts
        logger.warning(f"Quality gate exhausted {max_revisions} revision attempts")
        return self._build_result(
            "FLAG", current_text, original_text, revisions,
            fact_result, auth_result, human_result,
            reason=f"Content revised {revisions} times but may still have issues"
        )

    def _build_result(self, verdict, final_text, original_text, revisions,
                       fact_check, authority_check, human_touch_check, reason=None):
        result = {
            "verdict": verdict,
            "final_text": final_text,
            "original_text": original_text,
            "revisions": revisions,
            "fact_check": fact_check,
            "authority_check": authority_check,
            "human_touch_check": human_touch_check,
        }
        if reason:
            result["reason"] = reason
        return result
