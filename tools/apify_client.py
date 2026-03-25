"""Apify API client for LinkedIn scraping (READ operations)."""

from __future__ import annotations

import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.apify.com/v2"


def _token() -> str:
    return os.environ["APIFY_API_TOKEN"]


def run_actor(actor_id: str, input_data: dict, timeout: int = 120) -> list[dict]:
    """Run an Apify actor and wait for results.

    Returns the dataset items from the run.
    """
    logger.info(f"[apify] running actor {actor_id}")

    # Start the actor run
    resp = requests.post(
        f"{BASE_URL}/acts/{actor_id}/runs",
        params={"token": _token()},
        json=input_data,
        timeout=30,
    )
    resp.raise_for_status()
    run_data = resp.json().get("data", {})
    run_id = run_data["id"]

    # Poll until finished
    start = time.time()
    while time.time() - start < timeout:
        status_resp = requests.get(
            f"{BASE_URL}/actor-runs/{run_id}",
            params={"token": _token()},
            timeout=15,
        )
        status_resp.raise_for_status()
        status = status_resp.json().get("data", {}).get("status")
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            logger.error(f"[apify] actor run {run_id} ended with status: {status}")
            return []
        time.sleep(5)

    # Get dataset items
    dataset_id = run_data.get("defaultDatasetId")
    if not dataset_id:
        return []

    items_resp = requests.get(
        f"{BASE_URL}/datasets/{dataset_id}/items",
        params={"token": _token(), "format": "json"},
        timeout=30,
    )
    items_resp.raise_for_status()
    items = items_resp.json()
    logger.info(f"[apify] got {len(items)} items from actor {actor_id}")
    return items


def scrape_linkedin_profile(profile_url: str) -> dict:
    """Scrape a single LinkedIn profile."""
    results = run_actor(
        "anchor/linkedin-profile-scraper",
        {"profileUrls": [profile_url]},
    )
    return results[0] if results else {}


def scrape_linkedin_posts(profile_url: str, max_posts: int = 5) -> list[dict]:
    """Scrape recent posts from a LinkedIn profile."""
    results = run_actor(
        "anchor/linkedin-post-scraper",
        {"profileUrls": [profile_url], "maxPosts": max_posts},
    )
    return results


def scrape_post_commenters(post_url: str, max_comments: int = 100) -> list[dict]:
    """Scrape commenters from a specific LinkedIn post."""
    results = run_actor(
        "anchor/linkedin-comment-scraper",
        {"postUrls": [post_url], "maxComments": max_comments},
    )
    return results


def scrape_own_post_comments(profile_url: str) -> list[dict]:
    """Scrape comments on our own recent posts (for reply monitoring)."""
    # First get our recent posts
    posts = scrape_linkedin_posts(profile_url, max_posts=10)
    all_comments = []
    for post in posts:
        post_url = post.get("postUrl", post.get("url", ""))
        if post_url:
            comments = scrape_post_commenters(post_url, max_comments=50)
            for c in comments:
                c["source_post_url"] = post_url
            all_comments.extend(comments)
    return all_comments
