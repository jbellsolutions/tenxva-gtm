"""Retriever (rtrvr.ai) API client for lead enrichment."""

from __future__ import annotations

import os
import logging
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.rtrvr.ai/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['RETRIEVER_API_KEY']}",
        "Content-Type": "application/json",
    }


def enrich_contact(linkedin_url: str) -> dict:
    """Enrich a single LinkedIn contact with email and company data.

    Returns dict with: email, phone, company, title, location, etc.
    """
    logger.info(f"[retriever] enriching: {linkedin_url}")
    resp = requests.post(
        f"{BASE_URL}/enrich",
        headers=_headers(),
        json={"linkedin_url": linkedin_url},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"[retriever] enriched: {data.get('name', 'unknown')}")
    return data


def enrich_batch(linkedin_urls: list[str]) -> list[dict]:
    """Enrich multiple LinkedIn contacts in batch.

    Returns list of enriched contact dicts.
    """
    logger.info(f"[retriever] batch enriching {len(linkedin_urls)} contacts")
    results = []
    for url in linkedin_urls:
        try:
            result = enrich_contact(url)
            results.append(result)
        except Exception as e:
            logger.warning(f"[retriever] failed to enrich {url}: {e}")
            results.append({"linkedin_url": url, "error": str(e)})
    logger.info(f"[retriever] enriched {len([r for r in results if 'error' not in r])}/{len(linkedin_urls)}")
    return results
