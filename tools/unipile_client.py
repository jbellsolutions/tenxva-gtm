"""
Unipile API Client — LinkedIn engagement operations.

Handles: post reactions/comments retrieval, profile viewing, commenting,
liking, endorsing, connection requests, messaging, and search.

Replaces PhantomBuster for engagement operations (PhantomBuster still used for posting).
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class UnipileClient:
    """Wrapper for Unipile unified API — LinkedIn operations."""

    def __init__(self):
        self.dsn = os.environ.get("UNIPILE_DSN", "").rstrip("/")
        self.api_key = os.environ.get("UNIPILE_API_KEY", "")
        self.account_id = os.environ.get("UNIPILE_ACCOUNT_ID", "")

        if not self.dsn or not self.api_key:
            logger.warning("Unipile credentials not set (UNIPILE_DSN, UNIPILE_API_KEY)")

        self.base_url = f"{self.dsn}/api/v1"
        self.headers = {
            "Accept": "application/json",
            "X-API-KEY": self.api_key,
        }

    # ─── Account Management ────────────────────────────────────────────

    def list_accounts(self) -> list:
        """List all connected accounts."""
        resp = self._get("/accounts")
        return resp.get("items", []) if resp else []

    def get_account_id(self) -> str:
        """Get the first LinkedIn account ID (cached after first call)."""
        if self.account_id:
            return self.account_id
        accounts = self.list_accounts()
        for acct in accounts:
            if acct.get("type") == "LINKEDIN":
                self.account_id = acct["id"]
                logger.info(f"Found LinkedIn account: {self.account_id}")
                return self.account_id
        logger.error("No LinkedIn account found in Unipile")
        return ""

    # ─── Post Engagement Retrieval ─────────────────────────────────────

    def get_post_reactions(self, post_id: str, limit: int = 100) -> list:
        """
        Get all reactions (likes, etc.) on a post.
        post_id: The Unipile post ID or LinkedIn URN (urn:li:activity:XXXX)
        Returns list of reactor profiles.
        """
        reactions = []
        cursor = None
        account_id = self.get_account_id()
        while True:
            params = {"limit": min(limit - len(reactions), 100)}
            if account_id:
                params["account_id"] = account_id
            if cursor:
                params["cursor"] = cursor
            resp = self._get(f"/posts/{post_id}/reactions", params=params)
            if not resp:
                break
            items = resp.get("items", [])
            reactions.extend(items)
            cursor = resp.get("cursor")
            if not cursor or len(reactions) >= limit:
                break
        logger.info(f"Retrieved {len(reactions)} reactions for post {post_id}")
        return reactions

    def get_post_comments(self, post_id: str, limit: int = 100) -> list:
        """
        Get all comments on a post.
        Returns list of comment objects with commenter info.
        """
        comments = []
        cursor = None
        account_id = self.get_account_id()
        while True:
            params = {"limit": min(limit - len(comments), 100)}
            if account_id:
                params["account_id"] = account_id
            if cursor:
                params["cursor"] = cursor
            resp = self._get(f"/posts/{post_id}/comments", params=params)
            if not resp:
                break
            items = resp.get("items", [])
            comments.extend(items)
            cursor = resp.get("cursor")
            if not cursor or len(comments) >= limit:
                break
        logger.info(f"Retrieved {len(comments)} comments for post {post_id}")
        return comments

    # ─── Post Interactions ─────────────────────────────────────────────

    def react_to_post(self, post_id: str, reaction_type: str = "LIKE") -> dict:
        """
        Add a reaction to a post.
        reaction_type: LIKE, CELEBRATE, SUPPORT, LOVE, INSIGHTFUL, FUNNY
        """
        account_id = self.get_account_id()
        body = {"reaction_type": reaction_type}
        if account_id:
            body["account_id"] = account_id
        return self._post(f"/posts/{post_id}/reactions", body)

    def comment_on_post(self, post_id: str, text: str) -> dict:
        """Post a comment on a LinkedIn post."""
        account_id = self.get_account_id()
        body = {"text": text}
        if account_id:
            body["account_id"] = account_id
        return self._post(f"/posts/{post_id}/comments", body)

    def reply_to_comment(self, post_id: str, comment_id: str, text: str) -> dict:
        """Reply to a specific comment on a post."""
        account_id = self.get_account_id()
        body = {"text": text, "in_reply_to": comment_id}
        if account_id:
            body["account_id"] = account_id
        return self._post(f"/posts/{post_id}/comments", body)

    # ─── Profile Operations ────────────────────────────────────────────

    def get_profile(self, identifier: str) -> dict:
        """
        Retrieve a LinkedIn profile.
        identifier: Unipile user ID, LinkedIn username, or profile URL.
        This also counts as a "profile view" on LinkedIn.
        """
        resp = self._get(f"/users/{identifier}")
        if resp:
            logger.info(f"Retrieved profile: {resp.get('first_name', '')} {resp.get('last_name', '')}")
        return resp or {}

    def view_profile(self, identifier: str) -> dict:
        """View a profile (triggers LinkedIn notification to them)."""
        return self.get_profile(identifier)

    def get_user_posts(self, identifier: str, limit: int = 10) -> list:
        """Get recent posts from a user."""
        account_id = self.get_account_id()
        params = {"limit": limit}
        if account_id:
            params["account_id"] = account_id
        resp = self._get(f"/users/{identifier}/posts", params=params)
        if not resp:
            return []
        return resp.get("items", [])

    # ─── Connection Requests ───────────────────────────────────────────

    def send_connection_request(self, identifier: str, message: str = None) -> dict:
        """
        Send a LinkedIn connection request.
        identifier: user ID or profile URL.
        message: optional note (None = no message, which is what we want).
        """
        body = {"provider_id": identifier}
        if message:
            body["message"] = message[:300]  # LinkedIn limit
        account_id = self.get_account_id()
        if account_id:
            body["account_id"] = account_id
        resp = self._post("/users/invitations", body)
        if resp:
            logger.info(f"Connection request sent to {identifier}")
        return resp or {}

    def list_sent_invitations(self, limit: int = 100) -> list:
        """List sent connection requests (to track daily count)."""
        params = {"limit": limit}
        account_id = self.get_account_id()
        if account_id:
            params["account_id"] = account_id
        resp = self._get("/users/invitations/sent", params=params)
        return resp.get("items", []) if resp else []

    # ─── Messaging ─────────────────────────────────────────────────────

    def send_message(self, identifier: str, text: str) -> dict:
        """
        Send a LinkedIn message to a connection.
        identifier: user ID or attendee ID in an existing chat.
        """
        account_id = self.get_account_id()
        body = {
            "attendees_ids": [identifier],
            "text": text,
        }
        if account_id:
            body["account_id"] = account_id
        # First create or get chat
        chat = self._post("/chats", body)
        return chat or {}

    def send_message_to_chat(self, chat_id: str, text: str) -> dict:
        """Send a message to an existing chat."""
        body = {"text": text}
        return self._post(f"/chats/{chat_id}/messages", body)

    # ─── Skill Endorsement ─────────────────────────────────────────────

    def endorse_skill(self, identifier: str, skill_name: str = None) -> dict:
        """
        Endorse a user's skill on LinkedIn.
        If skill_name is None, endorses their top listed skill.
        """
        body = {"action": "ENDORSE"}
        if skill_name:
            body["skill_name"] = skill_name
        return self._post(f"/users/{identifier}/actions", body)

    # ─── Search ────────────────────────────────────────────────────────

    def search_people(self, query: str, limit: int = 25) -> list:
        """Search LinkedIn for people."""
        body = {
            "query": query,
            "type": "PEOPLE",
            "limit": limit,
        }
        account_id = self.get_account_id()
        if account_id:
            body["account_id"] = account_id
        resp = self._post("/linkedin/search", body)
        return resp.get("items", []) if resp else []

    # ─── Our Posts Management ──────────────────────────────────────────

    def get_my_posts(self, limit: int = 20) -> list:
        """Get our own recent LinkedIn posts (to check for engagement)."""
        account_id = self.get_account_id()
        if not account_id:
            return []
        # Get the LinkedIn provider user ID from the account
        my_provider_id = os.environ.get(
            "UNIPILE_LINKEDIN_USER_ID",
            "ACoAAATU8tsB_mtHtLz4nLtBsUdhmdT1Dow_4qM",
        )
        params = {"limit": limit, "account_id": account_id}
        resp = self._get(f"/users/{my_provider_id}/posts", params=params)
        return resp.get("items", []) if resp else []

    def get_post(self, post_id: str) -> dict:
        """Get a single post by ID."""
        resp = self._get(f"/posts/{post_id}")
        return resp or {}

    # ─── Post Creation ────────────────────────────────────────────────

    def create_post(self, text: str, image_path: str = None) -> dict:
        """
        Create a LinkedIn post via Unipile (multipart form data).
        Supports image and document (PDF/carousel) attachments.

        Args:
            text: Post text content
            image_path: Optional local path to an image or PDF file to attach.
                        PDF files become LinkedIn document/carousel posts.

        Returns:
            API response dict with post details
        """
        account_id = self.get_account_id()
        url = f"{self.base_url}/posts"

        files = None
        if image_path:
            import mimetypes
            from pathlib import Path
            attachment = Path(image_path)
            if attachment.exists():
                mime = mimetypes.guess_type(str(attachment))[0] or "application/octet-stream"
                # Map common extensions
                ext = attachment.suffix.lower()
                mime_map = {
                    ".pdf": "application/pdf",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }
                mime = mime_map.get(ext, mime)

                files = {
                    "attachments": (attachment.name, attachment.read_bytes(), mime),
                }
                size_kb = attachment.stat().st_size / 1024
                is_doc = ext in (".pdf", ".pptx", ".docx")
                logger.info(
                    f"Attaching {'document' if is_doc else 'image'}: "
                    f"{attachment.name} ({size_kb:.0f} KB, {mime})"
                )
            else:
                logger.warning(f"Attachment not found: {image_path}")

        try:
            headers = {"X-API-KEY": self.api_key}  # No Content-Type — let requests set multipart boundary
            resp = requests.post(
                url,
                headers=headers,
                data={"account_id": account_id, "text": text},
                files=files,
                timeout=90,  # Longer timeout for PDF uploads
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Post created successfully: {result.get('id', 'unknown')}")
            return result
        except requests.exceptions.HTTPError as e:
            logger.error(f"Unipile create_post failed: {e} — {resp.text[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Unipile create_post error: {e}")
            return {}

    def delete_post(self, post_id: str) -> dict:
        """Delete a LinkedIn post via Unipile."""
        return self._delete(f"/posts/{post_id}") or {}

    # ─── HTTP Helpers ──────────────────────────────────────────────────

    def _get(self, path: str, params: dict = None) -> dict | None:
        """GET request to Unipile API."""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Unipile GET {path} failed: {e} — {resp.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Unipile GET {path} error: {e}")
            return None

    def _post(self, path: str, body: dict = None) -> dict | None:
        """POST request to Unipile API."""
        url = f"{self.base_url}{path}"
        headers = {**self.headers, "Content-Type": "application/json"}
        try:
            resp = requests.post(url, headers=headers, json=body or {}, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Unipile POST {path} failed: {e} — {resp.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Unipile POST {path} error: {e}")
            return None

    def _delete(self, path: str) -> dict | None:
        """DELETE request to Unipile API."""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.delete(url, headers=self.headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Unipile DELETE {path} error: {e}")
            return None
