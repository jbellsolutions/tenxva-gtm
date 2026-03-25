"""
Connection Manager — sends top 5 connection requests per day (no message).

Selects the 5 highest-scored engagers who:
- Haven't received a connection request yet
- Have been in our database at least 1 day
- Score >= 6
"""

import logging
from datetime import datetime, timezone

from tools.unipile_client import UnipileClient
from tools.airtable_client import AirtableClient

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_DAY = 5
MIN_SCORE_FOR_CONNECTION = 6


class ConnectionManager:
    """Sends daily connection requests to top-scored engagers."""

    def __init__(self):
        self.unipile = UnipileClient()
        self.airtable = AirtableClient()

    def send_daily_connections(self) -> dict:
        """
        Select top 5 engagers and send connection requests (no message).
        Returns summary.
        """
        # Get candidates: not already sent, score >= threshold
        candidates = self.airtable._query(
            self.airtable.table_name,
            f'AND({{Connection Sent}} = FALSE(), {{Score}} >= {MIN_SCORE_FOR_CONNECTION})',
            sort=[{"field": "Score", "direction": "desc"}],
        )

        if not candidates:
            logger.info("No connection request candidates found")
            return {"sent": 0, "candidates": 0}

        sent = 0
        for record in candidates[:MAX_CONNECTIONS_PER_DAY]:
            fields = record.get("fields", {})
            linkedin_url = fields.get("LinkedIn URL", "")
            name = fields.get("Name", "Unknown")
            score = fields.get("Score", 0)

            if not linkedin_url:
                continue

            # Send connection request with NO message
            result = self.unipile.send_connection_request(linkedin_url, message=None)
            if result:
                self.airtable.mark_connection_sent(linkedin_url)
                self.airtable.log_engagement(
                    linkedin_url=linkedin_url,
                    action="connection_request",
                    details=f"Score: {score}, no message attached",
                )
                sent += 1
                logger.info(f"Connection request sent to {name} (score: {score})")
            else:
                logger.warning(f"Failed to send connection request to {name}")

        return {
            "sent": sent,
            "candidates": len(candidates),
            "top_scores": [r.get("fields", {}).get("Score", 0) for r in candidates[:MAX_CONNECTIONS_PER_DAY]],
        }
