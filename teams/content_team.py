"""Content Team orchestrator — runs the full daily content production pipeline.

Architecture: Three parallel sub-pipelines with retry loops + fact checking.

  PHASE 1: Intelligence
    TrendAnalyst → 10 trends

  PHASE 2: Three Sub-Pipelines (each with retry until quota met)
    POST PIPELINE (quota: 1/day — less volume, higher quality)
      SwipeStrategist (post briefs) → PostWriter → QualityEditor → retry loop
    ARTICLE PIPELINE (quota: 1, Tue + Thu only)
      SwipeStrategist (article brief) → ArticleResearcher → LongFormWriter → QualityEditor → retry
    NEWSLETTER PIPELINE (quota: 1, Wed only)
      SwipeStrategist (newsletter brief) → NewsletterResearcher → LongFormWriter → QualityEditor → retry

  PHASE 3: Post-Pipeline
    FactChecker → Strategic Tagging → Visual Generation → Queue → Email Report
"""

from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

from agents.base import load_config
from agents.content.trend_analyst import TrendAnalyst
from agents.content.swipe_strategist import SwipeStrategist
from agents.content.post_writer import PostWriter
from agents.content.longform_writer import LongFormWriter
from agents.content.quality_editor import QualityEditor
from agents.content.fact_checker import FactChecker
from agents.content.newsletter_researcher import NewsletterResearcher
from agents.content.article_researcher import ArticleResearcher
from agents.content.publisher import Publisher
from tools.email_notifier import send_pipeline_report

logger = logging.getLogger(__name__)

# VPS base URL for serving visual files
VISUAL_BASE_URL = "http://104.131.172.48:8080/visuals"

# Load retry config from content calendar
try:
    _cal = load_config("content_calendar.yaml")
    RETRY_CONFIG = _cal.get("retry_config", {})
    DAILY_QUOTAS = _cal.get("daily_quotas", {})
except Exception:
    RETRY_CONFIG = {}
    DAILY_QUOTAS = {}

MAX_RETRIES = RETRY_CONFIG.get("max_retries", 3)
POSTS_PER_ATTEMPT = RETRY_CONFIG.get("posts_per_attempt", 3)
ARTICLES_PER_ATTEMPT = RETRY_CONFIG.get("articles_per_attempt", 2)
NEWSLETTERS_PER_ATTEMPT = RETRY_CONFIG.get("newsletters_per_attempt", 2)

POST_QUOTA = DAILY_QUOTAS.get("posts", 1)
ARTICLE_QUOTA = 1  # 1 article per article day
ARTICLE_DAYS = DAILY_QUOTAS.get("article_days", ["tuesday", "thursday"])
NEWSLETTER_DAYS = DAILY_QUOTAS.get("newsletter_days", ["wednesday"])


def _is_newsletter_day() -> bool:
    """Check if today is a newsletter day (Wednesday)."""
    return datetime.now().strftime("%A").lower() in NEWSLETTER_DAYS


def _is_article_day() -> bool:
    """Check if today is an article day (Tuesday + Thursday)."""
    return datetime.now().strftime("%A").lower() in ARTICLE_DAYS


# ── Visual Generation ──────────────────────────────────────────────────────

