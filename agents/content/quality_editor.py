"""Quality Editor agent — reviews all content before publishing.

Includes:
- AI quality review via Claude
- Automated formatting validation (markdown artifacts, LinkedIn readiness)
- AI detection pattern flagging
- Text sanitization of approved content's final_text
"""

from __future__ import annotations

import json
import logging

from agents.base import BaseAgent
from tools.text_sanitizer import (
    check_formatting_issues,
    strip_markdown,
    humanize_text,
    format_for_linkedin,
)

logger = logging.getLogger(__name__)


class QualityEditor(BaseAgent):
    max_tokens = 16384

    def __init__(self):
        super().__init__("quality_editor")

    def _review_batch(self, content_items: list[dict], content_type: str) -> list[dict]:
        """Review a batch of content items."""
        # Content-type-specific review guidance
        type_guidance = ""
        if "article" in content_type.lower():
            type_guidance = (
                "## IMPORTANT: Article-Specific Review Criteria\n"
                "You are reviewing ARTICLES (1000-1500 words), NOT short posts.\n"
                "- Articles can open with a problem statement OR a scene — both are valid\n"
                "- Multiple sections with different sub-insights are EXPECTED and GOOD\n"
                "- 1000-1500 words is the TARGET — do NOT penalize for length\n"
                "- Section titles, bullet points, and structured formatting are EXPECTED\n"
                "- Look for: named mechanism, specific tools/numbers, practitioner depth, bookmark-worthy value\n"
                "- Do NOT apply the post-specific Mueller 'opens with scene' requirement strictly\n"
                "- Score 70+ if it has genuine value, specific details, and practitioner authority\n\n"
            )
        elif "newsletter" in content_type.lower():
            type_guidance = (
                "## IMPORTANT: Newsletter-Specific Review Criteria\n"
                "You are reviewing NEWSLETTERS (800-1200 words), NOT short posts.\n"
                "- Mueller 5-phase narrative IS required for newsletters\n"
                "- 800-1200 words is the TARGET — do NOT penalize for length\n"
                "- Must include a saveable framework, checklist, or template\n"
                "- 2-3 named sections within the narrative are OK and expected\n"
                "- Score 70+ if it tells a compelling story with a clear, save-worthy takeaway\n\n"
            )

        prompt = (
            f"Review the following {content_type} content for TenXVA.\n"
            f"Apply the quality checklist from your instructions.\n\n"
            f"{type_guidance}"
            f"## Content to Review\n```json\n{json.dumps(content_items, indent=2)[:12000]}\n```\n\n"
            f"## Business Quick Reference\n"
            f"- Brand: TenXVA / Using AI to Scale\n"
            f"- Author: Justin Bellware\n"
            f"- Voice: Expert authority, direct, no-BS, tactical, approachable\n"
            f"- NEVER: hard CTAs, hashtags, hype language, generic AI advice\n"
            f"- ALWAYS: specific numbers, save-worthy elements, first-person voice\n\n"
            f"Review each piece. Return a JSON array of review objects."
        )
        return self.call_json(prompt)

    def _post_process_reviews(
        self, reviews: list[dict], content_type: str = "post"
    ) -> list[dict]:
        """Post-process AI reviews with automated formatting checks.

        For each approved review:
        1. Check final_text for markdown artifacts
        2. Strip markdown from final_text
        3. Humanize AI-telltale patterns
        4. Format for LinkedIn
        5. Flag any remaining formatting issues
        6. Deduct score points for formatting problems found

        For rejected reviews: skip sanitization but still flag issues.

        Args:
            reviews: List of review dicts from AI review.
            content_type: "post", "article", or "newsletter" — adjusts thresholds.
        """
        for review in reviews:
            final_text = review.get("final_text", "")
            if not final_text:
                continue

            # Check raw text for formatting issues BEFORE sanitization
            raw_issues = check_formatting_issues(final_text, content_type=content_type)
            if raw_issues:
                existing_issues = review.get("issues", [])
                if not isinstance(existing_issues, list):
                    existing_issues = []
                for issue in raw_issues:
                    formatted_issue = f"[FORMAT] {issue}"
                    if formatted_issue not in existing_issues:
                        existing_issues.append(formatted_issue)
                review["issues"] = existing_issues

                # Deduct score for formatting issues found
                score = review.get("score", 0)
                if isinstance(score, (int, float)):
                    formatting_penalty = min(len(raw_issues) * 3, 15)
                    review["score"] = max(0, score - formatting_penalty)
                    if formatting_penalty > 0:
                        logger.info(
                            f"[quality_editor] deducted {formatting_penalty} points "
                            f"for {len(raw_issues)} formatting issues"
                        )

            # For APPROVED content, sanitize the final_text
            if review.get("verdict") == "APPROVED" and final_text:
                # Strip markdown artifacts
                cleaned = strip_markdown(final_text)
                # Humanize AI patterns
                cleaned = humanize_text(cleaned)
                # Format for LinkedIn
                cleaned = format_for_linkedin(cleaned)
                review["final_text"] = cleaned

                # Verify clean after sanitization
                post_issues = check_formatting_issues(cleaned, content_type=content_type)
                if post_issues:
                    review["formatting_warnings"] = post_issues

        return reviews

    def run(self, posts: dict, longform: dict) -> dict:
        """Review all today's content."""
        logger.info("[quality_editor] reviewing all content")

        results = {"posts": [], "newsletters": [], "articles": []}

        # Review posts
        post_list = posts.get("posts", [])
        if post_list:
            results["posts"] = self._review_batch(post_list, "LinkedIn posts")

        # Review newsletters
        newsletters = longform.get("newsletters", [])
        if newsletters:
            results["newsletters"] = self._review_batch(newsletters, "LinkedIn newsletters")

        # Review articles
        articles = longform.get("articles", [])
        if articles:
            results["articles"] = self._review_batch(articles, "LinkedIn articles")

        # Post-process all reviews with formatting checks and sanitization
        # Pass content_type so formatting thresholds are appropriate
        _ct_map = {"posts": "post", "newsletters": "newsletter", "articles": "article"}
        for category in ["posts", "newsletters", "articles"]:
            if results[category]:
                results[category] = self._post_process_reviews(
                    results[category], content_type=_ct_map[category]
                )

        # Collect approved content
        approved = []
        rejected = []
        formatting_issues_total = 0
        for category in ["posts", "newsletters", "articles"]:
            for review in results.get(category, []):
                if review.get("verdict") == "APPROVED":
                    approved.append(review)
                else:
                    rejected.append(review)
                # Count formatting issues
                issues = review.get("issues", [])
                formatting_issues_total += sum(
                    1 for i in issues if isinstance(i, str) and i.startswith("[FORMAT]")
                )

        results["summary"] = {
            "total_reviewed": len(approved) + len(rejected),
            "approved": len(approved),
            "rejected": len(rejected),
            "formatting_issues_found": formatting_issues_total,
        }

        # Determine filename based on what was reviewed (avoid overwrites)
        content_types_reviewed = []
        if results["posts"]:
            content_types_reviewed.append("posts")
        if results["newsletters"]:
            content_types_reviewed.append("newsletters")
        if results["articles"]:
            content_types_reviewed.append("articles")
        filename_suffix = "_".join(content_types_reviewed) if content_types_reviewed else "all"
        self.save_output(
            results,
            f"drafts/{self.today_str()}",
            f"reviews_{filename_suffix}.json",
        )

        logger.info(
            f"[quality_editor] {len(approved)} approved, {len(rejected)} rejected, "
            f"{formatting_issues_total} formatting issues found & fixed"
        )
        return results
