"""
Dashboard Messaging Module — adds LinkedIn messaging UI to the existing dashboard.

Provides:
- /messages — inbox view with all conversations
- /messages/<chat_id> — single conversation thread view
- /messages/<chat_id>/send — send a message (POST)
- /api/messages/unread — unread message count for nav badge
- /api/messages/sequences — active automation sequences

To integrate: import and call add_messaging_routes(app) from dashboard.py
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)


def get_unipile_headers():
    """Get Unipile API headers."""
    import os
    return {
        "Accept": "application/json",
        "X-API-KEY": os.environ.get("UNIPILE_API_KEY", ""),
    }


def get_unipile_base():
    """Get Unipile base URL."""
    import os
    dsn = os.environ.get("UNIPILE_DSN", "").rstrip("/")
    return f"{dsn}/api/v1"


def get_account_id():
    import os
    return os.environ.get("UNIPILE_ACCOUNT_ID", "kM1vZlgEQPCdxY7Sp5H4nA")


def add_messaging_routes(handler_class):
    """
    Add messaging routes to the dashboard HTTP handler.
    Call this to extend the existing dashboard with messaging.

    Since the dashboard uses a simple HTTPServer, we patch the do_GET/do_POST handlers.
    """
    # Store original handlers
    _original_do_GET = handler_class.do_GET
    _original_do_POST = handler_class.do_POST if hasattr(handler_class, 'do_POST') else None

    def new_do_GET(self):
        path = self.path.split("?")[0]

        if path == "/messages":
            self._serve_messages_inbox()
        elif path.startswith("/messages/") and not path.endswith("/send"):
            chat_id = path.split("/messages/")[1].rstrip("/")
            self._serve_conversation(chat_id)
        elif path == "/api/messages/unread":
            self._serve_unread_count()
        elif path == "/api/messages/sequences":
            self._serve_sequences()
        else:
            _original_do_GET(self)

    def new_do_POST(self):
        path = self.path.split("?")[0]

        if path.startswith("/messages/") and path.endswith("/send"):
            parts = path.split("/")
            chat_id = parts[2]
            self._handle_send_message(chat_id)
        elif _original_do_POST:
            _original_do_POST(self)
        else:
            self.send_error(405, "Method Not Allowed")

    # ─── Inbox View ────────────────────────────────────────────────────

    def _serve_messages_inbox(self):
        """Serve the messaging inbox page."""
        import requests

        base = get_unipile_base()
        headers = get_unipile_headers()
        account_id = get_account_id()

        # Get chats
        try:
            resp = requests.get(
                f"{base}/chats",
                headers=headers,
                params={"account_id": account_id, "limit": 50},
                timeout=15,
            )
            chats = resp.json().get("items", []) if resp.ok else []
        except Exception as e:
            chats = []
            logger.error(f"Error fetching chats: {e}")

        # Get attendee names for each chat
        chat_list = []
        for chat in chats[:30]:  # Limit to 30 for speed
            chat_id = chat.get("id", "")
            attendee_id = chat.get("attendee_provider_id", "")
            unread = chat.get("unread_count", 0)
            timestamp = chat.get("timestamp", "")

            # Get attendee info
            name = "Unknown"
            headline = ""
            picture = ""
            try:
                aresp = requests.get(
                    f"{base}/chats/{chat_id}/attendees",
                    headers=headers,
                    timeout=10,
                )
                if aresp.ok:
                    attendees = aresp.json().get("items", [])
                    for a in attendees:
                        if not a.get("is_self"):
                            name = a.get("name", "Unknown")
                            headline = a.get("specifics", {}).get("occupation", "")
                            picture = a.get("picture_url", "")
                            break
            except Exception:
                pass

            # Get last message preview
            preview = ""
            try:
                mresp = requests.get(
                    f"{base}/chats/{chat_id}/messages",
                    headers=headers,
                    params={"limit": 1},
                    timeout=10,
                )
                if mresp.ok:
                    msgs = mresp.json().get("items", [])
                    if msgs:
                        preview = (msgs[0].get("text", "") or "")[:100]
            except Exception:
                pass

            chat_list.append({
                "id": chat_id,
                "name": name,
                "headline": headline,
                "picture": picture,
                "unread": unread,
                "preview": preview,
                "timestamp": timestamp,
            })

        # Load sequence status
        seq_file = Path("data/messaging/sequences.json")
        sequences = {}
        if seq_file.exists():
            try:
                sequences = json.loads(seq_file.read_text())
            except Exception:
                pass

        html = _build_inbox_html(chat_list, sequences)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    # ─── Conversation View ─────────────────────────────────────────────

    def _serve_conversation(self, chat_id):
        """Serve a single conversation thread."""
        import requests

        base = get_unipile_base()
        headers = get_unipile_headers()

        # Get attendee info
        name = "Unknown"
        headline = ""
        picture = ""
        profile_url = ""
        try:
            aresp = requests.get(
                f"{base}/chats/{chat_id}/attendees",
                headers=headers,
                timeout=10,
            )
            if aresp.ok:
                for a in aresp.json().get("items", []):
                    if not a.get("is_self"):
                        name = a.get("name", "Unknown")
                        headline = a.get("specifics", {}).get("occupation", "")
                        picture = a.get("picture_url", "")
                        profile_url = a.get("profile_url", "")
                        break
        except Exception:
            pass

        # Get messages
        messages = []
        try:
            mresp = requests.get(
                f"{base}/chats/{chat_id}/messages",
                headers=headers,
                params={"limit": 50},
                timeout=15,
            )
            if mresp.ok:
                messages = mresp.json().get("items", [])
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")

        # Reverse to chronological order
        messages.reverse()

        # Check sequence status
        seq_file = Path("data/messaging/sequences.json")
        seq_info = None
        if seq_file.exists():
            try:
                seqs = json.loads(seq_file.read_text())
                seq_info = seqs.get(chat_id)
            except Exception:
                pass

        html = _build_conversation_html(chat_id, name, headline, picture, profile_url, messages, seq_info)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    # ─── Send Message Handler ──────────────────────────────────────────

    def _handle_send_message(self, chat_id):
        """Handle POST to send a message."""
        import requests
        from urllib.parse import parse_qs

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        params = parse_qs(body)
        text = params.get("message", [""])[0]

        if not text:
            self.send_response(302)
            self.send_header("Location", f"/messages/{chat_id}")
            self.end_headers()
            return

        base = get_unipile_base()
        headers = {**get_unipile_headers(), "Content-Type": "application/json"}

        try:
            resp = requests.post(
                f"{base}/chats/{chat_id}/messages",
                headers=headers,
                json={"text": text},
                timeout=15,
            )
            if resp.ok:
                logger.info(f"Message sent to chat {chat_id}")
            else:
                logger.error(f"Failed to send message: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

        self.send_response(302)
        self.send_header("Location", f"/messages/{chat_id}")
        self.end_headers()

    # ─── API: Unread Count ─────────────────────────────────────────────

    def _serve_unread_count(self):
        """Return JSON with unread message count."""
        import requests

        base = get_unipile_base()
        headers = get_unipile_headers()
        account_id = get_account_id()

        try:
            resp = requests.get(
                f"{base}/chats",
                headers=headers,
                params={"account_id": account_id, "limit": 50},
                timeout=10,
            )
            if resp.ok:
                chats = resp.json().get("items", [])
                unread = sum(c.get("unread_count", 0) for c in chats)
            else:
                unread = 0
        except Exception:
            unread = 0

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"unread": unread}).encode())

    # ─── API: Sequences ────────────────────────────────────────────────

    def _serve_sequences(self):
        """Return JSON with active automation sequences."""
        seq_file = Path("data/messaging/sequences.json")
        sequences = {}
        if seq_file.exists():
            try:
                sequences = json.loads(seq_file.read_text())
            except Exception:
                pass

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(sequences).encode())

    # Patch the handler class
    handler_class.do_GET = new_do_GET
    handler_class.do_POST = new_do_POST
    handler_class._serve_messages_inbox = _serve_messages_inbox
    handler_class._serve_conversation = _serve_conversation
    handler_class._handle_send_message = _handle_send_message
    handler_class._serve_unread_count = _serve_unread_count
    handler_class._serve_sequences = _serve_sequences


# ─── HTML Templates ────────────────────────────────────────────────────

def _build_inbox_html(chats: list, sequences: dict) -> str:
    """Build the messaging inbox HTML."""
    chat_rows = ""
    for c in chats:
        unread_badge = f'<span class="badge">{c["unread"]}</span>' if c["unread"] else ""
        seq_status = ""
        if c["id"] in sequences:
            s = sequences[c["id"]]
            seq_status = f'<span class="seq-badge">{s.get("trigger", "")} (step {s.get("current_step", "?")})</span>'

        pic = f'<img src="{c["picture"]}" class="avatar">' if c["picture"] else '<div class="avatar placeholder">?</div>'
        ts = c["timestamp"][:16].replace("T", " ") if c["timestamp"] else ""
        preview_escaped = c["preview"].replace("<", "&lt;").replace(">", "&gt;")

        chat_rows += f"""
        <a href="/messages/{c['id']}" class="chat-row {'unread' if c['unread'] else ''}">
            {pic}
            <div class="chat-info">
                <div class="chat-header">
                    <span class="chat-name">{c['name']}</span>
                    {unread_badge}
                    {seq_status}
                    <span class="chat-time">{ts}</span>
                </div>
                <div class="chat-headline">{c['headline'][:60]}</div>
                <div class="chat-preview">{preview_escaped}</div>
            </div>
        </a>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>TenXVA Messages</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; }}
        .header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ font-size: 20px; color: #0096FF; }}
        .header a {{ color: #8b949e; text-decoration: none; font-size: 14px; }}
        .header a:hover {{ color: #0096FF; }}
        .chat-list {{ max-width: 800px; margin: 0 auto; }}
        .chat-row {{ display: flex; gap: 12px; padding: 16px 24px; border-bottom: 1px solid #21262d; text-decoration: none; color: inherit; transition: background 0.15s; }}
        .chat-row:hover {{ background: #161b22; }}
        .chat-row.unread {{ background: #161b22; border-left: 3px solid #0096FF; }}
        .avatar {{ width: 48px; height: 48px; border-radius: 50%; flex-shrink: 0; object-fit: cover; }}
        .avatar.placeholder {{ background: #30363d; display: flex; align-items: center; justify-content: center; color: #8b949e; }}
        .chat-info {{ flex: 1; min-width: 0; }}
        .chat-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
        .chat-name {{ font-weight: 600; font-size: 15px; }}
        .chat-time {{ color: #8b949e; font-size: 12px; margin-left: auto; }}
        .chat-headline {{ color: #8b949e; font-size: 13px; margin-bottom: 4px; }}
        .chat-preview {{ color: #8b949e; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .badge {{ background: #0096FF; color: white; font-size: 11px; padding: 2px 6px; border-radius: 10px; font-weight: 600; }}
        .seq-badge {{ background: #e94560; color: white; font-size: 10px; padding: 2px 6px; border-radius: 10px; font-weight: 500; }}
        .empty {{ text-align: center; padding: 60px; color: #8b949e; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>LinkedIn Messages</h1>
        <a href="/">&larr; Dashboard</a>
    </div>
    <div class="chat-list">
        {chat_rows if chat_rows else '<div class="empty">No conversations yet</div>'}
    </div>
    <script>
        // Auto-refresh unread count every 60 seconds
        setInterval(() => {{ fetch('/api/messages/unread').then(r => r.json()).then(d => {{
            document.title = d.unread > 0 ? `(${{d.unread}}) TenXVA Messages` : 'TenXVA Messages';
        }}); }}, 60000);
    </script>
</body>
</html>"""


def _build_conversation_html(chat_id: str, name: str, headline: str, picture: str,
                               profile_url: str, messages: list, seq_info: dict) -> str:
    """Build the conversation thread HTML."""
    msg_html = ""
    for msg in messages:
        is_mine = msg.get("is_sender", 0)
        text = (msg.get("text", "") or "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        ts = msg.get("timestamp", "")[:16].replace("T", " ")
        css_class = "mine" if is_mine else "theirs"
        sender = "You" if is_mine else name.split()[0]

        msg_html += f"""
        <div class="msg {css_class}">
            <div class="msg-sender">{sender} <span class="msg-time">{ts}</span></div>
            <div class="msg-text">{text}</div>
        </div>"""

    seq_html = ""
    if seq_info:
        seq_html = f"""
        <div class="seq-panel">
            <strong>Automation:</strong> {seq_info.get('trigger', '')} |
            Step {seq_info.get('current_step', '?')} |
            Status: {seq_info.get('status', 'unknown')} |
            Started: {seq_info.get('started', '')[:10]}
        </div>"""

    profile_link = f'<a href="{profile_url}" target="_blank" class="profile-link">View Profile</a>' if profile_url else ""
    pic_html = f'<img src="{picture}" class="conv-avatar">' if picture else ""

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Chat with {name} | TenXVA</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; display: flex; flex-direction: column; height: 100vh; }}
        .header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 12px 24px; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }}
        .header a.back {{ color: #8b949e; text-decoration: none; font-size: 20px; }}
        .conv-avatar {{ width: 36px; height: 36px; border-radius: 50%; }}
        .conv-info h2 {{ font-size: 16px; margin-bottom: 2px; }}
        .conv-info .hl {{ color: #8b949e; font-size: 12px; }}
        .profile-link {{ color: #0096FF; text-decoration: none; font-size: 12px; margin-left: auto; }}
        .seq-panel {{ background: #1a1a2e; border: 1px solid #e94560; padding: 8px 16px; font-size: 12px; color: #e94560; flex-shrink: 0; }}
        .messages {{ flex: 1; overflow-y: auto; padding: 16px 24px; display: flex; flex-direction: column; gap: 12px; }}
        .msg {{ max-width: 70%; padding: 10px 14px; border-radius: 12px; }}
        .msg.mine {{ align-self: flex-end; background: #0096FF; color: white; border-bottom-right-radius: 4px; }}
        .msg.theirs {{ align-self: flex-start; background: #21262d; border-bottom-left-radius: 4px; }}
        .msg-sender {{ font-size: 11px; font-weight: 600; margin-bottom: 4px; opacity: 0.7; }}
        .msg-time {{ font-weight: 400; }}
        .msg-text {{ font-size: 14px; line-height: 1.5; }}
        .compose {{ background: #161b22; border-top: 1px solid #30363d; padding: 12px 24px; flex-shrink: 0; }}
        .compose form {{ display: flex; gap: 8px; }}
        .compose textarea {{ flex: 1; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; color: #e6edf3; font-size: 14px; font-family: inherit; resize: none; min-height: 44px; max-height: 120px; }}
        .compose textarea:focus {{ outline: none; border-color: #0096FF; }}
        .compose button {{ background: #0096FF; color: white; border: none; border-radius: 8px; padding: 10px 20px; font-size: 14px; font-weight: 600; cursor: pointer; }}
        .compose button:hover {{ background: #0077cc; }}
    </style>
</head>
<body>
    <div class="header">
        <a href="/messages" class="back">&larr;</a>
        {pic_html}
        <div class="conv-info">
            <h2>{name}</h2>
            <div class="hl">{headline[:80]}</div>
        </div>
        {profile_link}
    </div>
    {seq_html}
    <div class="messages" id="messages">
        {msg_html}
    </div>
    <div class="compose">
        <form method="POST" action="/messages/{chat_id}/send">
            <textarea name="message" placeholder="Type a message..." rows="1"
                onkeydown="if(event.key==='Enter'&&!event.shiftKey){{this.form.submit();event.preventDefault();}}"></textarea>
            <button type="submit">Send</button>
        </form>
    </div>
    <script>
        // Scroll to bottom
        const msgs = document.getElementById('messages');
        msgs.scrollTop = msgs.scrollHeight;
        // Auto-refresh every 30 seconds
        setInterval(() => location.reload(), 30000);
    </script>
</body>
</html>"""
