"""PhantomBuster API client for LinkedIn WRITE operations (posts, comments, replies).

The LinkedIn Auto Poster phantom reads from a CSV/spreadsheet URL.
We serve a CSV from our dashboard at /post-content.csv and point the phantom to it.
"""

from __future__ import annotations

import os
import csv
import json
import time
import logging
from io import StringIO
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.phantombuster.com/api/v2"
PROJECT_ROOT = Path(__file__).parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "posting-queue" / "current_post.csv"
# The droplet serves this CSV at http://<IP>:8080/post-content.csv
DROPLET_CSV_URL = f"http://104.131.172.48:8080/post-content.csv"


def _headers() -> dict:
    return {
        "X-Phantombuster-Key": os.environ["PHANTOMBUSTER_API_KEY"],
        "Content-Type": "application/json",
    }


def _get_stored_argument(phantom_id: str) -> dict:
    """Fetch the phantom's stored argument config (includes sessionCookie etc)."""
    resp = requests.get(
        f"{BASE_URL}/agents/fetch",
        headers=_headers(),
        params={"id": phantom_id},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return json.loads(data.get("argument", "{}"))


def _write_post_csv(text: str, image_url: str | None = None):
    """Write the post content to a CSV file that the dashboard serves.

    PhantomBuster reads every row as content to post.
    If image_url is provided, writes two columns: text + image URL.
    """
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if image_url:
            writer.writerow([text, image_url])
            logger.info(f"[phantombuster] wrote post CSV with image to {CSV_PATH}")
        else:
            writer.writerow([text])
            logger.info(f"[phantombuster] wrote post CSV to {CSV_PATH}")


def launch_phantom(phantom_id: str, arguments: dict, timeout: int = 120) -> dict:
    """Launch a PhantomBuster phantom with merged arguments and wait for results.

    Merges the stored phantom config (sessionCookie, userAgent, etc.)
    with the provided arguments so the phantom has everything it needs.
    """
    logger.info(f"[phantombuster] launching phantom {phantom_id}")

    # Get stored config and merge with provided arguments
    stored_args = _get_stored_argument(phantom_id)
    merged = {**stored_args, **arguments}

    # Launch the phantom
    resp = requests.post(
        f"{BASE_URL}/agents/launch",
        headers=_headers(),
        json={"id": phantom_id, "argument": merged},
        timeout=30,
    )
    resp.raise_for_status()
    container_id = resp.json().get("containerId")

    # Poll until finished
    start = time.time()
    while time.time() - start < timeout:
        status_resp = requests.get(
            f"{BASE_URL}/containers/fetch",
            headers=_headers(),
            params={"id": container_id},
            timeout=15,
        )
        status_resp.raise_for_status()
        container = status_resp.json()
        status = container.get("status")
        if status == "finished":
            return container
        if status == "error":
            logger.error(f"[phantombuster] phantom {phantom_id} failed")
            return container
        time.sleep(5)

    logger.warning(f"[phantombuster] phantom {phantom_id} timed out")
    return {}


def get_phantom_output(phantom_id: str) -> dict:
    """Get the output/result of a phantom's last run."""
    resp = requests.get(
        f"{BASE_URL}/agents/fetch-output",
        headers=_headers(),
        params={"id": phantom_id},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def publish_post(phantom_id: str, text: str, image_url: str | None = None) -> dict:
    """Publish a LinkedIn post via PhantomBuster LinkedIn Auto Poster.

    Flow:
    1. Write post content to CSV file (served by dashboard at /post-content.csv)
    2. Launch phantom with spreadsheetUrl pointing to our CSV
    3. Phantom reads CSV, posts to LinkedIn
    """
    # Step 1: Write content to CSV (with optional image)
    _write_post_csv(text, image_url)

    # Step 2: Launch phantom pointing to our CSV
    args = {
        "spreadsheetUrl": DROPLET_CSV_URL,
        "numberTweetsPerLaunch": 1,
    }
    return launch_phantom(phantom_id, args, timeout=180)


def post_comment(phantom_id: str, post_url: str, comment_text: str) -> dict:
    """Post a comment on a LinkedIn post via PhantomBuster LinkedIn Auto Commenter."""
    return launch_phantom(phantom_id, {
        "postUrl": post_url,
        "commentContent": comment_text,
    })


def reply_to_comment(phantom_id: str, comment_url: str, reply_text: str) -> dict:
    """Reply to a comment on LinkedIn."""
    return launch_phantom(phantom_id, {
        "commentUrl": comment_url,
        "replyContent": reply_text,
    })
