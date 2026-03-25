"""Trend Analyst agent — scrapes sources and identifies content angles."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from agents.base import BaseAgent, load_config
from tools import firecrawl_client

logger = logging.getLogger(__name__)


class TrendAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("trend_analyst")
        self.sources = load_config("trend_sources.yaml")

    def _scrape_web_searches(self) -> list[dict]:
        """Run Firecrawl searches for each configured query."""
        results = []
        for source in self.sources.get("web_search_queries", []):
            try:
                hits = firecrawl_client.search(source["query"], limit=3)
                for hit in hits:
                    hit["category"] = source["category"]
                    hit["relevance"] = source["relevance"]
                results.append({"query": source["query"], "results": hits})
            except Exception as e:
                logger.warning(f"Search failed for '{source['query']}': {e}")
        return results

    def _scrape_urls(self) -> list[dict]:
        """Scrape configured news sites for headlines."""
        results = []
        for source in self.sources.get("scrape_urls", []):
            try:
                data = firecrawl_client.extract_headlines(source["url"])
                data["category"] = source["category"]
                results.append(data)
            except Exception as e:
                logger.warning(f"Scrape failed for '{source['url']}': {e}")
        return results

    def _get_recent_angles(self, days: int = 7) -> list[str]:
        """Load angles from recent days to avoid duplicates."""
        recent = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            data = self.load_latest("trend-intel", prefix=date)
            if data and isinstance(data, list):
                for trend in data:
                    recent.extend(trend.get("content_angles", []))
        return recent

    def run(self) -> list[dict]:
        """Run the full trend analysis pipeline."""
        logger.info("[trend_analyst] starting daily trend scan")

        # 1. Scrape all sources
        search_results = self._scrape_web_searches()
        url_results = self._scrape_urls()

        # 2. Get recent angles for dedup
        recent_angles = self._get_recent_angles(
            self.sources.get("dedup_against_days", 7)
        )

        # 3. Build the prompt
        has_scraped_data = any(
            r.get("results") for r in search_results
        ) or any(
            r.get("markdown") for r in url_results
        )

        if has_scraped_data:
            scraped_content = json.dumps({
                "web_searches": search_results,
                "scraped_sites": url_results,
            }, indent=2)
            source_section = f"## Scraped Content\n```json\n{scraped_content[:8000]}\n```"
        else:
            # Fallback: ask Claude to use its knowledge of current trends
            logger.info("[trend_analyst] no scraped data available, using Claude's knowledge")
            source_section = (
                "## Note: Web scraping was unavailable today.\n"
                "Use your knowledge of current AI, automation, remote work, and business "
                "trends as of today's date to generate trending topics. Focus on:\n"
                "- AI agent/automation news and developments\n"
                "- Claude, GPT, and other AI tool updates\n"
                "- Remote team productivity and VA industry shifts\n"
                "- LinkedIn content strategy trends\n"
                "- Business scaling with AI\n"
            )

        dedup_section = ""
        if recent_angles:
            dedup_section = (
                f"\n\n## AVOID THESE ANGLES (already covered recently):\n"
                + "\n".join(f"- {a}" for a in recent_angles[:30])
            )

        max_trends = self.sources.get("max_trends_per_day", 10)
        prompt = (
            f"Today is {self.today_str()}. Identify the top {max_trends} trending "
            f"topics for TenXVA content.\n\n"
            f"{source_section}"
            f"{dedup_section}\n\n"
            f"IMPORTANT: Return a JSON ARRAY of {max_trends} trend objects. "
            f"Your response MUST start with [ and end with ]. "
            f"Include {max_trends} diverse trend objects in the array. "
            f"Do NOT return a single trend object — return an array."
        )

        # 4. Call Claude
        trends = self.call_json(prompt)

        # Guard: ensure we always have a list of dicts
        # Claude sometimes returns a single trend dict instead of a list
        if isinstance(trends, dict):
            # Check if it looks like a single trend object (has 'title' key)
            if "title" in trends:
                logger.warning("[trend_analyst] got single trend dict — wrapping in list")
                trends = [trends]
            # Or it might be a wrapper like {"trends": [...]}
            elif "trends" in trends and isinstance(trends["trends"], list):
                logger.info("[trend_analyst] unwrapping {trends: [...]} response")
                trends = trends["trends"]
            else:
                logger.warning(f"[trend_analyst] unexpected dict format, keys: {list(trends.keys())}")
                trends = [trends]

        if not isinstance(trends, list):
            logger.error(f"[trend_analyst] call_json returned {type(trends).__name__}, expected list")
            trends = []

        # 5. Save output
        self.save_output(
            trends,
            "trend-intel",
            f"{self.today_str()}_trends.json",
        )

        logger.info(f"[trend_analyst] identified {len(trends)} trends")
        return trends
