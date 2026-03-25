"""Auto-poster — checks the posting queue and publishes to LinkedIn.

Runs every 15 minutes via the scheduler. Picks up any queued items
whose scheduled_for time has passed and posts them to LinkedIn.

Posting methods:
  - Unipile (primary): Direct API posting with image attachment support
  - PhantomBuster (fallback): CSV-based posting for text-only posts

Supports content types: post, article, newsletter.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from datetime import datetime

from tools.posting_queue import get_due_posts, mark_posting, mark_posted, mark_failed
from tools.text_sanitizer import sanitize_for_linkedin

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
VISUALS_DIR = DATA_DIR / "visuals"


def _url_to_local_path(image_url: str) -> str | None:
    """Convert a dashboard image URL to a local file path.

    Handles images, PDFs (carousels), and ai-generated subdirectory.
    """
    if not image_url:
        return None
    if "/visuals/" in image_url:
        relative = image_url.split("/visuals/")[-1]
        local = VISUALS_DIR / relative
        if local.exists():
            return str(local)
    return None


def _is_carousel(path: str | None) -> bool:
    """Check if the attachment is a carousel/document (PDF)."""
    if not path:
        return False
    return path.lower().endswith((".pdf", ".pptx", ".docx"))


def _post_via_unipile(text: str, image_url: str | None = None) -> dict:
    """Post via Unipile API (supports images via multipart upload)."""
    from tools.unipile_client import UnipileClient

    client = UnipileClient()
    image_path = _url_to_local_path(image_url)

    is_doc = _is_carousel(image_path)
    if image_path and is_doc:
        logger.info(f"[auto-poster] Unipile posting carousel/document: {image_path}")
    elif image_path:
        logger.info(f"[auto-poster] Unipile posting with image: {image_path}")
    else:
        logger.info("[auto-poster] Unipile posting text-only")

    result = client.create_post(text, image_path=image_path)

    if result and result.get("post_id"):
        return {
            "status": "finished",
            "post_id": result.get("post_id", ""),
            "method": "unipile",
        }
    elif result:
        return {
            "status": "finished",
            "post_id": result.get("id", ""),
            "method": "unipile",
        }
    else:
        return {
            "status": "error",
            "error": "Unipile returned empty response",
            "method": "unipile",
        }


def _post_via_phantombuster(text: str, image_url: str | None = None) -> dict:
    """Post via PhantomBuster (CSV method, limited image support)."""
    from tools.phantombuster_client import publish_post

    phantom_id = os.environ.get("PB_POST_PHANTOM_ID", "")
    if not phantom_id:
        return {"status": "error", "error": "PB_POST_PHANTOM_ID not set", "method": "phantombuster"}

    result = publish_post(phantom_id, text, image_url=image_url)
    result["method"] = "phantombuster"
    return result


def run_auto_poster() -> dict:
    """Check the queue and post any due items.

    Uses Unipile as the primary posting method (supports images).
    Falls back to PhantomBuster for text-only if Unipile fails.

    Returns summary of what was posted.
    """
    due = get_due_posts()
    if not due:
        logger.debug("[auto-poster] no items due right now")
        return {"status": "idle", "items_due": 0}

    # Check which posting methods are available
    has_unipile = bool(os.environ.get("UNIPILE_API_KEY"))
    has_pb = bool(os.environ.get("PB_POST_PHANTOM_ID"))

    if not has_unipile and not has_pb:
        logger.warning("[auto-poster] No posting method configured (need UNIPILE_API_KEY or PB_POST_PHANTOM_ID)")
        return {"status": "skipped", "reason": "No posting method configured"}

    logger.info(f"[auto-poster] {len(due)} item(s) due for posting")
    results = []

    for item in due:
        queue_id = item["id"]
        text = item["text"]
        content_type = item.get("content_type", "post")
        image_url = item.get("image_url")

        # Sanitize text before publishing (strip markdown, humanize, format)
        text = sanitize_for_linkedin(text, humanize=True)

        try:
            mark_posting(queue_id)
            logger.info(f"[auto-poster] posting {content_type} {queue_id}...")

            post_result = None

            # Strategy: Use Unipile for posts with images, or as primary method
            if has_unipile:
                post_result = _post_via_unipile(text, image_url)

                # If Unipile failed and we have PB, try PB as fallback (text-only)
                if post_result.get("status") != "finished" and has_pb and not image_url:
                    logger.warning("[auto-poster] Unipile failed, trying PhantomBuster fallback...")
                    post_result = _post_via_phantombuster(text, image_url)
            elif has_pb:
                post_result = _post_via_phantombuster(text, image_url)

            # Process result
            if post_result and post_result.get("status") == "finished":
                post_url = post_result.get("post_url") or post_result.get("url")
                post_id = post_result.get("post_id", "")
                method = post_result.get("method", "unknown")

                mark_posted(queue_id, post_url)
                results.append({
                    "id": queue_id,
                    "content_type": content_type,
                    "status": "posted",
                    "url": post_url,
                    "post_id": post_id,
                    "method": method,
                })
                logger.info(f"[auto-poster] ✓ posted {content_type} {queue_id} via {method}")
            else:
                error_msg = post_result.get("error", "Unknown error") if post_result else "No result"
                mark_failed(queue_id, str(error_msg))
                results.append({
                    "id": queue_id,
                    "content_type": content_type,
                    "status": "failed",
                    "error": str(error_msg),
                })
                logger.error(f"[auto-poster] ✗ failed {content_type} {queue_id}: {error_msg}")

        except Exception as e:
            mark_failed(queue_id, str(e))
            results.append({
                "id": queue_id,
                "content_type": content_type,
                "status": "failed",
                "error": str(e),
            })
            logger.error(f"[auto-poster] ✗ exception posting {content_type} {queue_id}: {e}")

    # Summarize by content type
    posted_by_type = {}
    for r in results:
        ct = r.get("content_type", "post")
        if r["status"] == "posted":
            posted_by_type[ct] = posted_by_type.get(ct, 0) + 1

    return {
        "status": "completed",
        "items_due": len(due),
        "posted": sum(1 for r in results if r["status"] == "posted"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "posted_by_type": posted_by_type,
        "results": results,
    }
