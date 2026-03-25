"""
Content Blitz Loader — loads pre-written content into the posting queue.

Reads JSON files from data/content-blitz/ and queues them for the auto-poster.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BLITZ_DIR = Path("data/content-blitz")


def load_blitz_content():
    """
    Load all content blitz files and return them as queue-ready items.
    """
    items = []
    if not BLITZ_DIR.exists():
        logger.warning("No content-blitz directory found")
        return items

    for f in sorted(BLITZ_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            items.append({
                "file": f.name,
                "content_type": data.get("content_type", "post"),
                "scheduled_date": data.get("scheduled_date", ""),
                "scheduled_time": data.get("scheduled_time", "09:00"),
                "title": data.get("title", ""),
                "text": data.get("text", ""),
                "image": data.get("image", ""),
                "image_file": data.get("image_file", ""),
                "image_url": data.get("image_url", ""),
                "image_description": data.get("image_description", ""),
                "day_label": data.get("day_label", ""),
                "cta": data.get("cta", ""),
            })
        except Exception as e:
            logger.error(f"Error loading blitz file {f.name}: {e}")

    logger.info(f"Loaded {len(items)} content blitz items")
    return items


def queue_blitz_content(posting_queue_add_func=None):
    """
    Load blitz content and add to posting queue.
    If no posting_queue_add_func is provided, just prints what would be queued.
    """
    items = load_blitz_content()
    queued = 0

    for item in items:
        date = item["scheduled_date"]
        time_slot = item["scheduled_time"]
        content_type = item["content_type"]
        text = item["text"]
        title = item.get("title", "")

        if title:
            text = f"{title}\n\n{text}"

        logger.info(f"Queuing {item['day_label']} {content_type}: {item['file']}")
        logger.info(f"  Date: {date}, Time: {time_slot}")
        logger.info(f"  Text length: {len(text)} chars")

        if posting_queue_add_func:
            posting_queue_add_func(
                content_type=content_type,
                text=text,
                score=10,  # Pre-approved content
                source_date=date,
                image_url=item.get("image_url") or None,
            )
            queued += 1
        else:
            print(f"  [DRY RUN] Would queue: {item['day_label']} {content_type}")
            queued += 1

    return {"loaded": len(items), "queued": queued}


if __name__ == "__main__":
    # Dry run
    import sys
    logging.basicConfig(level=logging.INFO)
    result = queue_blitz_content()
    print(f"\nBlitz content: {result}")
