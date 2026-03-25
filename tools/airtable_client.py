"""
AirTable Engager Database — tracks everyone who engages with our LinkedIn content.

Schema (auto-created if not exists):
- Name: full name
- LinkedIn URL: profile URL
- Email: enriched email
- Phone: enriched phone
- Company: current company
- Title: job title
- First Engaged: date of first engagement
- Last Engaged: date of most recent engagement
- Engagement Type: like, comment, share, view
- Engagement Count: total interactions
- Post Engaged: which of our posts they engaged with
- Sequence Status: none, linkedin_active, linkedin_complete, email_active, email_complete, converted
- Sequence Day: current day in sequence (1-7)
- Sequence Start: when sequence started
- Connection Sent: whether we sent a connection request
- Connection Status: none, sent, accepted
- Last Outreach: date of last outreach action
- Score: lead quality score (1-10)
- Notes: any relevant notes
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

AIRTABLE_API_URL = "https://api.airtable.com/v0"


class AirtableClient:
    """AirTable client for the LinkedIn engager database."""

    def __init__(self):
        self.pat = os.environ.get("AIRTABLE_PAT", "")
        self.base_id = os.environ.get("AIRTABLE_BASE_ID", "")
        self.table_name = os.environ.get("AIRTABLE_TABLE_NAME", "Engagers")

        if not self.pat:
            logger.warning("AIRTABLE_PAT not set")

        self.headers = {
            "Authorization": f"Bearer {self.pat}",
            "Content-Type": "application/json",
        }

    # ─── Setup ─────────────────────────────────────────────────────────

    def ensure_base_exists(self) -> str:
        """Create the AirTable base if it doesn't exist. Returns base_id."""
        if self.base_id:
            return self.base_id

        # List existing bases to find ours
        resp = requests.get(
            "https://api.airtable.com/v0/meta/bases",
            headers=self.headers,
            timeout=15,
        )
        if resp.ok:
            bases = resp.json().get("bases", [])
            for base in bases:
                if base.get("name") == "TenXVA LinkedIn Engagement":
                    self.base_id = base["id"]
                    logger.info(f"Found existing AirTable base: {self.base_id}")
                    return self.base_id

        # Create new base with schema
        body = {
            "name": "TenXVA LinkedIn Engagement",
            "tables": [
                {
                    "name": "Engagers",
                    "fields": [
                        {"name": "Name", "type": "singleLineText"},
                        {"name": "LinkedIn URL", "type": "url"},
                        {"name": "Email", "type": "email"},
                        {"name": "Phone", "type": "phoneNumber"},
                        {"name": "Company", "type": "singleLineText"},
                        {"name": "Title", "type": "singleLineText"},
                        {"name": "First Engaged", "type": "dateTime", "options": {"timeZone": "America/New_York", "dateFormat": {"name": "us"}}},
                        {"name": "Last Engaged", "type": "dateTime", "options": {"timeZone": "America/New_York", "dateFormat": {"name": "us"}}},
                        {"name": "Engagement Type", "type": "singleLineText"},
                        {"name": "Engagement Count", "type": "number", "options": {"precision": 0}},
                        {"name": "Posts Engaged", "type": "multilineText"},
                        {"name": "Sequence Status", "type": "singleSelect", "options": {"choices": [
                            {"name": "none", "color": "grayLight2"},
                            {"name": "linkedin_active", "color": "blueLight2"},
                            {"name": "linkedin_complete", "color": "blueDark1"},
                            {"name": "email_active", "color": "yellowLight2"},
                            {"name": "email_complete", "color": "greenLight2"},
                            {"name": "converted", "color": "greenDark1"},
                        ]}},
                        {"name": "Sequence Day", "type": "number", "options": {"precision": 0}},
                        {"name": "Sequence Start", "type": "dateTime", "options": {"timeZone": "America/New_York", "dateFormat": {"name": "us"}}},
                        {"name": "Connection Sent", "type": "checkbox"},
                        {"name": "Connection Status", "type": "singleSelect", "options": {"choices": [
                            {"name": "none", "color": "grayLight2"},
                            {"name": "sent", "color": "yellowLight2"},
                            {"name": "accepted", "color": "greenLight2"},
                        ]}},
                        {"name": "Last Outreach", "type": "dateTime", "options": {"timeZone": "America/New_York", "dateFormat": {"name": "us"}}},
                        {"name": "Score", "type": "number", "options": {"precision": 0}},
                        {"name": "Notes", "type": "multilineText"},
                    ],
                },
                {
                    "name": "Engagement Log",
                    "fields": [
                        {"name": "Engager LinkedIn URL", "type": "url"},
                        {"name": "Action", "type": "singleLineText"},
                        {"name": "Post URL", "type": "url"},
                        {"name": "Timestamp", "type": "dateTime", "options": {"timeZone": "America/New_York", "dateFormat": {"name": "us"}}},
                        {"name": "Details", "type": "multilineText"},
                    ],
                },
                {
                    "name": "Outreach Sequences",
                    "fields": [
                        {"name": "Engager LinkedIn URL", "type": "url"},
                        {"name": "Day", "type": "number", "options": {"precision": 0}},
                        {"name": "Action Type", "type": "singleLineText"},
                        {"name": "Action Details", "type": "multilineText"},
                        {"name": "Status", "type": "singleSelect", "options": {"choices": [
                            {"name": "pending", "color": "grayLight2"},
                            {"name": "completed", "color": "greenLight2"},
                            {"name": "skipped", "color": "yellowLight2"},
                            {"name": "failed", "color": "redLight2"},
                        ]}},
                        {"name": "Scheduled For", "type": "dateTime", "options": {"timeZone": "America/New_York", "dateFormat": {"name": "us"}}},
                        {"name": "Completed At", "type": "dateTime", "options": {"timeZone": "America/New_York", "dateFormat": {"name": "us"}}},
                    ],
                },
            ],
        }
        resp = requests.post(
            "https://api.airtable.com/v0/meta/bases",
            headers=self.headers,
            json=body,
            timeout=30,
        )
        if resp.ok:
            self.base_id = resp.json()["id"]
            logger.info(f"Created AirTable base: {self.base_id}")
            return self.base_id
        else:
            logger.error(f"Failed to create AirTable base: {resp.status_code} {resp.text[:500]}")
            return ""

    # ─── Engager CRUD ──────────────────────────────────────────────────

    def find_engager(self, linkedin_url: str) -> Optional[dict]:
        """Find an engager by LinkedIn URL. Returns record or None."""
        if not self.base_id:
            self.ensure_base_exists()
        url = f"{AIRTABLE_API_URL}/{self.base_id}/{self.table_name}"
        params = {
            "filterByFormula": f'{{LinkedIn URL}} = "{linkedin_url}"',
            "maxRecords": 1,
        }
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=15)
            resp.raise_for_status()
            records = resp.json().get("records", [])
            return records[0] if records else None
        except Exception as e:
            logger.error(f"AirTable find_engager error: {e}")
            return None

    def add_engager(self, data: dict) -> Optional[dict]:
        """
        Add a new engager or update existing one.
        data keys: name, linkedin_url, email, phone, company, title,
                   engagement_type, post_url, score
        """
        if not self.base_id:
            self.ensure_base_exists()

        linkedin_url = data.get("linkedin_url", "")
        existing = self.find_engager(linkedin_url)
        now = datetime.now(timezone.utc).isoformat()

        if existing:
            # Update existing — increment count, update last engaged
            record_id = existing["id"]
            fields = existing.get("fields", {})
            count = fields.get("Engagement Count", 0) or 0
            posts = fields.get("Posts Engaged", "") or ""
            post_url = data.get("post_url", "")
            if post_url and post_url not in posts:
                posts = f"{posts}\n{post_url}".strip()

            updates = {
                "fields": {
                    "Last Engaged": now,
                    "Engagement Count": count + 1,
                    "Posts Engaged": posts,
                }
            }
            # Update enrichment data if provided
            if data.get("email") and not fields.get("Email"):
                updates["fields"]["Email"] = data["email"]
            if data.get("phone") and not fields.get("Phone"):
                updates["fields"]["Phone"] = data["phone"]
            if data.get("company") and not fields.get("Company"):
                updates["fields"]["Company"] = data["company"]
            if data.get("title") and not fields.get("Title"):
                updates["fields"]["Title"] = data["title"]

            return self._update_record(self.table_name, record_id, updates)
        else:
            # Create new engager
            record = {
                "fields": {
                    "Name": data.get("name", "Unknown"),
                    "LinkedIn URL": linkedin_url,
                    "Email": data.get("email", ""),
                    "Phone": data.get("phone", ""),
                    "Company": data.get("company", ""),
                    "Title": data.get("title", ""),
                    "First Engaged": now,
                    "Last Engaged": now,
                    "Engagement Type": data.get("engagement_type", "like"),
                    "Engagement Count": 1,
                    "Posts Engaged": data.get("post_url", ""),
                    "Sequence Status": "none",
                    "Sequence Day": 0,
                    "Connection Sent": False,
                    "Connection Status": "none",
                    "Score": data.get("score", 5),
                    "Notes": "",
                }
            }
            return self._create_record(self.table_name, record)

    def get_active_sequences(self, status: str = "linkedin_active") -> list:
        """Get all engagers currently in a sequence."""
        return self._query(self.table_name, f'{{Sequence Status}} = "{status}"')

    def get_engagers_for_email_trigger(self, days_since_start: int = 7) -> list:
        """
        Get engagers who completed LinkedIn sequence (7 days)
        and haven't started email yet.
        """
        return self._query(
            self.table_name,
            '{Sequence Status} = "linkedin_complete"'
        )

    def get_engagers_for_recurring(self) -> list:
        """Get all engagers in our database for recurring engagement."""
        return self._query(
            self.table_name,
            'NOT({Sequence Status} = "converted")',
            sort=[{"field": "Last Engaged", "direction": "desc"}],
        )

    def start_sequence(self, linkedin_url: str) -> bool:
        """Start LinkedIn peekaboo sequence for an engager."""
        record = self.find_engager(linkedin_url)
        if not record:
            return False
        now = datetime.now(timezone.utc).isoformat()
        self._update_record(self.table_name, record["id"], {
            "fields": {
                "Sequence Status": "linkedin_active",
                "Sequence Day": 1,
                "Sequence Start": now,
            }
        })
        return True

    def advance_sequence(self, linkedin_url: str) -> int:
        """Advance sequence day by 1. Returns new day number."""
        record = self.find_engager(linkedin_url)
        if not record:
            return 0
        fields = record.get("fields", {})
        current_day = fields.get("Sequence Day", 0) or 0
        new_day = current_day + 1

        updates = {"Sequence Day": new_day, "Last Outreach": datetime.now(timezone.utc).isoformat()}
        if new_day > 7:
            updates["Sequence Status"] = "linkedin_complete"

        self._update_record(self.table_name, record["id"], {"fields": updates})
        return new_day

    def mark_connection_sent(self, linkedin_url: str) -> bool:
        """Mark that we sent a connection request."""
        record = self.find_engager(linkedin_url)
        if not record:
            return False
        self._update_record(self.table_name, record["id"], {
            "fields": {
                "Connection Sent": True,
                "Connection Status": "sent",
            }
        })
        return True

    def update_score(self, linkedin_url: str, score: int) -> bool:
        """Update lead quality score (1-10)."""
        record = self.find_engager(linkedin_url)
        if not record:
            return False
        self._update_record(self.table_name, record["id"], {
            "fields": {"Score": min(max(score, 1), 10)}
        })
        return True

    # ─── Engagement Log ────────────────────────────────────────────────

    def log_engagement(self, linkedin_url: str, action: str, post_url: str = "", details: str = "") -> Optional[dict]:
        """Log an engagement action (view, like, comment, endorse, etc.)."""
        record = {
            "fields": {
                "Engager LinkedIn URL": linkedin_url,
                "Action": action,
                "Post URL": post_url,
                "Timestamp": datetime.now(timezone.utc).isoformat(),
                "Details": details,
            }
        }
        return self._create_record("Engagement Log", record)

    # ─── Outreach Sequences ────────────────────────────────────────────

    def schedule_sequence_action(self, linkedin_url: str, day: int, action_type: str,
                                  details: str, scheduled_for: str) -> Optional[dict]:
        """Schedule a sequence action for a specific day."""
        record = {
            "fields": {
                "Engager LinkedIn URL": linkedin_url,
                "Day": day,
                "Action Type": action_type,
                "Action Details": details,
                "Status": "pending",
                "Scheduled For": scheduled_for,
            }
        }
        return self._create_record("Outreach Sequences", record)

    def get_due_sequence_actions(self) -> list:
        """Get sequence actions that are due to execute."""
        now = datetime.now(timezone.utc).isoformat()
        return self._query(
            "Outreach Sequences",
            f'AND({{Status}} = "pending", IS_BEFORE({{Scheduled For}}, "{now}"))',
        )

    def complete_sequence_action(self, record_id: str) -> bool:
        """Mark a sequence action as completed."""
        now = datetime.now(timezone.utc).isoformat()
        result = self._update_record("Outreach Sequences", record_id, {
            "fields": {"Status": "completed", "Completed At": now}
        })
        return result is not None

    # ─── Stats ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get engagement database stats."""
        all_engagers = self._query(self.table_name, "")
        stats = {
            "total_engagers": len(all_engagers),
            "linkedin_active": 0,
            "linkedin_complete": 0,
            "email_active": 0,
            "converted": 0,
            "connections_sent": 0,
            "avg_score": 0,
        }
        total_score = 0
        for r in all_engagers:
            f = r.get("fields", {})
            status = f.get("Sequence Status", "none")
            if status == "linkedin_active":
                stats["linkedin_active"] += 1
            elif status == "linkedin_complete":
                stats["linkedin_complete"] += 1
            elif status == "email_active":
                stats["email_active"] += 1
            elif status == "converted":
                stats["converted"] += 1
            if f.get("Connection Sent"):
                stats["connections_sent"] += 1
            total_score += f.get("Score", 0) or 0

        if all_engagers:
            stats["avg_score"] = round(total_score / len(all_engagers), 1)
        return stats

    # ─── Internal Helpers ──────────────────────────────────────────────

    def _create_record(self, table: str, record: dict) -> Optional[dict]:
        """Create a single record."""
        url = f"{AIRTABLE_API_URL}/{self.base_id}/{table}"
        try:
            resp = requests.post(url, headers=self.headers, json=record, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"AirTable create error ({table}): {e}")
            return None

    def _update_record(self, table: str, record_id: str, updates: dict) -> Optional[dict]:
        """Update a single record."""
        url = f"{AIRTABLE_API_URL}/{self.base_id}/{table}/{record_id}"
        try:
            resp = requests.patch(url, headers=self.headers, json=updates, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"AirTable update error ({table}/{record_id}): {e}")
            return None

    def _query(self, table: str, formula: str, sort: list = None) -> list:
        """Query records with optional filter formula."""
        url = f"{AIRTABLE_API_URL}/{self.base_id}/{table}"
        all_records = []
        offset = None

        while True:
            params = {}
            if formula:
                params["filterByFormula"] = formula
            if sort:
                for i, s in enumerate(sort):
                    params[f"sort[{i}][field]"] = s["field"]
                    params[f"sort[{i}][direction]"] = s.get("direction", "asc")
            if offset:
                params["offset"] = offset

            try:
                resp = requests.get(url, headers=self.headers, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                all_records.extend(data.get("records", []))
                offset = data.get("offset")
                if not offset:
                    break
            except Exception as e:
                logger.error(f"AirTable query error ({table}): {e}")
                break

        return all_records