def _generate_visuals_for_approved(reviews: dict, originals: dict) -> int:
    """Generate smart visuals for ALL approved content using visual rotation.

    Uses the smart visual system to pick the optimal format for each piece:
    - AI-generated images (DALL-E/Flux) for story-driven posts
    - Branded Pillow cards (stat, comparison, insight) for data/framework posts
    - Carousel PDFs for step-by-step, tip list, and save-worthy content

    Attaches visual_path and visual_url to the review dict for the publisher.

    Returns:
        Number of visuals successfully generated.
    """
    try:
        from tools.ai_image_generator import generate_smart_visual
    except ImportError as e:
        logger.warning(f"[content_team] ai_image_generator not available: {e}")
        try:
            from tools.visual_generator import generate_visual_for_post
            return _generate_visuals_legacy(reviews, originals)
        except ImportError:
            logger.warning("[content_team] no visual generator available")
            return 0

    visual_count = 0

    for category in ["posts", "newsletters", "articles"]:
        original_items = originals.get(category, originals.get("posts", []))
        reviewed_items = reviews.get(category, [])

        for idx, review in enumerate(reviewed_items):
            if review.get("verdict") != "APPROVED":
                continue

            # Already has a visual
            if review.get("visual_url") or review.get("visual_path"):
                visual_count += 1
                continue

            try:
                # Build post_data from review + original
                if idx < len(original_items):
                    original = original_items[idx]
                else:
                    original = {}

                post_data = {
                    "body": review.get("final_text", review.get("text", "")),
                    "headline": original.get("headline", review.get("headline", "")),
                    "format_style": original.get("format_style", review.get("format_style", "")),
                    "story_theme": original.get("story_theme", review.get("story_theme", "")),
                    "content_type": category.rstrip("s"),  # "posts" → "post"
                    "content_mix_category": original.get("content_mix_category", ""),
                    "save_worthy_element": original.get("save_worthy_element", ""),
                    "key_insight": original.get("key_insight", ""),
                    "type": original.get("type", ""),
                }

                # Generate smart visual (auto-picks best format)
                visual_path, visual_type = generate_smart_visual(post_data)

                if visual_path and Path(visual_path).exists():
                    review["visual_path"] = str(visual_path)
                    review["visual_type"] = visual_type

                    # Build URL — handle subdirectories
                    try:
                        rel_path = Path(visual_path).relative_to(
                            Path(__file__).parent.parent / "data" / "visuals"
                        )
                        review["visual_url"] = f"{VISUAL_BASE_URL}/{rel_path}"
                    except ValueError:
                        review["visual_url"] = f"{VISUAL_BASE_URL}/{Path(visual_path).name}"

                    visual_count += 1
                    logger.info(
                        f"[content_team] generated {visual_type} for {category}[{idx}]: "
                        f"{Path(visual_path).name}"
                    )
            except Exception as e:
                logger.warning(
                    f"[content_team] visual generation failed for {category}[{idx}]: {e}"
                )

    return visual_count


def _generate_visuals_legacy(reviews: dict, originals: dict) -> int:
    """Legacy visual generation using Pillow branded cards (fallback)."""
    from tools.visual_generator import generate_visual_for_post

    visual_count = 0
    for category in ["posts", "newsletters", "articles"]:
        original_items = originals.get(category, originals.get("posts", []))
        reviewed_items = reviews.get(category, [])

        for idx, review in enumerate(reviewed_items):
            if review.get("verdict") != "APPROVED":
                continue

            if idx < len(original_items):
                original = original_items[idx]
                visual_type = original.get("visual_type", "none")
            else:
                visual_type = review.get("visual_type", "none")

            if not visual_type or visual_type == "none":
                continue

            try:
                post_data = {
                    "visual_type": visual_type,
                    "body": review.get("final_text", ""),
                    "headline": original.get("headline", "") if idx < len(original_items) else "",
                }
                visual_path = generate_visual_for_post(post_data)
                if visual_path and Path(visual_path).exists():
                    review["visual_path"] = str(visual_path)
                    review["visual_url"] = f"{VISUAL_BASE_URL}/{Path(visual_path).name}"
                    visual_count += 1
            except Exception as e:
                logger.warning(f"[content_team] legacy visual failed for {category}[{idx}]: {e}")

    return visual_count


# ── Sub-Pipeline: Posts ────────────────────────────────────────────────────

def _run_post_pipeline(
    trends: list[dict],
    quota: int = POST_QUOTA,
    max_retries: int = MAX_RETRIES,
) -> tuple[list[dict], dict]:
    """Generate posts with retry loop until quota is met.

    Returns:
        (approved_reviews, all_original_posts_dict) — approved reviews list
        and the original posts dict (for visual generation matching).
    """
    logger.info(f"[post_pipeline] starting — quota: {quota}, max_retries: {max_retries}")

    strategist = SwipeStrategist()
    post_writer = PostWriter()
    editor = QualityEditor()

    all_approved = []
    all_posts = {"posts": []}
    attempt = 0

    while len(all_approved) < quota and attempt < max_retries:
        attempt += 1
        posts_needed = quota - len(all_approved)
        briefs_to_generate = posts_needed + 1  # +1 buffer for rejections

        logger.info(
            f"[post_pipeline] attempt {attempt}/{max_retries}: "
            f"generating {briefs_to_generate} briefs, need {posts_needed} more"
        )

        # Generate briefs — filter for post-type only
        briefs = strategist.run(trends)
        post_briefs = [b for b in briefs if b.get("content_type") not in ("newsletter", "article")]
        post_briefs = post_briefs[:briefs_to_generate]

        if not post_briefs:
            logger.warning("[post_pipeline] no post briefs generated — retrying")
            continue

        # Write posts
        posts = post_writer.run(post_briefs)
        all_posts["posts"].extend(posts.get("posts", []))

        # Quality review — posts only
        reviews = editor.run(posts, {"newsletters": [], "articles": []})

        # Collect newly approved
        newly_approved = [
            r for r in reviews.get("posts", [])
            if r.get("verdict") == "APPROVED"
        ]
        all_approved.extend(newly_approved)

        logger.info(
            f"[post_pipeline] attempt {attempt}: {len(newly_approved)} approved, "
            f"total: {len(all_approved)}/{quota}"
        )

        if len(all_approved) >= quota:
            break

    # Cap at quota
    all_approved = all_approved[:quota]

    logger.info(
        f"[post_pipeline] complete: {len(all_approved)}/{quota} posts approved "
        f"in {attempt} attempt(s)"
    )
    return all_approved, all_posts


