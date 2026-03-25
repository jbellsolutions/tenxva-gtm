"""Email notification when content pipeline completes.

Supports two backends:
  1. Resend (HTTP API) — works on DigitalOcean (recommended)
  2. Gmail SMTP — works locally but blocked on DO droplets

Set RESEND_API_KEY to use Resend. Falls back to Gmail SMTP if not set.
"""

from __future__ import annotations

import os
import json
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def send_pipeline_report(pipeline_result: dict, date_str: str | None = None) -> dict:
    """Send an email summary of the content pipeline run.

    Tries Resend first (HTTP, works on DO), then falls back to Gmail SMTP.

    Env vars:
        RESEND_API_KEY  - Resend API key (preferred, works on DigitalOcean)
        SMTP_EMAIL      - Gmail address (used as From + fallback SMTP)
        SMTP_PASSWORD   - Gmail app password (fallback if no Resend key)
        NOTIFY_EMAIL    - Where to send notifications
    """
    notify_email = os.environ.get("NOTIFY_EMAIL", "")
    smtp_email = os.environ.get("SMTP_EMAIL", "")
    resend_key = os.environ.get("RESEND_API_KEY", "")

    if not notify_email:
        logger.warning("[email] NOTIFY_EMAIL not set, skipping email notification")
        return {"status": "skipped", "reason": "NOTIFY_EMAIL not configured"}

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    subject, body = _build_email(pipeline_result, date_str)
    html_body = _build_html_email(pipeline_result, date_str)

    # Try Resend first (HTTP — works on DigitalOcean)
    if resend_key:
        # Resend free tier requires sending from onboarding@resend.dev
        resend_from = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")
        return _send_via_resend(resend_key, resend_from,
                                notify_email, subject, body, html_body)

    # Fall back to Gmail SMTP
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    if smtp_email and smtp_password:
        return _send_via_smtp(smtp_email, smtp_password, notify_email,
                              subject, body, html_body)

    logger.warning("[email] No email backend configured (need RESEND_API_KEY or SMTP_EMAIL+SMTP_PASSWORD)")
    return {"status": "skipped", "reason": "No email backend configured"}


def _send_via_resend(api_key: str, from_email: str, to_email: str,
                     subject: str, text: str, html: str) -> dict:
    """Send email via Resend HTTP API (works on DigitalOcean)."""
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"TenXVA Content <{from_email}>",
                "to": [to_email],
                "subject": subject,
                "text": text,
                "html": html,
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info(f"[email] sent via Resend to {to_email}")
            return {"status": "sent", "to": to_email, "backend": "resend"}
        else:
            error = resp.text[:200]
            logger.error(f"[email] Resend failed ({resp.status_code}): {error}")
            return {"status": "error", "error": error, "backend": "resend"}
    except Exception as e:
        logger.error(f"[email] Resend failed: {e}")
        return {"status": "error", "error": str(e), "backend": "resend"}


