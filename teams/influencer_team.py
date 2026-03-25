"""Influencer Team orchestrator — scrapes, analyzes, and extracts leads."""

import logging
from datetime import datetime

from agents.influencer.scraper import InfluencerScraper
from agents.influencer.analyzer import ContentAnalyzer
from agents.influencer.lead_extractor import LeadExtractor

logger = logging.getLogger(__name__)


def run_influencer_scrape():
    """Scrape influencer content and analyze it.

    Runs daily at 6:00 AM ET.
    """
    start = datetime.now()
    logger.info(f"[influencer_team] starting scrape+analyze at {start.isoformat()}")

    try:
        # Step 1: Scrape influencer posts
        scraper = InfluencerScraper()
        scraped = scraper.run(priority_filter="high")

        # Step 2: Analyze content patterns
        analyzer = ContentAnalyzer()
        analysis = analyzer.run(scraped)

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"[influencer_team] scrape+analyze complete in {elapsed:.1f}s")

        return {
            "status": "success",
            "influencers_scraped": len(scraped),
            "analysis": analysis,
            "elapsed_seconds": elapsed,
        }

    except Exception as e:
        logger.error(f"[influencer_team] scrape failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def run_lead_extraction():
    """Extract and enrich leads from influencer post commenters.

    Runs daily at 2:00 PM ET.
    """
    start = datetime.now()
    logger.info(f"[influencer_team] starting lead extraction at {start.isoformat()}")

    try:
        # Load today's scraped data
        scraper = InfluencerScraper()
        scraped = scraper.load_latest("influencers/content")
        if not scraped:
            logger.warning("[influencer_team] no scraped data found for today")
            return {"status": "skipped", "reason": "no scraped data"}

        # Extract leads
        extractor = LeadExtractor()
        leads = extractor.run(scraped)

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"[influencer_team] lead extraction complete in {elapsed:.1f}s")

        return {
            "status": "success",
            "leads_extracted": leads.get("enriched", 0),
            "elapsed_seconds": elapsed,
        }

    except Exception as e:
        logger.error(f"[influencer_team] lead extraction failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
