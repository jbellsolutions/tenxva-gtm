"""Firecrawl API client for web scraping and search."""

from __future__ import annotations

import os
import logging
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.firecrawl.dev/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}",
        "Content-Type": "application/json",
    }


def search(query: str, limit: int = 5) -> list[dict]:
    """Search the web and return scraped results.

    Returns list of dicts with keys: url, title, description, markdown
    """
    logger.info(f"[firecrawl] searching: {query}")
    resp = requests.post(
        f"{BASE_URL}/search",
        headers=_headers(),
        json={"query": query, "limit": limit},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("data", [])
    logger.info(f"[firecrawl] got {len(results)} results for: {query}")
    return results


def scrape_url(url: str, formats: list[str] | None = None) -> dict:
    """Scrape a single URL and return its content.

    Returns dict with keys: markdown, metadata, etc.
    """
    logger.info(f"[firecrawl] scraping: {url}")
    payload = {"url": url}
    if formats:
        payload["formats"] = formats
    resp = requests.post(
        f"{BASE_URL}/scrape",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", {})


def extract_headlines(url: str) -> list[dict]:
    """Scrape a news site and extract headlines + summaries."""
    result = scrape_url(url, formats=["markdown"])
    markdown = result.get("markdown", "")
    # Return the raw markdown — the TrendAnalyst agent will parse it
    return {"url": url, "markdown": markdown[:5000], "metadata": result.get("metadata", {})}
