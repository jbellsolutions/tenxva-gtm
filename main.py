"""TenXVA GTM Content Agent System — Main Entry Point

Starts the scheduler and runs all agent teams on their configured schedules.
Can also run individual teams manually for testing.

Usage:
  python main.py                    # Start the scheduler (production mode)
  python main.py --run content      # Run content team once (testing)
  python main.py --run influencer   # Run influencer team once
  python main.py --run engagement   # Run engagement loop once
  python main.py --run comments     # Run strategic commenting once
  python main.py --run profile      # Run profile audit once
  python main.py --run all          # Run all teams once (full test)

Environment Variables Required:
  ANTHROPIC_API_KEY     - Claude API key
  FIRECRAWL_API_KEY     - Firecrawl API key
  APIFY_API_TOKEN       - Apify API token
  PHANTOMBUSTER_API_KEY - PhantomBuster API key
  RETRIEVER_API_KEY     - Retriever (rtrvr.ai) API key
  PB_POST_PHANTOM_ID   - PhantomBuster LinkedIn poster phantom ID
  PB_REPLY_PHANTOM_ID  - PhantomBuster reply phantom ID
  PB_COMMENT_PHANTOM_ID - PhantomBuster commenter phantom ID
"""

import os
import sys
import logging
import argparse

# Add project root to path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, ".env"), override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("tenxva-gtm.log"),
    ],
)
logger = logging.getLogger(__name__)


def check_env():
    """Check that required environment variables are set."""
    required = ["ANTHROPIC_API_KEY"]
    optional = [
        "FIRECRAWL_API_KEY",
        "APIFY_API_TOKEN",
        "PHANTOMBUSTER_API_KEY",
        "RETRIEVER_API_KEY",
        "PB_POST_PHANTOM_ID",
        "PB_REPLY_PHANTOM_ID",
        "PB_COMMENT_PHANTOM_ID",
    ]

    missing_required = [v for v in required if not os.environ.get(v)]
    if missing_required:
        logger.error(f"Missing required env vars: {', '.join(missing_required)}")
        sys.exit(1)

    missing_optional = [v for v in optional if not os.environ.get(v)]
    if missing_optional:
        logger.warning(f"Missing optional env vars (some features may not work): {', '.join(missing_optional)}")


def run_team(team: str):
    """Run a specific team manually (for testing)."""
    from teams.content_team import run_content_production
    from teams.influencer_team import run_influencer_scrape, run_lead_extraction
    from teams.engagement_team import run_engagement_loop, run_strategic_commenting
    from teams.profile_team import run_monthly_audit

    runners = {
        "content": ("Content Production", run_content_production),
        "influencer": ("Influencer Scrape", run_influencer_scrape),
        "leads": ("Lead Extraction", run_lead_extraction),
        "engagement": ("Engagement Loop", run_engagement_loop),
        "comments": ("Strategic Commenting", run_strategic_commenting),
        "profile": ("Profile Audit", run_monthly_audit),
    }

    if team == "all":
        for name, (label, func) in runners.items():
            logger.info(f"\n{'='*60}\nRunning: {label}\n{'='*60}")
            result = func()
            logger.info(f"Result: {result}")
        return

    if team not in runners:
        logger.error(f"Unknown team: {team}. Options: {', '.join(runners.keys())}, all")
        sys.exit(1)

    label, func = runners[team]
    logger.info(f"\n{'='*60}\nRunning: {label}\n{'='*60}")
    result = func()
    logger.info(f"Result: {result}")


def main():
    parser = argparse.ArgumentParser(description="TenXVA GTM Content Agent System")
    parser.add_argument(
        "--run",
        type=str,
        help="Run a specific team once: content, influencer, leads, engagement, comments, profile, all",
    )
    args = parser.parse_args()

    logger.info("TenXVA GTM Content Agent System starting...")
    check_env()

    if args.run:
        # Manual run mode (for testing)
        run_team(args.run)
    else:
        # Production mode — start dashboard + scheduler
        from scheduler import create_scheduler
        from tools.dashboard import start_dashboard

        # Start content review dashboard in background
        try:
            dashboard = start_dashboard(background=True)
            logger.info("Content review dashboard started on port 8080")
        except Exception as e:
            logger.warning(f"Dashboard failed to start (non-fatal): {e}")

        logger.info("Starting scheduler in production mode...")
        scheduler = create_scheduler()

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
