"""Fact Checker agent — verifies claims, statistics, and factual assertions in approved content.

Runs AFTER quality review, BEFORE queuing. Protects credibility by catching:
- Wrong statistics or unsourced claims
- Misspelled company/product names
- Incorrect tool capabilities
- Wrong attributions

Verdicts: PASS (publish), FLAG (publish with corrections), FAIL (reject)
"""

from __future__ import annotations

import json
import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class FactChecker(BaseAgent):
    """Fact-checks approved content before it enters the posting queue."""

    max_tokens = 8192

    def __init__(self):
        super().__init__("fact_checker")

    def _build_prompt(self, content_items: list[dict]) -> str:
        """Build the fact-checking prompt with all approved content."""
        pieces = []
        for i, item in enumerate(content_items):
            ct = item.get("content_type", "post")
            text = item.get("final_text", "")
            pieces.append(
                f"--- CONTENT PIECE {i} (type: {ct}) ---\n{text}\n"
            )

        return (
            "Review the following approved LinkedIn content for factual accuracy.\n"
            "Check every claim, statistic, company name, and attribution.\n"
            "Return a JSON array with one object per piece.\n\n"
            + "\n".join(pieces)
        )

    def run(self, approved_items: list[dict]) -> list[dict]:
        """Fact-check all approved content items.

        Args:
            approved_items: List of review dicts with verdict=APPROVED and final_text

        Returns:
            The same list with fact_check_status, fact_check_issues added.
            Items with FAIL verdict get demoted to REJECTED.
        """
        if not approved_items:
            logger.info("[fact_checker] no items to check")
            return approved_items

        logger.info(f"[fact_checker] checking {len(approved_items)} items")

        prompt = self._build_prompt(approved_items)

        try:
            results = self.call_json(prompt, temperature=0.3)
        except Exception as e:
            logger.error(f"[fact_checker] API call failed: {e}")
            # On failure, let content through with a warning
            for item in approved_items:
                item["fact_check_status"] = "skipped"
                item["fact_check_issues"] = [f"Fact checker failed: {e}"]
            return approved_items

        if not isinstance(results, list):
            results = [results]

        # Apply fact-check results back to items
        pass_count = 0
        flag_count = 0
        fail_count = 0

        for result in results:
            idx = result.get("index", 0)
            if idx >= len(approved_items):
                continue

            item = approved_items[idx]
            verdict = result.get("verdict", "PASS").upper()
            issues = result.get("issues", [])
            corrected_text = result.get("corrected_text")

            item["fact_check_status"] = verdict.lower()
            item["fact_check_issues"] = issues

            if verdict == "PASS":
                pass_count += 1

            elif verdict == "FLAG":
                flag_count += 1
                # Apply corrections if provided
                if corrected_text:
                    item["final_text"] = corrected_text
                    logger.info(f"[fact_checker] item {idx}: FLAG — applied corrections")

            elif verdict == "FAIL":
                fail_count += 1
                # Demote to REJECTED
                item["verdict"] = "REJECTED"
                item["rejection_reason"] = f"Fact check failed: {issues}"
                if corrected_text:
                    # Save corrected version but still reject for review
                    item["fact_check_corrected_text"] = corrected_text
                logger.warning(
                    f"[fact_checker] item {idx}: FAIL — demoted to REJECTED. "
                    f"Issues: {issues}"
                )

        logger.info(
            f"[fact_checker] results: {pass_count} PASS, "
            f"{flag_count} FLAG (corrected), {fail_count} FAIL (rejected)"
        )

        return approved_items
