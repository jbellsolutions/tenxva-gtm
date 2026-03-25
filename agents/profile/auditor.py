"""Profile Auditor agent — audits LinkedIn profile against 360 Brew algorithm."""

import json
import logging

from agents.base import BaseAgent, load_config
from tools import apify_client

logger = logging.getLogger(__name__)


class ProfileAuditor(BaseAgent):
    def __init__(self):
        super().__init__("profile_auditor", prompt_file="profile_optimizer.md")
        self.business = load_config("business.yaml")

    def run(self) -> dict:
        """Audit Justin's LinkedIn profile."""
        profile_url = self.business.get("linkedin", "")
        logger.info(f"[profile_auditor] auditing profile: {profile_url}")

        # Scrape current profile
        try:
            profile_data = apify_client.scrape_linkedin_profile(profile_url)
        except Exception as e:
            logger.error(f"[profile_auditor] scrape failed: {e}")
            profile_data = {}

        prompt = (
            f"Audit this LinkedIn profile for TenXVA / Using AI to Scale.\n\n"
            f"## Current Profile Data\n```json\n{json.dumps(profile_data, indent=2)[:6000]}\n```\n\n"
            f"## Business Context\n```json\n{json.dumps(self.business, indent=2)[:3000]}\n```\n\n"
            f"Audit the profile against the 360 Brew algorithm requirements. "
            f"Score each section and provide specific rewrite recommendations.\n\n"
            f"Return your audit as valid JSON."
        )

        audit = self.call_json(prompt)

        self.save_output(audit, "analytics", f"profile_audit_{self.today_str()}.json")
        logger.info("[profile_auditor] audit complete")
        return audit