# ── Sub-Pipeline: Articles ─────────────────────────────────────────────────

def _run_article_pipeline(
    trends: list[dict],
    quota: int = ARTICLE_QUOTA,
    max_retries: int = MAX_RETRIES,
) -> tuple[list[dict], dict]:
    """Generate articles with research + retry loop.

    Returns:
        (approved_reviews, all_original_articles_dict)
    """
    if not _is_article_day():
        logger.info("[article_pipeline] skipping — not an article day (Tue/Thu)")
        return [], {"articles": []}

    logger.info(f"[article_pipeline] starting — quota: {quota}, max_retries: {max_retries}")

    strategist = SwipeStrategist()
    researcher = ArticleResearcher()
    longform_writer = LongFormWriter()
    editor = QualityEditor()

    all_approved = []
    all_articles = {"articles": []}
    attempt = 0

    while len(all_approved) < quota and attempt < max_retries:
        attempt += 1
        articles_needed = quota - len(all_approved)

        logger.info(
            f"[article_pipeline] attempt {attempt}/{max_retries}: "
            f"need {articles_needed} more article(s)"
        )

        # Generate article briefs
        briefs = strategist.run(trends)
        article_briefs = [b for b in briefs if b.get("content_type") == "article"]
        article_briefs = article_briefs[:ARTICLES_PER_ATTEMPT]

        if not article_briefs:
            # Force-create an article brief from the best trend
            logger.info("[article_pipeline] no article briefs — forcing from top trend")
            article_briefs = [{
                "content_type": "article",
                "trend_source": trends[0].get("title", "AI implementation") if trends else "AI implementation",
                "angle": trends[0].get("angle", "practical AI") if trends else "practical AI",
                "copywriter_dna": ["todd_brown", "alex_hormozi", "bill_mueller"],
                "word_count": [1000, 1500],
            }]

        # Research each article brief
        enriched_briefs = []
        for brief in article_briefs:
            research = researcher.run(brief, trends)
            enriched = researcher.enrich_brief(brief, research)
            enriched_briefs.append(enriched)

        # Write articles using enriched briefs
        articles = longform_writer.run(enriched_briefs)
        all_articles["articles"].extend(articles.get("articles", []))

        # Quality review — articles only
        reviews = editor.run({"posts": []}, articles)

        newly_approved = [
            r for r in reviews.get("articles", [])
            if r.get("verdict") == "APPROVED"
        ]
        all_approved.extend(newly_approved)

        logger.info(
            f"[article_pipeline] attempt {attempt}: {len(newly_approved)} approved, "
            f"total: {len(all_approved)}/{quota}"
        )

        if len(all_approved) >= quota:
            break

    all_approved = all_approved[:quota]

    logger.info(
        f"[article_pipeline] complete: {len(all_approved)}/{quota} articles approved "
        f"in {attempt} attempt(s)"
    )
    return all_approved, all_articles


# ── Sub-Pipeline: Newsletters ──────────────────────────────────────────────

