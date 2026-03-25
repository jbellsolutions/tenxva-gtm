"""Newsletter Researcher agent — deep research for newsletter content.

Runs BEFORE the LongFormWriter for newsletters. Enriches the brief with:
- Key statistics from credible sources
- Authority sources (named experts, companies, studies)
- A framework or mental model worth saving
- Visual content suggestions
- A contrarian or unique angle

This agent uses web-search-like reasoning to produce credible, authority-packed
research that makes the final newsletter impossible to ignore.
"""

from __future__ import annotations

import json
import logging

from agents.base import BaseAgent

logger = logging.getLogger(__name__)


class NewsletterResearcher(BaseAgent):
    """Researches newsletter topics to produce authority-packed research packages."""

    max_tokens = 8192

    def __init__(self):
        super().__init__("newsletter_researcher")

    def _build_research_prompt(self, brief: dict, trends: list[dict] | None = None) -> str:
        """Build a research prompt from the newsletter brief."""
        trend_context = ""
        if trends:
            trend_context = (
                f"\n## Current Trends Context\n"
                f"```json\n{json.dumps(trends[:5], indent=2)[:3000]}\n```\n"
            )

        return (
            f"Research the following newsletter topic deeply.\n\n"
            f"## Newsletter Brief\n```json\n{json.dumps(brief, indent=2)}\n```\n"
            f"{trend_context}\n"
            f"## Business Context\n"
            f"- Author: Justin Bellware — AI implementation practitioner\n"
            f"- Newsletter: 'Using AI to Scale' on LinkedIn\n"
            f"- Audience: Business owners, ops managers, founders exploring AI\n"
            f"- Tone: Practitioner sharing real experience, not lecturing\n"
            f"- Case Studies: ops manager (5 AI agent teams), developer (prototype to alpha in 5 days), "
            f"insurance agency (custom CRM in 48 hours)\n\n"
            f"Produce a complete research package following your instructions. "
            f"Return valid JSON matching the output format in your system prompt."
        )

    def run(self, brief: dict, trends: list[dict] | None = None) -> dict:
        """Research a newsletter topic and return enriched brief.

        Args:
            brief: The newsletter brief from SwipeStrategist
            trends: Optional current trends for additional context

        Returns:
            Research package dict with key_stats, authority_sources, framework,
            visual_suggestions, contrarian_angle, etc.
        """
        topic = brief.get("angle", brief.get("trend_source", "AI implementation"))
        logger.info(f"[newsletter_researcher] researching: {topic}")

        prompt = self._build_research_prompt(brief, trends)

        try:
            research = self.call_json(prompt, temperature=0.5)
        except Exception as e:
            logger.error(f"[newsletter_researcher] research failed: {e}")
            # Return minimal research package so pipeline continues
            research = {
                "topic_summary": topic,
                "key_stats": [],
                "authority_sources": [],
                "framework": None,
                "visual_suggestions": [],
                "contrarian_angle": "",
                "error": str(e),
            }

        # Save research output
        self.save_output(
            research,
            f"research/{self.today_str()}",
            f"newsletter_research_{brief.get('content_type', 'newsletter')}_{self.today_str()}.json",
        )

        logger.info(
            f"[newsletter_researcher] research complete: "
            f"{len(research.get('key_stats', []))} stats, "
            f"{len(research.get('authority_sources', []))} sources, "
            f"framework: {'yes' if research.get('framework') else 'no'}"
        )

        return research

    def enrich_brief(self, brief: dict, research: dict) -> dict:
        """Merge research into the brief for the LongFormWriter.

        Creates an enriched brief that includes all original brief data
        plus the research package as additional context.
        """
        enriched = dict(brief)
        enriched["research"] = research
        enriched["research_stats"] = research.get("key_stats", [])
        enriched["research_sources"] = research.get("authority_sources", [])
        enriched["research_framework"] = research.get("framework")
        enriched["research_visuals"] = research.get("visual_suggestions", [])
        enriched["research_contrarian"] = research.get("contrarian_angle", "")
        enriched["research_structure"] = research.get("recommended_structure", "")
        enriched["research_enriched"] = True

        return enriched
