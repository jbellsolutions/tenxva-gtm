"""Profile Writer agent — drafts optimized LinkedIn profile sections."""

import json
import logging

from agents.base import BaseAgent, load_config

logger = logging.getLogger(__name__)


class ProfileWriter(BaseAgent):
    max_tokens = 8192

    def __init__(self):
        super().__init__("profile_writer", prompt_file="profile_optimizer.md")
        self.business = load_config("business.yaml")

    def run(self, audit: dict) -> dict:
        """Write optimized profile sections based on audit results."""
        logger.info("[profile_writer] writing optimized profile sections")

        prompt = (
            f"Based on this profile audit, write the optimized profile sections.\n\n"
            f"## Audit Results\n```json\n{json.dumps(audit, indent=2)[:5000]}\n```\n\n"
            f"## Business Context\n```json\n{json.dumps(self.business, indent=2)[:3000]}\n```\n\n"
            f"Write the following sections:\n"
            f"1. Headline (max 220 chars) — 3 options\n"
            f"2. About section (max 2000 chars) — full text\n"
            f"3. Experience bullets for current role\n"
            f"4. Featured section recommendations\n\n"
            f"Return valid JSON with: headline_options (array of 3), about, "
            f"experience_bullets (array), featured_suggestions (array)"
        )

        profile = self.call_json(prompt)

        self.save_output(
            profile,
            "analytics",
            f"profile_rewrite_{self.today_str()}.json",
        )

        logger.info("[profile_writer] profile sections written")
        return profile