def _run_newsletter_pipeline(
    trends: list[dict],
    quota: int = 1,
    max_retries: int = MAX_RETRIES,
) -> tuple[list[dict], dict]:
    """Generate newsletters with research + retry loop.

    Returns:
        (approved_reviews, all_original_newsletters_dict)
    """
    if not _is_newsletter_day():
        logger.info("[newsletter_pipeline] skipping — not a newsletter day")
        return [], {"newsletters": []}

    logger.info(f"[newsletter_pipeline] starting — quota: {quota}, max_retries: {max_retries}")

    strategist = SwipeStrategist()
    researcher = NewsletterResearcher()
    longform_writer = LongFormWriter()
    editor = QualityEditor()

    all_approved = []
    all_newsletters = {"newsletters": []}
    attempt = 0

    while len(all_approved) < quota and attempt < max_retries:
        attempt += 1

        logger.info(
            f"[newsletter_pipeline] attempt {attempt}/{max_retries}: "
            f"need {quota - len(all_approved)} more newsletter(s)"
        )

        # Generate newsletter briefs
        briefs = strategist.run(trends)
        nl_briefs = [b for b in briefs if b.get("content_type") == "newsletter"]
        nl_briefs = nl_briefs[:NEWSLETTERS_PER_ATTEMPT]

        if not nl_briefs:
            # Force-create a newsletter brief
            logger.info("[newsletter_pipeline] no newsletter briefs — forcing from top trend")
            nl_briefs = [{
                "content_type": "newsletter",
                "trend_source": trends[0].get("title", "AI implementation") if trends else "AI implementation",
                "angle": trends[0].get("angle", "practical AI") if trends else "practical AI",
                "copywriter_dna": ["jay_abraham", "bill_mueller", "brian_kurtz"],
                "word_count": [800, 1200],
            }]

        # Research each newsletter brief
        enriched_briefs = []
        for brief in nl_briefs:
            research = researcher.run(brief, trends)
            enriched = researcher.enrich_brief(brief, research)
            enriched_briefs.append(enriched)

        # Write newsletters using enriched briefs
        newsletters = longform_writer.run(enriched_briefs)
        all_newsletters["newsletters"].extend(newsletters.get("newsletters", []))

        # Quality review — newsletters only
        reviews = editor.run({"posts": []}, newsletters)

        newly_approved = [
            r for r in reviews.get("newsletters", [])
            if r.get("verdict") == "APPROVED"
        ]
        all_approved.extend(newly_approved)

        logger.info(
            f"[newsletter_pipeline] attempt {attempt}: {len(newly_approved)} approved, "
            f"total: {len(all_approved)}/{quota}"
        )

        if len(all_approved) >= quota:
            break

    all_approved = all_approved[:quota]

    logger.info(
        f"[newsletter_pipeline] complete: {len(all_approved)}/{quota} newsletters approved "
        f"in {attempt} attempt(s)"
    )
    return all_approved, all_newsletters


# ── Main Pipeline ──────────────────────────────────────────────────────────

