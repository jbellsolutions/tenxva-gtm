"""Posting queue — manages approved content waiting to be posted at strategic times.

All content flows through this queue:
  1. Pipeline generates → quality editor scores → fact checker verifies → APPROVED
  2. Publisher routes approved content here with content_type and scheduled time
  3. Auto-poster checks queue every 15 min → posts via PhantomBuster when due
  4. Post status updates: queued → posting → posted / failed

Content types and their daily posting slots (ET):
  post:       09:00, 15:00          (2/day)
  article:    10:30                 (1/day, Mon-Fri)
  newsletter: 08:00                 (Mon/Wed/Fri)

Queue file: data/posting-queue/queue.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
QUEUE_DIR = PROJECT_ROOT / "data" / "posting-queue"
QUEUE_FILE = QUEUE_DIR / "queue.json"

# Typed posting slots — each content type has its own schedule (ET)
# Updated March 16: Less volume, higher quality
POSTING_SLOTS = {
    "post": ["09:00"],                # 1 authority post per day
    "article": ["10:30"],             # 1 article (Tue + Thu only)
    "newsletter": ["08:00"],          # 1 newsletter (Wed only)
}

# Flat list for backward compatibility
ALL_SLOTS = sorted(
    slot for slots in POSTING_SLOTS.values() for slot in slots
)


def _ensure_dir():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def _load_queue() -> list[dict]:
    _ensure_dir()
    if QUEUE_FILE.exists():
        try:
            with open(QUEUE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_queue(queue: list[dict]):
    _ensure_dir()
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2, default=str)


def _next_slot(content_type: str = "post") -> str:
    """Find the next available posting slot for a given content type.

    Looks at what's already queued/posted today for this content_type
    and picks the next open slot. If all slots today are taken or past,
    picks the first slot tomorrow.
    """
    queue = _load_queue()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    slots = POSTING_SLOTS.get(content_type, POSTING_SLOTS["post"])

    # Find which slots are taken today for this content_type
    taken_times = set()
    for item in queue:
        if item.get("status") in ("queued", "posting", "posted"):
            if item.get("content_type", "post") != content_type:
                continue
            sched = item.get("scheduled_for", "")
            if sched.startswith(today):
                try:
                    t = sched.split("T")[1][:5]
                    taken_times.add(t)
                except (IndexError, ValueError):
                    pass

    # Find next open slot today
    for slot in slots:
        if slot not in taken_times:
            slot_dt = datetime.strptime(f"{today}T{slot}", "%Y-%m-%dT%H:%M")
            if slot_dt > now:
                return f"{today}T{slot}:00"

    # All today's slots are taken or past — use first slot tomorrow
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    for slot in slots:
        tomorrow_slot = f"{tomorrow}T{slot}:00"
        taken_tomorrow = any(
            item.get("scheduled_for", "").startswith(f"{tomorrow}T{slot}")
            for item in queue
            if item.get("status") in ("queued", "posting", "posted")
            and item.get("content_type", "post") == content_type
        )
        if not taken_tomorrow:
            return tomorrow_slot

    # Fallback: schedule for tomorrow at first slot
    return f"{tomorrow}T{slots[0]}:00"


def add_to_queue(
    date_str: str,
    post_index: int,
    text: str,
    content_type: str = "post",
    score: int | str = 0,
    scheduled_for: str | None = None,
    image_url: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Add content to the posting queue.

    Args:
        date_str: The content date (e.g., "2026-03-11")
        post_index: Index of the content piece (0-based)
        text: The full post text (already sanitized)
        content_type: "post", "article", or "newsletter"
        score: Quality score from editor
        scheduled_for: Optional specific time, otherwise auto-assigned
        image_url: Optional visual URL to attach
        metadata: Optional extra data (fact_check_status, tags, etc.)
    """
    queue = _load_queue()

    # Check for duplicates (same date + index + content_type)
    for item in queue:
        if (
            item.get("source_date") == date_str
            and item.get("post_index") == post_index
            and item.get("content_type", "post") == content_type
            and item["status"] in ("queued", "posting", "posted")
        ):
            return {"status": "already_queued", "item": item}

    if scheduled_for is None:
        scheduled_for = _next_slot(content_type)

    queue_item = {
        "id": f"{content_type}-{date_str}-{post_index}-{datetime.now().strftime('%H%M%S')}",
        "source_date": date_str,
        "post_index": post_index,
        "content_type": content_type,
        "text": text,
        "score": score,
        "status": "queued",  # queued → posting → posted / failed
        "queued_at": datetime.now().isoformat(),
        "scheduled_for": scheduled_for,
        "image_url": image_url,
        "posted_at": None,
        "post_url": None,
        "error": None,
    }

    if metadata:
        queue_item["metadata"] = metadata

    queue.append(queue_item)
    _save_queue(queue)

    logger.info(
        f"[queue] added {content_type} {date_str}/{post_index} "
        f"scheduled for {scheduled_for}"
    )
    return {"status": "queued", "item": queue_item}


