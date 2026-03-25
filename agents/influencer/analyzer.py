"""Content Analyzer agent — analyzes influencer posts for patterns and content ideas."""

from __future__ import annotations

import json
import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ContentAnalyzer(BaseAgent):
    def __init__(self):
        super().__init__("content_analyzer", prompt_file=None)
        self.system_prompt = """You are an expert LinkedIn content analyst for TenXVA ("Using AI to Scale").

Your job is to analyze scraped influencer posts and extract:
1. Top-performing content patterns (what gets the most engagement)
2. Content ideas Justin Bellware can adapt for his audience
3. Trending topics and formats in the AI/business space
4. Hook patterns and structures that work

You focus on AI automation, virtual assistants, remote teams, and business scaling content.

Return your analysis as valid JSON."""

    def run(self, scraped_data: list[dict]) -> dict:
        """Analyze scraped influencer content for patterns and ideas."""
        logger.info(f"[content_analyzer] analyzing posts from {len(scraped_data)} influencers")

        # Filter to influencers with actual posts
        with_posts = [d for d in scraped_data if d.get("posts")]

        prompt = (
            f"Analyze these scraped LinkedIn influencer posts. Identify top-performing "
            f"content patterns, hook structures, and content ideas Justin Bellware can "
            f"adapt for TenXVA.\n\n"
            f"## Scraped Data\n```json\n{json.dumps(with_posts, indent=2)[:10000]}\n```\n\n"
            f"Return JSON with:\n"
            f"- top_posts: array of the 5 highest-engagement posts with analysis\n"
            f"- patterns: array of content pattern observations\n"
            f"- content_ideas: array of 5-10 content ideas for Justin\n"
            f"- hook_analysis: array of effective hook structures found\n"
            f"- trending_topics: what topics are getting the most traction"
        )

        analysis = self.call_json(prompt)

        self.save_output(
            analysis,
            "influencers/analysis",
            f"{self.today_str()}_analysis.json",
        )

        logger.info("[content_analyzer] analysis complete")
        return analysis
