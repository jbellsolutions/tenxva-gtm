"""
Contact Enricher — pulls profile data from Unipile and enriches the AirTable database.

For each new engager:
1. View their LinkedIn profile (triggers a profile view on their end)
2. Extract: name, email, phone, company, title, headline
3. Score them as a lead (1-10)
4. Push enriched data to AirTable
"""

import logging
from agents.base import BaseAgent
from tools.unipile_client import UnipileClient
from tools.airtable_client import AirtableClient

logger = logging.getLogger(__name__)


class ContactEnricher(BaseAgent):
    """Enriches engager profiles and scores them as leads."""

    def __init__(self):
        super().__init__(name="contact_enricher", prompt_file=None)
        self.unipile = UnipileClient()
        self.airtable = AirtableClient()

    def enrich_and_store(self, engager: dict) -> dict:
        """
        Enrich a single engager's profile and store in AirTable.

        Args:
            engager: {
                "user_id": str,
                "name": str,
                "linkedin_url": str,
                "engagement_type": "like" | "comment",
                "post_url": str,
                "comment_text": str (optional),
            }

        Returns enriched data dict.
        """
        user_id = engager.get("user_id", "")
        linkedin_url = engager.get("linkedin_url", "")
        identifier = user_id or linkedin_url

        if not identifier:
            logger.warning(f"No identifier for engager: {engager.get('name', 'unknown')}")
            return engager

        # Step 1: View their profile (this also triggers a LinkedIn notification)
        profile = self.unipile.view_profile(identifier)

        if not profile:
            logger.warning(f"Could not retrieve profile for {identifier}")
            # Still add to DB with basic info
            self.airtable.add_engager({
                "name": engager.get("name", "Unknown"),
                "linkedin_url": linkedin_url,
                "engagement_type": engager.get("engagement_type", "like"),
                "post_url": engager.get("post_url", ""),
            })
            return engager

        # Step 2: Extract enrichment data
        enriched = {
            "name": profile.get("name") or f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip() or engager.get("name", "Unknown"),
            "linkedin_url": profile.get("public_profile_url") or profile.get("url") or linkedin_url,
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
            "company": profile.get("company") or self._extract_company(profile),
            "title": profile.get("headline") or profile.get("title", ""),
            "engagement_type": engager.get("engagement_type", "like"),
            "post_url": engager.get("post_url", ""),
        }

        # Step 3: Score as lead
        score = self._score_lead(enriched, engager)
        enriched["score"] = score

        # Step 4: Push to AirTable
        self.airtable.add_engager(enriched)

        # Log the enrichment
        self.airtable.log_engagement(
            linkedin_url=enriched["linkedin_url"],
            action="profile_view_enrichment",
            post_url=engager.get("post_url", ""),
            details=f"Enriched: {enriched['company']} / {enriched['title']}",
        )

        logger.info(f"Enriched: {enriched['name']} ({enriched['company']}) — score: {score}")
        return enriched

    def enrich_batch(self, engagers: list) -> list:
        """Enrich a batch of engagers. Returns list of enriched data."""
        results = []
        for engager in engagers:
            result = self.enrich_and_store(engager)
            results.append(result)
        return results

    def _extract_company(self, profile: dict) -> str:
        """Extract current company from profile experience."""
        experiences = profile.get("experiences", []) or profile.get("positions", [])
        if experiences:
            current = experiences[0]  # Usually most recent
            return current.get("company_name", "") or current.get("company", "")
        return ""

    def _score_lead(self, enriched: dict, engager: dict) -> int:
        """
        Score a lead 1-10 based on profile and engagement.
        Higher = better fit for AI VA/Growth Hacker services.
        """
        score = 5  # Base score

        title = (enriched.get("title", "") or "").lower()
        company = (enriched.get("company", "") or "").lower()

        # Title signals
        high_value_titles = ["ceo", "founder", "owner", "coo", "cto", "vp", "director", "head of"]
        mid_value_titles = ["manager", "lead", "principal", "senior"]

        for t in high_value_titles:
            if t in title:
                score += 2
                break
        else:
            for t in mid_value_titles:
                if t in title:
                    score += 1
                    break

        # Engagement depth
        if engager.get("engagement_type") == "comment":
            score += 1  # Comments show more intent than likes
        if engager.get("comment_text", ""):
            if len(engager["comment_text"]) > 100:
                score += 1  # Thoughtful comment

        # Has contact info
        if enriched.get("email"):
            score += 1

        # Cap at 10
        return min(score, 10)