def remove_from_queue(queue_id: str) -> dict:
    """Remove a post from the queue."""
    queue = _load_queue()
    new_queue = [item for item in queue if item.get("id") != queue_id]

    if len(new_queue) == len(queue):
        return {"status": "not_found"}

    _save_queue(new_queue)
    logger.info(f"[queue] removed {queue_id}")
    return {"status": "removed"}


def get_queue() -> list[dict]:
    """Get the full posting queue."""
    return _load_queue()


def get_due_posts() -> list[dict]:
    """Get posts that are due to be posted right now."""
    queue = _load_queue()
    now = datetime.now().isoformat()

    due = [
        item for item in queue
        if item.get("status") == "queued" and item.get("scheduled_for", "9999") <= now
    ]
    return due


def mark_posting(queue_id: str):
    """Mark a post as currently being posted."""
    queue = _load_queue()
    for item in queue:
        if item.get("id") == queue_id:
            item["status"] = "posting"
            break
    _save_queue(queue)


def mark_posted(queue_id: str, post_url: str | None = None):
    """Mark a post as successfully posted."""
    queue = _load_queue()
    for item in queue:
        if item.get("id") == queue_id:
            item["status"] = "posted"
            item["posted_at"] = datetime.now().isoformat()
            if post_url:
                item["post_url"] = post_url
            break
    _save_queue(queue)
    logger.info(f"[queue] marked {queue_id} as posted")


def mark_failed(queue_id: str, error: str):
    """Mark a post as failed."""
    queue = _load_queue()
    for item in queue:
        if item.get("id") == queue_id:
            item["status"] = "failed"
            item["error"] = error
            break
    _save_queue(queue)
    logger.error(f"[queue] {queue_id} failed: {error}")


def get_queue_stats() -> dict:
    """Get summary stats for the queue."""
    queue = _load_queue()
    stats = {
        "total": len(queue),
        "queued": sum(1 for q in queue if q["status"] == "queued"),
        "posting": sum(1 for q in queue if q["status"] == "posting"),
        "posted": sum(1 for q in queue if q["status"] == "posted"),
        "failed": sum(1 for q in queue if q["status"] == "failed"),
    }

    # Per content_type breakdown
    for ct in ["post", "article", "newsletter"]:
        ct_items = [q for q in queue if q.get("content_type", "post") == ct]
        stats[f"{ct}_queued"] = sum(1 for q in ct_items if q["status"] == "queued")
        stats[f"{ct}_posted"] = sum(1 for q in ct_items if q["status"] == "posted")

    return stats


def get_daily_quota_status(date_str: str | None = None) -> dict:
    """Check how many of each content type are queued/posted for a given date.

    Returns:
        {"posts": {"queued": N, "posted": N, "total": N, "quota": 2},
         "articles": {...}, "newsletters": {...}}
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    queue = _load_queue()

    status = {}
    quotas = {"post": 2, "article": 1, "newsletter": 1}

    for ct, quota in quotas.items():
        items = [
            q for q in queue
            if q.get("content_type", "post") == ct
            and q.get("source_date") == date_str
            and q.get("status") in ("queued", "posting", "posted")
        ]
        queued = sum(1 for q in items if q["status"] == "queued")
        posted = sum(1 for q in items if q["status"] in ("posting", "posted"))
        status[ct] = {
            "queued": queued,
            "posted": posted,
            "total": queued + posted,
            "quota": quota,
            "met": (queued + posted) >= quota,
        }

    return status