def run_content_production():
    """Execute the full content production pipeline.

    Runs daily at 5:30 AM ET.
    """
    start = datetime.now()
    day_name = start.strftime("%A")
    logger.info(
        f"[content_team] starting daily production at {start.isoformat()} ({day_name})"
    )

    try:
        # ── PHASE 1: Intelligence ──────────────────────────────────────
        logger.info("[content_team] Phase 1: Trend Analysis")
        trend_analyst = TrendAnalyst()
        trends = trend_analyst.run()
        logger.info(f"[content_team] found {len(trends)} trends")

        # ── PHASE 2: Three Sub-Pipelines ───────────────────────────────
        logger.info("[content_team] Phase 2: Content Production (3 sub-pipelines)")

        # 2a: Post Pipeline
        logger.info("[content_team] Phase 2a: Post Pipeline")
        approved_posts, original_posts = _run_post_pipeline(trends)

        # 2b: Article Pipeline
        logger.info("[content_team] Phase 2b: Article Pipeline")
        approved_articles, original_articles = _run_article_pipeline(trends)

        # 2c: Newsletter Pipeline
        logger.info("[content_team] Phase 2c: Newsletter Pipeline")
        approved_newsletters, original_newsletters = _run_newsletter_pipeline(trends)

        # ── Combine results into review structure ──────────────────────
        all_reviews = {
            "posts": approved_posts,
            "articles": approved_articles,
            "newsletters": approved_newsletters,
        }

        # Combined original content for visual matching
        all_originals = {
            "posts": original_posts.get("posts", []),
            "articles": original_articles.get("articles", []),
            "newsletters": original_newsletters.get("newsletters", []),
        }

        total_approved = (
            len(approved_posts) + len(approved_articles) + len(approved_newsletters)
        )
        logger.info(
            f"[content_team] Phase 2 complete: {total_approved} approved "
            f"({len(approved_posts)} posts, {len(approved_articles)} articles, "
            f"{len(approved_newsletters)} newsletters)"
        )

        # ── PHASE 3: Post-Pipeline Processing ─────────────────────────

        # 3a: Fact Checking
        logger.info("[content_team] Phase 3a: Fact Checking")
        all_approved_flat = approved_posts + approved_articles + approved_newsletters
        if all_approved_flat:
            fact_checker = FactChecker()
            checked = fact_checker.run(all_approved_flat)

            # Count fact check results
            fc_pass = sum(1 for item in checked if item.get("fact_check_status") == "pass")
            fc_flag = sum(1 for item in checked if item.get("fact_check_status") == "flag")
            fc_fail = sum(1 for item in checked if item.get("fact_check_status") == "fail")
            fc_skip = sum(1 for item in checked if item.get("fact_check_status") == "skipped")

            logger.info(
                f"[content_team] fact check: {fc_pass} pass, {fc_flag} flag, "
                f"{fc_fail} fail, {fc_skip} skipped"
            )

            # Remove fact-check-failed items (demoted to REJECTED) from reviews
            all_reviews["posts"] = [
                r for r in all_reviews["posts"]
                if r.get("verdict") == "APPROVED"
            ]
            all_reviews["articles"] = [
                r for r in all_reviews["articles"]
                if r.get("verdict") == "APPROVED"
            ]
            all_reviews["newsletters"] = [
                r for r in all_reviews["newsletters"]
                if r.get("verdict") == "APPROVED"
            ]

            total_after_fc = (
                len(all_reviews["posts"])
                + len(all_reviews["articles"])
                + len(all_reviews["newsletters"])
            )
            logger.info(
                f"[content_team] after fact check: {total_after_fc} remain approved"
            )
        else:
            fc_pass = fc_flag = fc_fail = fc_skip = 0
            logger.info("[content_team] no items to fact check")

        # 3b: Strategic Influencer Tagging
        logger.info("[content_team] Phase 3b: Strategic Tagging")
        try:
            from tools.influencer_tagger import apply_strategic_tags
            tagged_count = apply_strategic_tags(all_reviews)
            logger.info(f"[content_team] tagged {tagged_count} posts with influencer mentions")
        except ImportError as e:
            logger.warning(f"[content_team] influencer_tagger not available: {e}")
            tagged_count = 0

        # 3c: Generate Visuals for approved content
        logger.info("[content_team] Phase 3c: Generating Visuals")
        visual_count = _generate_visuals_for_approved(all_reviews, all_originals)
        logger.info(f"[content_team] generated {visual_count} visuals")

        # 3d: Route to Posting Queue
        logger.info("[content_team] Phase 3d: Routing to Posting Queue")
        publisher = Publisher()
        publish_result = publisher.run(all_reviews)
        total_queued = publish_result.get("total_queued", 0)
        logger.info(f"[content_team] queued {total_queued} items for strategic posting")

        # ── Pipeline complete ──────────────────────────────────────────
        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"[content_team] pipeline complete in {elapsed:.1f}s")

        result = {
            "status": "success",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "day": day_name,
            "trends": len(trends),
            "posts_approved": len(all_reviews["posts"]),
            "posts_quota": POST_QUOTA,
            "articles_approved": len(all_reviews["articles"]),
            "articles_quota": ARTICLE_QUOTA if _is_article_day() else 0,
            "newsletters_approved": len(all_reviews["newsletters"]),
            "newsletter_day": _is_newsletter_day(),
            "fact_check": {
                "pass": fc_pass,
                "flag": fc_flag,
                "fail": fc_fail,
                "skipped": fc_skip,
            },
            "posts_tagged": tagged_count,
            "visuals_generated": visual_count,
            "total_queued": total_queued,
            "queue_summary": publish_result.get("summary", {}),
            "elapsed_seconds": elapsed,
        }

        # Post-pipeline: Google Drive upload (optional)
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            from tools.gdrive_client import upload_daily_content
            logger.info("[content_team] Post-pipeline: Uploading to Google Drive")
            gdrive_result = upload_daily_content(today)
            result["gdrive"] = gdrive_result
            logger.info(f"[content_team] Drive upload: {gdrive_result.get('status')}")
        except Exception as e:
            logger.warning(f"[content_team] Drive upload failed (non-fatal): {e}")
            result["gdrive"] = {"status": "error", "error": str(e)}

        # Post-pipeline: Send email notification
        try:
            logger.info("[content_team] Post-pipeline: Sending email report")
            email_result = send_pipeline_report(result, today)
            result["email"] = email_result
            logger.info(f"[content_team] Email: {email_result.get('status')}")
        except Exception as e:
            logger.warning(f"[content_team] Email notification failed (non-fatal): {e}")
            result["email"] = {"status": "error", "error": str(e)}

        return result

    except Exception as e:
        logger.error(f"[content_team] pipeline failed: {e}", exc_info=True)
        error_result = {"status": "error", "error": str(e)}

        # Still try to send error notification
        try:
            send_pipeline_report(error_result)
        except Exception:
            pass

        return error_result
