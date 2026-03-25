"""Profile Team orchestrator — audits and optimizes LinkedIn profile."""

import logging
from datetime import datetime

from agents.profile.auditor import ProfileAuditor
from agents.profile.writer import ProfileWriter

logger = logging.getLogger(__name__)


def run_monthly_audit():
    """Run a full profile audit and generate optimized copy.

    Runs on the 1st of each month at 9:00 AM ET.
    """
    start = datetime.now()
    logger.info(f"[profile_team] starting monthly audit at {start.isoformat()}")

    try:
        # Step 1: Audit current profile
        auditor = ProfileAuditor()
        audit = auditor.run()

        # Step 2: Write optimized profile
        writer = ProfileWriter()
        profile = writer.run(audit)

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"[profile_team] monthly audit complete in {elapsed:.1f}s")

        return {
            "status": "success",
            "audit_score": audit.get("audit_scores", {}).get("overall_360_brew_score"),
            "headline_options": profile.get("headline_options", []),
            "elapsed_seconds": elapsed,
        }

    except Exception as e:
        logger.error(f"[profile_team] audit failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
