"""Post content blitz items with images via Unipile.

This is the direct posting tool for content blitz items.
Uses Unipile's multipart API to create LinkedIn posts WITH images.

Usage:
    python3 -m tools.post_with_image           # Post next due item
    python3 -m tools.post_with_image --test     # Test image posting with a test post
    python3 -m tools.post_with_image --day tue  # Post specific day
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.unipile_client import UnipileClient
from tools.posting_queue import get_queue, mark_posting, mark_posted, mark_failed

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VISUALS_DIR = DATA_DIR / "visuals"

# Map image URLs to local paths (for direct file upload)
IMAGE_MAP = {
    "image_7_monday.png": VISUALS_DIR / "blitz" / "image_7_monday.png",
    "image_3_tuesday.png": VISUALS_DIR / "blitz" / "image_3_tuesday.png",
    "image_1_wednesday.png": VISUALS_DIR / "blitz" / "image_1_wednesday.png",
    "image_2_thursday.png": VISUALS_DIR / "blitz" / "image_2_thursday.png",
}


def _url_to_local_path(image_url: str) -> str | None:
    """Convert a dashboard image URL to a local file path."""
    if not image_url:
        return None
    # Extract filename from URL
    for key, path in IMAGE_MAP.items():
        if key in image_url:
            if path.exists():
                return str(path)
    # Try generic: extract path after /visuals/
    if "/visuals/" in image_url:
        relative = image_url.split("/visuals/")[-1]
        local = VISUALS_DIR / relative
        if local.exists():
            return str(local)
    return None


def post_due_items_with_images():
    """Post all due queue items using Unipile with image support."""
    queue = get_queue()
    now = datetime.now().isoformat()

    due = [
        item for item in queue
        if item.get("status") == "queued" and item.get("scheduled_for", "9999") <= now
    ]

    if not due:
        print("No items due right now.")
        return {"posted": 0}

    client = UnipileClient()
    results = []

    for item in due:
        queue_id = item["id"]
        text = item["text"]
        image_url = item.get("image_url")
        content_type = item.get("content_type", "post")

        # Convert URL to local path for direct upload
        image_path = _url_to_local_path(image_url)

        print(f"\nPosting {content_type}: {queue_id}")
        print(f"  Text length: {len(text)} chars")
        print(f"  Image URL: {image_url}")
        print(f"  Image path: {image_path}")

        mark_posting(queue_id)

        try:
            result = client.create_post(text, image_path=image_path)

            if result:
                post_id = result.get("id", "")
                post_url = result.get("url", "")
                print(f"  ✓ Posted! ID: {post_id}")
                mark_posted(queue_id, post_url)
                results.append({"id": queue_id, "status": "posted", "post_id": post_id})
            else:
                print(f"  ✗ Failed — empty response")
                mark_failed(queue_id, "Empty response from Unipile")
                results.append({"id": queue_id, "status": "failed"})
        except Exception as e:
            print(f"  ✗ Error: {e}")
            mark_failed(queue_id, str(e))
            results.append({"id": queue_id, "status": "failed", "error": str(e)})

    posted = sum(1 for r in results if r["status"] == "posted")
    print(f"\nDone: {posted}/{len(due)} posted successfully")
    return {"posted": posted, "total": len(due), "results": results}


def post_specific_day(day: str):
    """Post a specific day's content blitz item with image."""
    from tools.content_blitz_loader import load_blitz_content

    items = load_blitz_content()
    day_map = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday"}
    target_day = day_map.get(day.lower()[:3], day.title())

    target = None
    for item in items:
        if item["day_label"] == target_day:
            target = item
            break

    if not target:
        print(f"No blitz item found for {target_day}")
        return

    text = target["text"]
    title = target.get("title", "")
    if title:
        text = f"{title}\n\n{text}"

    image_url = target.get("image_url", "")
    image_path = _url_to_local_path(image_url)

    print(f"Posting {target_day} ({target['content_type']})")
    print(f"  Text length: {len(text)} chars")
    print(f"  Image: {image_path}")

    client = UnipileClient()
    result = client.create_post(text, image_path=image_path)

    if result:
        print(f"  ✓ Posted! ID: {result.get('id', 'unknown')}")
        print(f"  Response: {json.dumps(result, indent=2)}")
    else:
        print("  ✗ Failed")


def test_image_post():
    """Test posting a simple post with an image to verify the pipeline works."""
    # Use the smallest image as test
    test_image = VISUALS_DIR / "blitz" / "image_3_tuesday.png"
    if not test_image.exists():
        print(f"Test image not found: {test_image}")
        return

    test_text = "Testing image posting — this is a test post. Will delete shortly."

    print("Test posting with image...")
    print(f"  Image: {test_image} ({test_image.stat().st_size / 1024:.0f} KB)")

    client = UnipileClient()
    result = client.create_post(test_text, image_path=str(test_image))

    print(f"Result: {json.dumps(result, indent=2)}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if "--test" in sys.argv:
        test_image_post()
    elif "--day" in sys.argv:
        idx = sys.argv.index("--day")
        if idx + 1 < len(sys.argv):
            post_specific_day(sys.argv[idx + 1])
        else:
            print("Usage: --day mon|tue|wed|thu")
    else:
        post_due_items_with_images()