def _send_via_smtp(smtp_email: str, smtp_password: str, to_email: str,
                   subject: str, text: str, html: str) -> dict:
    """Send email via Gmail SMTP (may not work on DigitalOcean)."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_email
        msg["To"] = to_email
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(smtp_email, smtp_password)
            server.send_message(msg)

        logger.info(f"[email] sent via SMTP to {to_email}")
        return {"status": "sent", "to": to_email, "backend": "smtp"}
    except Exception as e:
        logger.error(f"[email] SMTP failed: {e}")
        return {"status": "error", "error": str(e), "backend": "smtp"}


def _load_reviews(date_str: str) -> dict:
    """Load reviews from per-type files (new pipeline) or reviews.json (old pipeline).

    Returns dict with keys: posts, newsletters, articles — each a list of review dicts.
    """
    project_root = Path(__file__).parent.parent
    drafts_dir = project_root / "data" / "drafts" / date_str
    reviews = {"posts": [], "newsletters": [], "articles": []}

    # Try new per-type review files first
    type_files = {
        "posts": "reviews_posts.json",
        "articles": "reviews_articles.json",
        "newsletters": "reviews_newsletters.json",
    }
    loaded_any = False
    for category, filename in type_files.items():
        fpath = drafts_dir / filename
        if fpath.exists():
            try:
                with open(fpath) as f:
                    data = json.load(f)
                # The per-type file has the same structure: {category: [...]}
                if isinstance(data, dict):
                    reviews[category] = data.get(category, data.get("posts", []))
                elif isinstance(data, list):
                    reviews[category] = data
                loaded_any = True
            except Exception as e:
                logger.warning(f"[email] failed to load {filename}: {e}")

    # Fall back to combined reviews.json if no per-type files found
    if not loaded_any:
        combined_path = drafts_dir / "reviews.json"
        if combined_path.exists():
            try:
                with open(combined_path) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for cat in ["posts", "newsletters", "articles"]:
                        reviews[cat] = data.get(cat, [])
            except Exception as e:
                logger.warning(f"[email] failed to load reviews.json: {e}")

    return reviews


def _get_result_counts(result: dict) -> dict:
    """Extract counts from result dict, supporting both old and new key formats.

    Old format: approved, rejected, posts, newsletters, articles
    New format: posts_approved, posts_quota, articles_approved, articles_quota, etc.
    """
    # Check if new-format keys exist
    has_new_keys = "posts_approved" in result

    if has_new_keys:
        posts_approved = result.get("posts_approved", 0)
        articles_approved = result.get("articles_approved", 0)
        newsletters_approved = result.get("newsletters_approved", 0)
        total_approved = posts_approved + articles_approved + newsletters_approved
        return {
            "total_approved": total_approved,
            "posts_approved": posts_approved,
            "posts_quota": result.get("posts_quota", 0),
            "articles_approved": articles_approved,
            "articles_quota": result.get("articles_quota", 0),
            "newsletters_approved": newsletters_approved,
            "newsletter_day": result.get("newsletter_day", False),
            "total_queued": result.get("total_queued", 0),
            "fact_check": result.get("fact_check", {}),
            "new_format": True,
        }
    else:
        return {
            "total_approved": result.get("approved", 0),
            "posts_approved": result.get("approved", 0),
            "posts_quota": 0,
            "articles_approved": 0,
            "articles_quota": 0,
            "newsletters_approved": 0,
            "newsletter_day": False,
            "total_queued": result.get("published", 0),
            "fact_check": {},
            "new_format": False,
        }


def _build_email(result: dict, date_str: str) -> tuple[str, str]:
    """Build email subject and plain text body."""
    status = result.get("status", "unknown")
    counts = _get_result_counts(result)
    dashboard_url = os.environ.get("DASHBOARD_URL", "http://104.131.172.48:8080")

    if status == "success":
        if counts["new_format"]:
            parts = [f"{counts['posts_approved']}/{counts['posts_quota']} posts"]
            if counts["articles_quota"] > 0:
                parts.append(f"{counts['articles_approved']}/{counts['articles_quota']} articles")
            if counts["newsletter_day"]:
                parts.append(f"{counts['newsletters_approved']} newsletter")
            subject = f"TenXVA Content Ready — {date_str} — {', '.join(parts)}"
        else:
            subject = f"TenXVA Content Ready — {date_str} — {counts['total_approved']} approved"
    elif status == "error":
        subject = f"TenXVA Content FAILED — {date_str}"
    else:
        subject = f"TenXVA Content — {date_str} — {status}"

    lines = [
        f"TenXVA Content Pipeline Report",
        f"Date: {date_str} ({result.get('day', '')})",
        f"Status: {status.upper()}",
        f"",
        f"Review all content: {dashboard_url}",
        f"",
    ]

    if counts["new_format"]:
        lines.extend([
            f"--- Quotas ---",
            f"Posts:       {counts['posts_approved']}/{counts['posts_quota']} approved",
            f"Articles:    {counts['articles_approved']}/{counts['articles_quota']} approved",
            f"Newsletters: {counts['newsletters_approved']} ({'newsletter day' if counts['newsletter_day'] else 'not a newsletter day'})",
            f"Total queued: {counts['total_queued']}",
            f"",
        ])
        fc = counts.get("fact_check", {})
        if fc:
            lines.extend([
                f"--- Fact Check ---",
                f"Pass: {fc.get('pass', 0)}, Flag: {fc.get('flag', 0)}, Fail: {fc.get('fail', 0)}, Skip: {fc.get('skipped', 0)}",
                f"",
            ])
    else:
        lines.extend([
            f"--- Results ---",
            f"Trends identified: {result.get('trends', 0)}",
            f"Briefs created: {result.get('briefs', 0)}",
            f"Posts written: {result.get('posts', 0)}",
            f"Newsletters: {result.get('newsletters', 0)}",
            f"Articles: {result.get('articles', 0)}",
            f"Approved: {counts['total_approved']}",
            f"Rejected: {result.get('rejected', 0)}",
            f"Published: {result.get('published', 0)}",
            f"",
        ])

    lines.append(f"Trends: {result.get('trends', 0)}")
    lines.append(f"Pipeline time: {result.get('elapsed_seconds', 0):.0f} seconds")
    lines.append("")

    # Read the actual approved content from review files
    reviews = _load_reviews(date_str)

    approved_posts = [p for p in reviews.get("posts", []) if p.get("verdict") == "APPROVED"]
    if approved_posts:
        lines.append("--- APPROVED POSTS ---")
        lines.append("")
        for i, post in enumerate(approved_posts, 1):
            lines.append(f"POST {i} (Score: {post.get('score', '?')})")
            lines.append("-" * 40)
            lines.append(post.get("final_text", "No text available"))
            lines.append("")
            lines.append(f"Editor: {post.get('notes', 'No notes')}")
            lines.append("")
            lines.append("=" * 50)
            lines.append("")

    # Rejected posts
    rejected_posts = [p for p in reviews.get("posts", []) if p.get("verdict") == "REJECTED"]
    if rejected_posts:
        lines.append("--- REJECTED POSTS ---")
        for rp in rejected_posts:
            lines.append(f"  {rp.get('content_id', '?')} (Score: {rp.get('score', '?')})")
            for issue in rp.get("issues", []):
                lines.append(f"    - {issue}")
            lines.append("")

    # Long-form content
    for category in ["newsletters", "articles"]:
        items = reviews.get(category, [])
        approved_items = [x for x in items if x.get("verdict") == "APPROVED"]
        if approved_items:
            lines.append(f"--- APPROVED {category.upper()} ---")
            for item in approved_items:
                lines.append(f"Score: {item.get('score', '?')}")
                text = item.get("final_text", "")
                lines.append(text[:1500] if text else "No text")
                lines.append("")

    lines.append("")
    lines.append(f"Review dashboard: {dashboard_url}")
    lines.append("— TenXVA GTM System (Automated)")

    return subject, "\n".join(lines)


def _build_html_email(result: dict, date_str: str) -> str:
    """Build an HTML email body."""
    status = result.get("status", "unknown")
    counts = _get_result_counts(result)

    dashboard_url = os.environ.get("DASHBOARD_URL", "http://104.131.172.48:8080")
    status_color = "#22c55e" if status == "success" else "#ef4444"

    # Build status banner text
    if counts["new_format"]:
        banner_parts = []
        banner_parts.append(f"{counts['posts_approved']}/{counts['posts_quota']} posts")
        if counts["articles_quota"] > 0:
            banner_parts.append(f"{counts['articles_approved']}/{counts['articles_quota']} articles")
        if counts["newsletter_day"]:
            banner_parts.append(f"{counts['newsletters_approved']} newsletter")
        banner_text = f"{status.upper()} — {', '.join(banner_parts)} | {counts['total_queued']} queued"
    else:
        banner_text = f"{status.upper()} — {counts['total_approved']} approved"

    html_parts = [f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <h1 style="font-size: 24px; margin-bottom: 5px;">TenXVA Content Pipeline</h1>
        <p style="color: #666; margin-top: 0;">{date_str} ({result.get('day', '')})</p>

        <div style="background: {status_color}; color: white; padding: 12px 20px; border-radius: 8px; margin: 15px 0;">
            <strong>{banner_text}</strong>
        </div>

        <a href="{dashboard_url}" style="display: inline-block; background: #3b82f6; color: white; padding: 10px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; margin-bottom: 15px;">Open Dashboard &rarr;</a>
    """]

    # Quota table for new format
    if counts["new_format"]:
        fc = counts.get("fact_check", {})
        html_parts.append(f"""
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Trends</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{result.get('trends', 0)}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Posts</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{counts['posts_approved']}/{counts['posts_quota']}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Articles</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{counts['articles_approved']}/{counts['articles_quota']}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Newsletters</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{counts['newsletters_approved']} {'&#10004;' if counts['newsletter_day'] else '(not today)'}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Fact Check</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{fc.get('pass', 0)} pass, {fc.get('flag', 0)} flag, {fc.get('fail', 0)} fail</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Total Queued</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{counts['total_queued']}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Pipeline Time</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{result.get('elapsed_seconds', 0):.0f}s</td></tr>
        </table>
        """)
    else:
        html_parts.append(f"""
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Trends</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{result.get('trends', 0)}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Posts</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{result.get('posts', 0)}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Newsletters</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{result.get('newsletters', 0)}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Articles</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{result.get('articles', 0)}</td></tr>
            <tr><td style="padding: 6px 12px; border-bottom: 1px solid #eee;">Pipeline Time</td><td style="padding: 6px 12px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{result.get('elapsed_seconds', 0):.0f}s</td></tr>
        </table>
        """)

    # Load and display approved content from review files
    reviews = _load_reviews(date_str)

    approved_posts = [p for p in reviews.get("posts", []) if p.get("verdict") == "APPROVED"]
    if approved_posts:
        html_parts.append('<h2 style="font-size: 18px; margin-top: 25px;">Approved Posts</h2>')
        for i, post in enumerate(approved_posts, 1):
            score = post.get("score", "?")
            score_color = "#22c55e" if isinstance(score, int) and score >= 85 else "#f59e0b"
            text = (post.get("final_text", "No text") or "No text").replace("\n", "<br>")
            notes = post.get("notes", "")
            html_parts.append(f"""
            <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 12px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <span style="font-weight: bold;">Post {i}</span>
                    <span style="background: {score_color}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 13px;">Score: {score}</span>
                </div>
                <div style="background: #f9fafb; padding: 12px; border-radius: 6px; font-size: 14px; line-height: 1.6;">
                    {text}
                </div>
                <p style="color: #666; font-size: 12px; margin-top: 8px; font-style: italic;">{notes}</p>
            </div>
            """)

    # Rejected posts
    rejected_posts = [p for p in reviews.get("posts", []) if p.get("verdict") == "REJECTED"]
    if rejected_posts:
        html_parts.append('<h3 style="font-size: 15px; color: #ef4444; margin-top: 20px;">Rejected</h3>')
        for rp in rejected_posts:
            issues = "<br>".join(f"- {iss}" for iss in rp.get("issues", []))
            html_parts.append(f"""
            <div style="border-left: 3px solid #ef4444; padding: 8px 12px; margin: 8px 0; font-size: 13px; color: #666;">
                <strong>{rp.get('content_id', '?')}</strong> (Score: {rp.get('score', '?')})<br>{issues}
            </div>
            """)

    # Long-form content
    for category in ["newsletters", "articles"]:
        items = reviews.get(category, [])
        approved_items = [x for x in items if x.get("verdict") == "APPROVED"]
        if approved_items:
            html_parts.append(f'<h2 style="font-size: 18px; margin-top: 25px;">Approved {category.title()}</h2>')
            for item in approved_items:
                text = (item.get("final_text", "") or "")[:1500].replace("\n", "<br>")
                html_parts.append(f"""
                <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 12px 0;">
                    <span style="background: #22c55e; color: white; padding: 2px 10px; border-radius: 12px; font-size: 13px;">Score: {item.get('score', '?')}</span>
                    <div style="background: #f9fafb; padding: 12px; border-radius: 6px; font-size: 14px; line-height: 1.6; margin-top: 10px;">
                        {text}
                    </div>
                </div>
                """)

    html_parts.append(f"""
        <hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">
        <a href="{dashboard_url}" style="color: #3b82f6; text-decoration: none;">Open Dashboard &rarr;</a>
        <p style="color: #999; font-size: 12px; margin-top: 10px;">TenXVA GTM System (Automated)</p>
    </div>
    """)

    return "\n".join(html_parts)
