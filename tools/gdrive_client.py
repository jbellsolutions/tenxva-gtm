"""Google Drive client for uploading daily content for review."""

from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def _get_service():
    """Build Google Drive API service using service account credentials."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not creds_path or not os.path.exists(creds_path):
            logger.warning("[gdrive] no service account JSON found, skipping Drive upload")
            return None

        creds = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        return build("drive", "v3", credentials=creds)
    except ImportError:
        logger.warning("[gdrive] google-api-python-client not installed, skipping Drive upload")
        return None
    except Exception as e:
        logger.error(f"[gdrive] failed to init Drive service: {e}")
        return None


def _find_or_create_folder(service, name: str, parent_id: str | None = None) -> str:
    """Find a folder by name (under parent), or create it."""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    # Create folder
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    logger.info(f"[gdrive] created folder: {name} ({folder['id']})")
    return folder["id"]


def _upload_file(service, filepath: str, parent_id: str, filename: str | None = None) -> str:
    """Upload a file to a Drive folder. Returns file ID."""
    from googleapiclient.http import MediaFileUpload

    fname = filename or os.path.basename(filepath)
    media = MediaFileUpload(filepath, resumable=True)
    metadata = {
        "name": fname,
        "parents": [parent_id],
    }

    # Check if file already exists, update if so
    query = f"name='{fname}' and '{parent_id}' in parents and trashed=false"
    existing = service.files().list(q=query, spaces="drive", fields="files(id)").execute()
    existing_files = existing.get("files", [])

    if existing_files:
        # Update existing file
        file_id = existing_files[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
        logger.info(f"[gdrive] updated: {fname}")
        return file_id
    else:
        # Create new file
        file = service.files().create(body=metadata, media_body=media, fields="id").execute()
        logger.info(f"[gdrive] uploaded: {fname}")
        return file["id"]


def upload_daily_content(date_str: str | None = None) -> dict:
    """Upload all content for a given date to Google Drive.

    Creates structure:
        TenXVA Content / 2026-03-07 / posts.json
                                     longform.json
                                     reviews.json
                                     trends.json
                                     briefs.json
                                     published.json
                                     SUMMARY.txt  (human-readable)
    """
    service = _get_service()
    if not service:
        return {"status": "skipped", "reason": "Google Drive not configured"}

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    root_folder_id = os.environ.get("GDRIVE_FOLDER_ID", "")

    try:
        # Create/find root content folder
        if root_folder_id:
            content_root = root_folder_id
        else:
            content_root = _find_or_create_folder(service, "TenXVA Content")

        # Create date folder
        date_folder = _find_or_create_folder(service, date_str, content_root)

        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
        uploaded = []

        # Upload drafts (posts, longform, reviews)
        drafts_dir = data_dir / "drafts" / date_str
        if drafts_dir.exists():
            for f in drafts_dir.glob("*.json"):
                _upload_file(service, str(f), date_folder)
                uploaded.append(f.name)

        # Upload trends
        trends_file = data_dir / "trend-intel" / f"{date_str}_trends.json"
        if trends_file.exists():
            _upload_file(service, str(trends_file), date_folder, "trends.json")
            uploaded.append("trends.json")

        # Upload briefs
        briefs_file = data_dir / "briefs" / f"{date_str}_briefs.json"
        if briefs_file.exists():
            _upload_file(service, str(briefs_file), date_folder, "briefs.json")
            uploaded.append("briefs.json")

        # Upload published
        published_file = data_dir / "published" / f"{date_str}_published.json"
        if published_file.exists():
            _upload_file(service, str(published_file), date_folder, "published.json")
            uploaded.append("published.json")

        # Create and upload human-readable summary
        summary = _build_summary(data_dir, date_str)
        if summary:
            summary_path = data_dir / "drafts" / date_str / "SUMMARY.txt"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(summary)
            _upload_file(service, str(summary_path), date_folder, "SUMMARY.txt")
            uploaded.append("SUMMARY.txt")

        logger.info(f"[gdrive] uploaded {len(uploaded)} files to Drive for {date_str}")
        return {"status": "success", "date": date_str, "files_uploaded": uploaded}

    except Exception as e:
        logger.error(f"[gdrive] upload failed: {e}")
        return {"status": "error", "error": str(e)}


def _build_summary(data_dir: Path, date_str: str) -> str | None:
    """Build a human-readable summary of the day's content."""
    lines = [
        f"TenXVA Content Summary — {date_str}",
        "=" * 50,
        "",
    ]

    # Read reviews (has final approved text)
    reviews_path = data_dir / "drafts" / date_str / "reviews.json"
    if not reviews_path.exists():
        return None

    try:
        with open(reviews_path) as f:
            reviews = json.load(f)
    except Exception:
        return None

    # Posts
    posts = reviews.get("posts", [])
    approved_posts = [p for p in posts if p.get("verdict") == "APPROVED"]
    rejected_posts = [p for p in posts if p.get("verdict") == "REJECTED"]

    lines.append(f"LINKEDIN POSTS: {len(approved_posts)} approved, {len(rejected_posts)} rejected")
    lines.append("-" * 50)

    for i, post in enumerate(approved_posts, 1):
        lines.append(f"\n--- POST {i} (Score: {post.get('score', 'N/A')}) ---")
        lines.append(post.get("final_text", post.get("text", "No text")))
        lines.append(f"\nEditor notes: {post.get('notes', 'None')}")
        lines.append("")

    if rejected_posts:
        lines.append(f"\n--- REJECTED ({len(rejected_posts)}) ---")
        for rp in rejected_posts:
            lines.append(f"  ID: {rp.get('content_id', '?')}")
            lines.append(f"  Score: {rp.get('score', '?')}")
            lines.append(f"  Issues: {', '.join(rp.get('issues', []))}")
            lines.append("")

    # Newsletters / Articles
    newsletters = reviews.get("newsletters", [])
    articles = reviews.get("articles", [])

    if newsletters:
        lines.append(f"\nNEWSLETTERS: {len(newsletters)}")
        lines.append("-" * 50)
        for nl in newsletters:
            if nl.get("verdict") == "APPROVED":
                lines.append(f"\n--- NEWSLETTER (Score: {nl.get('score', 'N/A')}) ---")
                lines.append(nl.get("final_text", "")[:2000])
                lines.append("")

    if articles:
        lines.append(f"\nARTICLES: {len(articles)}")
        lines.append("-" * 50)
        for art in articles:
            if art.get("verdict") == "APPROVED":
                lines.append(f"\n--- ARTICLE (Score: {art.get('score', 'N/A')}) ---")
                lines.append(art.get("final_text", "")[:2000])
                lines.append("")

    return "\n".join(lines)
