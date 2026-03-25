"""
Email Outreach — sends laid-back connection emails to engagers
who completed their 7-day LinkedIn sequence without converting.

Trigger: 7 days after LinkedIn sequence started, if no LinkedIn conversation.
Tone: Casual, reference their content + our post they engaged with.
"""

import os
import logging
from datetime import datetime, timezone

from agents.base import BaseAgent
from agents.quality.quality_gate import QualityGate
from tools.airtable_client import AirtableClient

logger = logging.getLogger(__name__)

# Resend API (already used in the content pipeline)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("OUTREACH_FROM_EMAIL", "justin@usingaitoscale.com")
FROM_NAME = os.environ.get("OUTREACH_FROM_NAME", "Justin Bellware")


class EmailOutreach(BaseAgent):
    """
    Generates and sends personalized outreach emails to engagers
    who completed the LinkedIn peekaboo sequence.
    """

    def __init__(self):
        super().__init__(name="email_outreach", prompt_file=None)
        self.airtable = AirtableClient()
        self.quality_gate = QualityGate()

    def process_email_triggers(self) -> dict:
        """
        Find engagers who completed LinkedIn sequence and send emails.
        Returns summary.
        """
        eligible = self.airtable.get_engagers_for_email_trigger()
        if not eligible:
            logger.info("No engagers eligible for email outreach")
            return {"emails_sent": 0, "eligible": 0, "skipped": 0}

        sent = 0
        skipped = 0

        for record in eligible:
            fields = record.get("fields", {})
            email = fields.get("Email", "")
            name = fields.get("Name", "Unknown")
            linkedin_url = fields.get("LinkedIn URL", "")
            posts_engaged = fields.get("Posts Engaged", "")

            if not email:
                skipped += 1
                logger.info(f"Skipping {name} — no email address")
                continue

            # Generate personalized email
            email_content = self._generate_email(name, linkedin_url, posts_engaged, fields)
            if not email_content:
                skipped += 1
                continue

            # Quality check the email
            qr = self.quality_gate.check(email_content["body"], content_type="message")
            if qr.get("verdict") == "FAIL":
                skipped += 1
                logger.warning(f"Email to {name} failed quality gate")
                continue

            final_body = qr.get("final_text", email_content["body"])

            # Send via Resend
            success = self._send_email(
                to_email=email,
                to_name=name,
                subject=email_content["subject"],
                body=final_body,
            )

            if success:
                sent += 1
                # Update AirTable status
                self.airtable._update_record(self.airtable.table_name, record["id"], {
                    "fields": {
                        "Sequence Status": "email_active",
                        "Last Outreach": datetime.now(timezone.utc).isoformat(),
                    }
                })
                self.airtable.log_engagement(
                    linkedin_url=linkedin_url,
                    action="email_outreach",
                    details=f"Subject: {email_content['subject']}",
                )
                logger.info(f"Email sent to {name} ({email})")
            else:
                skipped += 1

        return {"emails_sent": sent, "eligible": len(eligible), "skipped": skipped}

    def _generate_email(self, name: str, linkedin_url: str, posts_engaged: str, fields: dict) -> dict | None:
        """Generate a personalized outreach email."""
        first_name = name.split()[0] if name else "there"
        company = fields.get("Company", "")
        title = fields.get("Title", "")

        prompt = f"""Write a short, casual outreach email to {first_name}.

CONTEXT:
- They engaged with our LinkedIn content (liked/commented on these posts: {posts_engaged[:300]})
- Their company: {company}
- Their title: {title}
- Their LinkedIn: {linkedin_url}
- We've been engaging with their content on LinkedIn for the past week

RULES:
- Subject line: casual, no clickbait, feels like a real person (NOT "Great connecting on LinkedIn!")
- Keep it SHORT — 3-5 sentences max
- Tone: like texting a new professional friend, not a cold email
- Reference that you noticed them on LinkedIn (don't say "I saw you liked my post")
- Find common ground: AI, business growth, operations, whatever fits their title
- NO pitch, NO CTA to book a call, NO mention of services
- End with something low-pressure: a question, a shared interest, or just "would love to stay connected"
- Sign off as Justin

Return JSON with: subject, body (plain text email body, including sign-off)."""

        result = self.call_json(prompt, temperature=0.7)
        if result and result.get("subject") and result.get("body"):
            return result
        return None

    def _send_email(self, to_email: str, to_name: str, subject: str, body: str) -> bool:
        """Send email via Resend API."""
        if not RESEND_API_KEY:
            logger.error("RESEND_API_KEY not set — cannot send outreach email")
            return False

        import requests

        # Build plain text email with HTML formatting
        html_body = body.replace("\n", "<br>")

        payload = {
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "text": body,
            "html": f"<div style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 15px; line-height: 1.6; color: #333;'>{html_body}</div>",
        }

        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            logger.info(f"Email sent via Resend to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Resend email failed to {to_email}: {e}")
            return False
