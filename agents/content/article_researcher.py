"""Article Researcher agent — deep research for article content.

Runs BEFORE the LongFormWriter for articles. Enriches the brief with:
- SEO keywords and search intent
- Todd Brown unique mechanism breakdown
- Proof points with real data
- Practitioner insights (specific tools, timelines, mistakes)
- Article structure recommendations

This agent produces research that makes the final article the definitive
resource on its topic — designed to rank, get bookmarked, and shared.
"""

from __future__ import annotations

import json
import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ArticleResearcher(BaseAgent):
    """Researches article topics to produce SEO-optimized, mechanism-rich research packages."""

    max_tokens = 8192

    def __init__(self):
        super().__init__("article_researcher")

    def _build_research_prompt(self, brief: dict, trends: list[dict] | None = None) -> str:
        """Build a research prompt from the article brief."""
        trend_context = ""
        if trends:
            trend_context = (
                f"\n## Current Trends Context\n"
                f"```json\n{json.dumps(trends[:5], indent=2)[:3000]}\n```\n"
            )

        return (
            f"Research the following article topic deeply.\n\n"
            f"## Article Brief\n```json\n{json.dumps(brief, indent=2)}\n```\n"
            f"{trend_context}\n"
            f"## Business Context\n"
            f"- Author: Justin Bellware — AI implementation practitioner\n"
            f"- Platform: LinkedIn articles under 'Using AI to Scale'\n"
            f"- Audience: Business owners, ops managers, founders discovering AI through search\n"
            f"- Tone: Practitioner sharing real experience with specific tools and timelines\n"
            f"- Case Studies: ops manager (5 AI agent teams), developer (prototype to alpha in 5 days), "
            f"insurance agency (custom CRM in 48 hours)\n"
            f"- Named mechanisms: The 30-Day AI Bootcamp, The 5-Tool Power Stack, "
            f"The AI Growth Hacker Certification\n\n"
            f"Produce a complete research package following your instructions. "
            f"Return valid JSON matching the output format in your system prompt."
        )

    def run(self, brief: dict, trends: list[dict] | None = None) -> dict:
        """Research an article topic and return enriched brief.

        Args:
            brief: The article brief from SwipeStrategist
            trends: Optional current trends for additional context

        Returns:
            Research package dict with seo_keywords, mechanism, proof_points,
            practitioner_insights, article_structure, etc.
        """
        topic = brief.get("angle", brief.get("trend_source", "AI automation"))
        logger.info(f"[article_researcher] researching: {topic}")

        prompt = self._build_research_prompt(brief, trends)

        try:
            research = self.call_json(prompt, temperature=0.5)
        except Exception as e:
            logger.error(f"[article_researcher] research failed: {e}")
            # Return minimal research package so pipeline continues
            research = {
                "topic_summary": topic,
                "seo_keywords": {"primary": "", "secondary": []},
                "mechanism": None,
                "proof_points": [],
                "practitioner_insights": {},
                "article_structure": {},
                "error": str(e),
            }

        # Save research output
        self.save_output(
            research,
            f"research/{self.today_str()}",
            f"article_research_{self.today_str()}.json",
        )

        logger.info(
            f"[article_researcher] research complete: "
            f"mechanism: {'yes' if research.get('mechanism') else 'no'}, "
            f"{len(research.get('proof_points', []))} proof points, "
            f"SEO primary: {research.get('seo_keywords', {}).get('primary', 'none')}"
        )

        return research

    def enrich_brief(self, brief: dict, research: dict) -> dict:
        """Merge research into the brief for the LongFormWriter.

        Creates an enriched brief that includes all original brief data
        plus the research package as additional context.
        """
        enriched = dict(brief)
        enriched["research"] = research
        enriched["research_seo"] = research.get("seo_keywords", {})
        enriched["research_mechanism"] = research.get("mechanism")
        enriched["research_proof"] = research.get("proof_points", [])
        enriched["research_practitioner"] = research.get("practitioner_insights", {})
        enriched["research_structure"] = research.get("article_structure", {})
        enriched["research_visuals"] = research.get("visual_suggestions", [])
        enriched["research_enriched"] = True

        return enriched
