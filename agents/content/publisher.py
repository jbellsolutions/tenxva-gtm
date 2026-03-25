"""Publisher agent — routes approved content to the posting queue for strategic publishing.

No longer publishes directly to PhantomBuster. Instead:
1. Sanitizes approved text (strip markdown, humanize, format)
2. Routes to posting_queue with content_type-specific time slots
3. Auto-poster (runs every 15 min) picks up queued items and posts via PhantomBuster

Content routing:
  posts       → 09:00, 15:00 (2/day)
  articles    → 10:30 (1/day, Mon-Fri)
  newsletters → 08:00 (Mon/Wed/Fri)
"""

from __future__ import annotations

import logging
from datetime import datetime

from agents.base import BaseAgent
from tools.posting_queue import add_to_queue
from tools.text_sanitizer import sanitize_for_linkedin

logger = logging.getLogger(__name__)

# Map review categories to content_type for queue routing
CATEGORY_TO_CONTENT_TYPE = {
    "posts": "post",
    "newsletters": "newsletter",
    "articles": "article",
}


class Publisher(BaseAgent):
    """Routes approved content to the posting queue for strategic publishing."""

    def __init__(self):
        super().__init__("publisher", prompt_file=None)

    def run(self, reviews: dict) -> dict:
        """Route all approved content to the posting queue.

        Args:
            reviews: Dict with 'posts', 'newsletters', 'articles' lists
                     from QualityEditor, each with verdict and final_text.

        Returns:
            Summary of what was queued.
        """
        logger.info("[publisher] routing approved content to posting queue")
        today = self.today_str()
        queued = []
        skipped = []

        for category in ["posts", "newsletters", "articles"]:
            content_type = CATEGORY_TO_CONTENT_TYPE[category]

            for idx, review in enumerate(reviews.get(category, [])):
                if review.get("verdict") != "APPROVED":
                    continue

                final_text = review.get("final_text", "")
                if not final_text:
                    logger.warning(
                        f"[publisher] {category}[{idx}] approved but no final_text — skipping"
                    )
                    skipped.append({"category": category, "index": idx, "reason": "no_text"})
                    continue

                # Sanitize text: strip markdown, humanize AI patterns, format for LinkedIn
                final_text = sanitize_for_linkedin(final_text, humanize=True)

                # Get visual URL if available
                image_url = review.get("visual_url")

                # Build metadata for the queue item
                metadata = {
                    "score": review.get("score", 0),
                    "fact_check_status": review.get("fact_check_status", "not_checked"),
                    "content_id": review.get("content_id", f"{category}-{idx}"),
                }

                # Route to queue
                result = add_to_queue(
                    date_str=today,
                    post_index=idx,
                    text=final_text,
                    content_type=content_type,
                    score=review.get("score", 0),
                    image_url=image_url,
                    metadata=metadata,
                )

                status = result.get("status", "unknown")
                if status in ("queued", "already_queued"):
                    queue_item = result.get("item", {})
                    queued.append({
                        "content_type": content_type,
                        "category": category,
                        "index": idx,
                        "status": status,
                        "scheduled_for": queue_item.get("scheduled_for", "unknown"),
                        "queue_id": queue_item.get("id", "unknown"),
                        "text_preview": final_text[:100],
                        "visual_url": image_url,
                    })
                    logger.info(
                        f"[publisher] queued {content_type} {today}/{idx} → "
                        f"{queue_item.get('scheduled_for', 'unknown')}"
                    )
                else:
                    skipped.append({
                        "category": category,
                        "index": idx,
                        "reason": f"queue_error: {status}",
                    })
                    logger.warning(f"[publisher] failed to queue {category}[{idx}]: {status}")

        output = {
            "date": today,
            "total_queued": len(queued),
            "total_skipped": len(skipped),
            "queued_items": queued,
            "skipped_items": skipped,
            "summary": {
                "posts_queued": sum(1 for q in queued if q["content_type"] == "post"),
                "articles_queued": sum(1 for q in queued if q["content_type"] == "article"),
                "newsletters_queued": sum(1 for q in queued if q["content_type"] == "newsletter"),
            },
        }

        self.save_output(
            output,
            "published",
            f"{today}_queued.json",
        )

        logger.info(
            f"[publisher] routed {len(queued)} items to queue "
            f"({output['summary']['posts_queued']} posts, "
            f"{output['summary']['articles_queued']} articles, "
            f"{output['summary']['newsletters_queued']} newsletters)"
        )
        return output
