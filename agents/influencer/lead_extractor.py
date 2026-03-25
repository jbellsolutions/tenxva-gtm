"""Lead Extractor agent — scrapes commenters from top influencer posts and enriches them."""

from __future__ import annotations

import json
import logging

from agents.base import BaseAgent, load_config
from tools import apify_client, retriever_client

logger = logging.getLogger(__name__)


class LeadExtractor(BaseAgent):
    def __init__(self):
        super().__init__("lead_extractor", prompt_file=None)
        config = load_config("influencers.yaml")
        self.scrape_config = config.get("scraping_config", {})

    def _identify_top_posts(self, scraped_data: list[dict]) -> list[dict]:
        """Find posts with enough engagement to warrant commenter scraping."""
        threshold = self.scrape_config.get("commenter_scrape_threshold", 100)
        top_posts = []

        for influencer in scraped_data:
            for post in influencer.get("posts", []):
                comments = post.get("commentsCount", post.get("comments", 0))
                likes = post.get("likesCount", post.get("likes", 0))
                if isinstance(comments, int) and comments >= threshold:
                    top_posts.append({
                        "influencer": influencer["name"],
                        "post_url": post.get("postUrl", post.get("url", "")),
                        "comments_count": comments,
                        "likes_count": likes,
                        "topic": post.get("text", "")[:200],
                    })

        # Sort by comment count, take top 5
        top_posts.sort(key=lambda x: x["comments_count"], reverse=True)
        return top_posts[:5]

    def run(self, scraped_data: list[dict]) -> dict:
        """Extract leads from top-performing influencer posts."""
        logger.info("[lead_extractor] identifying top posts for lead extraction")

        # 1. Find top posts worth scraping
        top_posts = self._identify_top_posts(scraped_data)
        logger.info(f"[lead_extractor] found {len(top_posts)} posts worth scraping")

        if not top_posts:
            logger.info("[lead_extractor] no posts met the comment threshold")
            return {"leads": [], "posts_scraped": 0}

        # 2. Scrape commenters from each post
        all_commenters = []
        for post in top_posts:
            url = post["post_url"]
            if not url:
                continue
            try:
                commenters = apify_client.scrape_post_commenters(url, max_comments=100)
                for c in commenters:
                    c["source_post"] = post["influencer"]
                    c["source_url"] = url
                all_commenters.extend(commenters)
            except Exception as e:
                logger.warning(f"[lead_extractor] failed to scrape commenters: {e}")

        logger.info(f"[lead_extractor] scraped {len(all_commenters)} commenters")

        # 3. Deduplicate by LinkedIn URL
        seen = set()
        unique = []
        for c in all_commenters:
            linkedin = c.get("profileUrl", c.get("linkedinUrl", ""))
            if linkedin and linkedin not in seen:
                seen.add(linkedin)
                unique.append(c)
        logger.info(f"[lead_extractor] {len(unique)} unique commenters")

        # 4. Enrich via Retriever
        linkedin_urls = [
            c.get("profileUrl", c.get("linkedinUrl", ""))
            for c in unique[:30]  # Limit enrichment to top 30
            if c.get("profileUrl") or c.get("linkedinUrl")
        ]

        enriched = []
        if linkedin_urls:
            try:
                enriched = retriever_client.enrich_batch(linkedin_urls)
            except Exception as e:
                logger.warning(f"[lead_extractor] enrichment failed: {e}")

        # 5. Save results
        output = {
            "date": self.today_str(),
            "posts_scraped": len(top_posts),
            "total_commenters": len(all_commenters),
            "unique_commenters": len(unique),
            "enriched": len([e for e in enriched if "error" not in e]),
            "leads": enriched,
            "top_posts": top_posts,
        }

        self.save_output(output, "leads", f"{self.today_str()}_leads.json")
        logger.info(f"[lead_extractor] extracted {len(enriched)} enriched leads")
        return output
