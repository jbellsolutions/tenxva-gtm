"""Swipe file reader — searches the 5,716 email swipe file for relevant examples.

Data sources:
- swipe_database.json: Full database with 302 emails that have body content
- swipe_compact.json: All 5,716 subject lines organized by sender
- style_analysis.json: Statistical style profiles per copywriter
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to the swipe file data
SWIPE_DIR = Path(__file__).parent.parent / "data" / "swipe-file"
# Fallback to the original location if data hasn't been copied
SWIPE_DIR_ORIGINAL = Path(__file__).parent.parent.parent / "swipe-file"

_database = None
_compact = None
_styles = None


def _get_swipe_dir() -> Path:
    """Return whichever swipe directory exists."""
    if SWIPE_DIR.exists() and (SWIPE_DIR / "swipe_database.json").exists():
        return SWIPE_DIR
    return SWIPE_DIR_ORIGINAL


def _load_database() -> dict:
    global _database
    if _database is None:
        path = _get_swipe_dir() / "swipe_database.json"
        with open(path) as f:
            _database = json.load(f)
    return _database


def _load_compact() -> dict:
    global _compact
    if _compact is None:
        path = _get_swipe_dir() / "swipe_compact.json"
        with open(path) as f:
            _compact = json.load(f)
    return _compact


def _load_styles() -> dict:
    global _styles
    if _styles is None:
        path = _get_swipe_dir() / "style_analysis.json"
        with open(path) as f:
            _styles = json.load(f)
    return _styles


def get_style_profile(copywriter_key: str) -> dict | None:
    """Get the statistical style profile for a copywriter.

    Keys: brian_kurtz, jay_abraham, todd_brown, alex_hormozi,
          tom_bilyeu, lead_gen_jay, liam_ottley, bill_mueller, jon_buchan
    """
    styles = _load_styles()
    return styles.get(copywriter_key)


def get_all_styles() -> dict:
    """Get all copywriter style profiles."""
    return _load_styles()


def get_subjects_by_sender(sender_key: str, limit: int = 20) -> list[str]:
    """Get subject lines from a specific copywriter."""
    compact = _load_compact()
    sender = compact.get("senders", {}).get(sender_key, {})
    subjects = sender.get("subjects", [])
    return subjects[:limit]


def get_emails_with_body(sender_key: str | None = None, limit: int = 10) -> list[dict]:
    """Get emails that have full body content (302 total across all senders).

    Returns list of dicts with: id, subject, date, body
    """
    db = _load_database()
    results = []
    senders = db.get("senders", {})

    if sender_key:
        sender_keys = [sender_key] if sender_key in senders else []
    else:
        sender_keys = list(senders.keys())

    for key in sender_keys:
        sender = senders[key]
        for email in sender.get("emails", []):
            if email.get("has_full_content") and email.get("body"):
                results.append({
                    "sender": sender["display_name"],
                    "sender_key": key,
                    "subject": email["subject"],
                    "date": email.get("date", ""),
                    "body": email["body"],
                })
                if len(results) >= limit:
                    return results
    return results


def search_subjects(query: str, limit: int = 15) -> list[dict]:
    """Search all 5,716 subject lines for keywords.

    Returns list of dicts with: sender, sender_key, subject
    """
    query_lower = query.lower()
    terms = query_lower.split()
    compact = _load_compact()
    results = []

    for sender_key, sender in compact.get("senders", {}).items():
        for subject in sender.get("subjects", []):
            subject_lower = subject.lower()
            if all(term in subject_lower for term in terms):
                results.append({
                    "sender": sender["name"],
                    "sender_key": sender_key,
                    "subject": subject,
                })
                if len(results) >= limit:
                    return results
    return results


def search_body_content(query: str, limit: int = 5) -> list[dict]:
    """Search the 302 full-body emails for keywords.

    Returns list of dicts with: sender, subject, body (truncated to 500 chars)
    """
    query_lower = query.lower()
    terms = query_lower.split()
    db = _load_database()
    results = []

    for sender_key, sender in db.get("senders", {}).items():
        for email in sender.get("emails", []):
            body = email.get("body", "")
            if not body:
                continue
            body_lower = body.lower()
            if all(term in body_lower for term in terms):
                results.append({
                    "sender": sender["display_name"],
                    "sender_key": sender_key,
                    "subject": email["subject"],
                    "body_preview": body[:500],
                    "body_full": body,
                })
                if len(results) >= limit:
                    return results
    return results


def get_swipe_context_for_brief(
    topic: str,
    copywriter_keys: list[str],
    max_subjects: int = 10,
    max_body_examples: int = 3,
) -> str:
    """Build a context string for content briefs.

    Combines: style profiles + relevant subjects + body examples
    Returns a formatted string ready to inject into a Claude prompt.
    """
    sections = []

    # Style profiles for requested copywriters
    for key in copywriter_keys:
        profile = get_style_profile(key)
        if profile:
            sections.append(
                f"## {profile['name']} Style Profile\n"
                f"- Total emails analyzed: {profile['total']}\n"
                f"- Avg subject length: {profile['avg_subject_length']} chars\n"
                f"- Questions: {profile['questions_pct']}% | Curiosity: {profile['curiosity_pct']}% | "
                f"Numbers: {profile['numbers_pct']}% | Story: {profile['story_pct']}%\n"
                f"- Sample subjects: {', '.join(profile['sample_subjects'][:5])}\n"
            )

    # Search for relevant subjects
    subject_results = search_subjects(topic, limit=max_subjects)
    if subject_results:
        lines = [f"## Relevant Subject Lines (matching '{topic}')"]
        for r in subject_results:
            lines.append(f"- [{r['sender']}] {r['subject']}")
        sections.append("\n".join(lines))

    # Search for relevant body content
    body_results = search_body_content(topic, limit=max_body_examples)
    if body_results:
        lines = [f"## Relevant Email Examples (matching '{topic}')"]
        for r in body_results:
            lines.append(f"\n### [{r['sender']}] {r['subject']}\n{r['body_preview']}...")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def get_sender_summary() -> str:
    """Get a quick summary of all senders in the swipe file."""
    compact = _load_compact()
    lines = [f"Swipe File: {compact['total']} total emails, {compact['full_content']} with full body content\n"]
    for key, sender in compact.get("senders", {}).items():
        lines.append(f"- {sender['name']} ({key}): {sender['count']} emails — {sender.get('specialty', 'N/A')}")
    return "\n".join(lines)
