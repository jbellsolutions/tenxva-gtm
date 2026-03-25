"""Influencer Scraper agent — scrapes latest posts from tracked influencers."""

from __future__ import annotations

import json
import logging

from agents.base import BaseAgent, load_config
from tools import apify_client

logger = logging.getLogger(__name__)


class InfluencerScraper(BaseAgent):
    def __init__(self):
        super().__init__("influencer_scraper", prompt_file=None)
        self.influencer_config = load_config("influencers.yaml")
        self.scrape_config = self.influencer_config.get("scraping_config", {})

    def run(self, priority_filter: str | None = None) -> list[dict]:
        """Scrape latest posts from tracked influencers.

        priority_filter: "high", "medium", "low", or None for all
        """
        influencers = self.influencer_config.get("influencers", [])
        if priority_filter:
            influencers = [i for i in influencers if i.get("priority") == priority_filter]

        posts_per = self.scrape_config.get("posts_per_influencer", 5)
        max_profiles = self.scrape_config.get("max_profiles_per_day", 50)
        influencers = influencers[:max_profiles]

        logger.info(f"[influencer_scraper] scraping {len(influencers)} influencers")

        all_data = []
        for inf in influencers:
            name = inf["name"]
            url = inf["linkedin"]
            logger.info(f"[influencer_scraper] scraping {name}")
            try:
                posts = apify_client.scrape_linkedin_posts(url, max_posts=posts_per)
                all_data.append({
                    "name": name,
                    "linkedin": url,
                    "topics": inf.get("topics", []),
                    "priority": inf.get("priority", "medium"),
                    "posts": posts,
                    "post_count": len(posts),
                })
            except Exception as e:
                logger.warning(f"[influencer_scraper] failed for {name}: {e}")
                all_data.append({
                    "name": name,
                    "linkedin": url,
                    "posts": [],
                    "error": str(e),
                })

        self.save_output(
            all_data,
            "influencers/content",
            f"{self.today_str()}_scraped.json",
        )

        total_posts = sum(d.get("post_count", 0) for d in all_data)
        logger.info(f"[influencer_scraper] scraped {total_posts} posts from {len(all_data)} influencers")
        return all_data
