"""Swipe Strategist agent — matches trends to swipe file and creates content briefs."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from agents.base import BaseAgent, load_config
from tools import swipe_reader

logger = logging.getLogger(__name__)


class SwipeStrategist(BaseAgent):
    def __init__(self):
        super().__init__("swipe_strategist")
        self.calendar = load_config("content_calendar.yaml")

    def _build_swipe_context(self, trends: list[dict]) -> str:
        """Build swipe file context based on trend keywords."""
        all_keywords = set()
        for trend in trends:
            if not isinstance(trend, dict):
                logger.warning(f"[swipe_strategist] skipping non-dict trend: {type(trend)}")
                continue
            all_keywords.update(trend.get("swipe_keywords", []))
            # Also extract words from title
            all_keywords.update(
                w.lower() for w in trend.get("title", "").split()
                if len(w) > 3
            )

        sections = [swipe_reader.get_sender_summary()]

        # Search for relevant examples per keyword cluster
        for kw in list(all_keywords)[:8]:
            context = swipe_reader.get_swipe_context_for_brief(
                topic=kw,
                copywriter_keys=["alex_hormozi", "bill_mueller", "brian_kurtz", "liam_ottley"],
                max_subjects=5,
                max_body_examples=1,
            )
            if context.strip():
                sections.append(context)

        return "\n\n---\n\n".join(sections)

    def _get_todays_content_needs(self) -> str:
        """Determine what content types are needed today."""
        day_name = datetime.now().strftime("%A").lower()
        needs = []

        # Daily posts are always needed
        for post_key, post_config in self.calendar.get("daily_posts", {}).items():
            needs.append({
                "type": post_config["type"],
                "time": post_config["time"],
                "copywriter_dna": post_config.get("copywriter_dna", []),
                "word_count": post_config.get("word_count", [150, 250]),
                "optional": post_config.get("optional", False),
            })

        # Newsletter?
        newsletter = self.calendar.get("newsletter", {})
        if day_name in newsletter.get("days", []):
            needs.append({
                "type": "newsletter",
                "time": newsletter["time"],
                "copywriter_dna": newsletter.get("copywriter_dna", []),
                "word_count": newsletter.get("word_count", [800, 1200]),
            })

        # Article?
        article = self.calendar.get("article", {})
        if day_name in article.get("days", []):
            needs.append({
                "type": "article",
                "time": article["time"],
                "copywriter_dna": article.get("copywriter_dna", []),
                "word_count": article.get("word_count", [1000, 1500]),
            })

        return json.dumps(needs, indent=2)

    def run(self, trends: list[dict]) -> list[dict]:
        """Create content briefs from trends + swipe file."""
        logger.info(f"[swipe_strategist] creating briefs from {len(trends)} trends")

        # 1. Build swipe file context
        swipe_context = self._build_swipe_context(trends)

        # 2. Get today's content needs
        content_needs = self._get_todays_content_needs()

        # 3. Build prompt
        prompt = (
            f"Today is {self.today_str()} ({datetime.now().strftime('%A')}).\n\n"
            f"## Today's Content Needs\n```json\n{content_needs}\n```\n\n"
            f"## Today's Trends\n```json\n{json.dumps(trends, indent=2)[:4000]}\n```\n\n"
            f"## Swipe File Context\n{swipe_context[:6000]}\n\n"
            f"Create a content brief for EACH content need. Match trends to the "
            f"appropriate content types. Use the swipe file examples as inspiration.\n\n"
            f"Return your response as a JSON array of brief objects."
        )

        # 4. Call Claude
        briefs = self.call_json(prompt)

        # 5. Save
        self.save_output(
            briefs,
            "briefs",
            f"{self.today_str()}_briefs.json",
        )

        logger.info(f"[swipe_strategist] created {len(briefs)} briefs")
        return briefs
