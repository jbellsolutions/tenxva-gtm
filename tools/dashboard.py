"""Lightweight content review + approval dashboard.

Features:
  - Password-protected login
  - View daily content by date
  - Approve posts → adds to posting queue
  - Reject posts → removes from queue
  - Queue view → see scheduled, posted, failed posts
  - Copy button for each post
"""

from __future__ import annotations

import os
import json
import logging
import secrets
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote_plus
import threading

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))

_active_tokens: set[str] = set()


def _get_password() -> str:
    return os.environ.get("DASHBOARD_PASSWORD", "tenxva2026")


def _get_dates() -> list[str]:
    drafts_dir = DATA_DIR / "drafts"
    if not drafts_dir.exists():
        return []
    return sorted(
        [d.name for d in drafts_dir.iterdir() if d.is_dir() and d.name.startswith("202")],
        reverse=True,
    )


def _load_reviews(date_str: str) -> dict | None:
    path = DATA_DIR / "drafts" / date_str / "reviews.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "<br>")
    )


# ── Shared CSS ──────────────────────────────────────────────────────────
SHARED_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
  a { color: #3b82f6; text-decoration: none; }
  a:hover { color: #60a5fa; }
  .container { max-width: 800px; margin: 0 auto; }
  .nav { display: flex; gap: 20px; align-items: center; margin-bottom: 30px; }
  .nav a { font-size: 14px; }
  .nav .active { color: #f8fafc; font-weight: 600; }
  .header h1 { font-size: 28px; color: #f8fafc; margin-bottom: 4px; }
  .header p { color: #94a3b8; font-size: 14px; margin-bottom: 20px; }
  .cards { display: flex; flex-direction: column; gap: 12px; }
  .card { display: block; background: #1e293b; padding: 20px; border-radius: 12px; text-decoration: none; color: #e2e8f0; transition: background 0.2s; border: 1px solid #334155; }
  .card:hover { background: #293548; border-color: #3b82f6; }
  .card-date { font-size: 20px; font-weight: 700; margin-bottom: 8px; color: #f8fafc; }
  .card-stats { display: flex; gap: 12px; margin-bottom: 4px; flex-wrap: wrap; }
  .stat { font-size: 13px; padding: 3px 10px; border-radius: 20px; background: #334155; }
  .stat.approved { background: #166534; color: #86efac; }
  .stat.rejected { background: #7f1d1d; color: #fca5a5; }
  .stat.score { background: #1e3a5f; color: #93c5fd; }
  .stat.queued { background: #92400e; color: #fcd34d; }
  .card-total { font-size: 13px; color: #64748b; margin-top: 4px; }
  .post-card { background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid #334155; }
  .post-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px; }
  .post-num { font-weight: 700; font-size: 16px; color: #f8fafc; }
  .badges { display: flex; gap: 8px; flex-wrap: wrap; }
  .badge { padding: 3px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
  .post-text { background: #0f172a; padding: 16px; border-radius: 8px; font-size: 14px; line-height: 1.7; white-space: pre-wrap; word-wrap: break-word; }
  .editor-notes { margin-top: 12px; padding: 10px 14px; background: #334155; border-radius: 8px; font-size: 13px; color: #94a3b8; font-style: italic; }
  .issues { margin-top: 10px; padding: 10px 14px; background: #3b1c1c; border-radius: 8px; font-size: 13px; color: #fca5a5; }
  .issues ul { margin: 6px 0 0 18px; }
  .issues li { margin-bottom: 4px; }
  .actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
  .btn { padding: 8px 16px; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; transition: background 0.15s; }
  .btn-approve { background: #166534; color: #86efac; }
  .btn-approve:hover { background: #15803d; }
  .btn-approve:disabled { background: #334155; color: #64748b; cursor: not-allowed; }
  .btn-remove { background: #7f1d1d; color: #fca5a5; }
  .btn-remove:hover { background: #991b1b; }
  .btn-copy { background: #334155; color: #94a3b8; }
  .btn-copy:hover { background: #475569; color: #e2e8f0; }
  .btn-copy.copied { background: #166534; color: #86efac; }
  .section-title { font-size: 20px; color: #f8fafc; margin: 30px 0 15px; }
  .toast { position: fixed; bottom: 30px; right: 30px; background: #166534; color: #86efac; padding: 14px 24px; border-radius: 10px; font-size: 14px; font-weight: 600; display: none; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
  .toast.error { background: #7f1d1d; color: #fca5a5; }
  .toast.show { display: block; animation: fadeInOut 2.5s ease; }
  @keyframes fadeInOut { 0% { opacity: 0; transform: translateY(10px); } 10% { opacity: 1; transform: translateY(0); } 80% { opacity: 1; } 100% { opacity: 0; } }
  .queue-item { background: #1e293b; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; border: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
  .queue-text-preview { font-size: 13px; color: #94a3b8; max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .queue-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .logout { position: fixed; top: 20px; right: 20px; color: #64748b; text-decoration: none; font-size: 13px; }
  .logout:hover { color: #94a3b8; }
  .approve-all { margin-bottom: 20px; }
"""


# ── JavaScript ──────────────────────────────────────────────────────────
SHARED_JS = """
function showToast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => { t.className = 'toast'; }, 2600);
}

function queuePost(dateStr, postIndex, btn) {
  btn.disabled = true;
  btn.textContent = 'Queuing...';
  fetch('/api/queue/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({date: dateStr, post_index: postIndex})
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'queued') {
      btn.textContent = '✓ Queued';
      btn.classList.remove('btn-approve');
      btn.style.background = '#92400e';
      btn.style.color = '#fcd34d';
      showToast('Post queued for ' + (data.item.scheduled_for || 'posting'));
    } else if (data.status === 'already_queued') {
      btn.textContent = 'Already Queued';
      showToast('This post is already in the queue');
    } else {
      btn.textContent = 'Error';
      showToast(data.error || 'Failed to queue', true);
    }
  })
  .catch(e => { btn.textContent = 'Error'; showToast('Network error', true); });
}

function queueAllApproved(dateStr, btn) {
  btn.disabled = true;
  btn.textContent = 'Queuing all...';
  fetch('/api/queue/add-all', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({date: dateStr})
  })
  .then(r => r.json())
  .then(data => {
    btn.textContent = '✓ ' + data.queued + ' Queued';
    showToast(data.queued + ' posts queued for auto-posting');
    // Disable individual buttons
    document.querySelectorAll('.btn-approve').forEach(b => {
      b.disabled = true;
      b.textContent = '✓ Queued';
      b.style.background = '#92400e';
      b.style.color = '#fcd34d';
    });
  })
  .catch(e => { btn.disabled = false; btn.textContent = 'Error'; showToast('Failed', true); });
}

function removeFromQueue(queueId, el) {
  fetch('/api/queue/remove', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({queue_id: queueId})
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'removed') {
      el.closest('.queue-item').remove();
      showToast('Removed from queue');
    }
  });
}

function copyText(btn) {
  const temp = document.createElement('textarea');
  temp.innerHTML = btn.getAttribute('data-text');
  let text = temp.value;
  text = text.replace(/<br>/g, '\\n').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/&quot;/g, '"');
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = '✓ Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = '📋 Copy'; btn.classList.remove('copied'); }, 2000);
  });
}
"""


def _render_login() -> str:
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TenXVA Content Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
  .login {{ background: #1e293b; padding: 40px; border-radius: 16px; width: 360px; text-align: center; }}
  .login h1 {{ font-size: 24px; margin-bottom: 8px; color: #f8fafc; }}
  .login p {{ color: #94a3b8; margin-bottom: 24px; font-size: 14px; }}
  .login input {{ width: 100%; padding: 12px 16px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; border-radius: 8px; font-size: 16px; margin-bottom: 16px; }}
  .login button {{ width: 100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; font-weight: 600; }}
  .login button:hover {{ background: #2563eb; }}
</style></head>
<body>
<form class="login" method="POST" action="/login">
  <h1>TenXVA</h1>
  <p>Content Review Dashboard</p>
  <input type="password" name="password" placeholder="Password" autofocus>
  <button type="submit">Sign In</button>
</form>
</body></html>"""


def _render_nav(active: str) -> str:
    items = [
        ("Content", "/"),
        ("Posting Queue", "/queue"),
    ]
    links = []
    for label, href in items:
        cls = ' class="active"' if label.lower().startswith(active.lower()) else ""
        links.append(f'<a href="{href}"{cls}>{label}</a>')
    return f'<div class="nav">{" ".join(links)}</div>'


def _render_index(dates: list[str]) -> str:
    # Load queue stats
    from tools.posting_queue import get_queue
    queue = get_queue()
    queued_count = sum(1 for q in queue if q["status"] == "queued")
    posted_count = sum(1 for q in queue if q["status"] == "posted")

    date_cards = ""
    for d in dates:
        reviews = _load_reviews(d)
        if reviews:
            posts = reviews.get("posts", [])
            approved = sum(1 for p in posts if p.get("verdict") == "APPROVED")
            rejected = sum(1 for p in posts if p.get("verdict") == "REJECTED")
            scores = [p.get("score", 0) for p in posts if isinstance(p.get("score"), (int, float))]
            avg_score = sum(scores) / len(scores) if scores else 0

            # Check how many from this date are in queue
            in_queue = sum(1 for q in queue if q.get("source_date") == d and q["status"] in ("queued", "posted"))

            queue_badge = f'<span class="stat queued">{in_queue} queued</span>' if in_queue else ""

            date_cards += f"""
            <a href="/day/{d}" class="card">
              <div class="card-date">{d}</div>
              <div class="card-stats">
                <span class="stat approved">{approved} approved</span>
                <span class="stat rejected">{rejected} rejected</span>
                <span class="stat score">avg {avg_score:.0f}</span>
                {queue_badge}
              </div>
              <div class="card-total">{len(posts)} posts total</div>
            </a>"""
        else:
            date_cards += f"""
            <a href="/day/{d}" class="card">
              <div class="card-date">{d}</div>
              <div class="card-stats"><span class="stat">No reviews yet</span></div>
            </a>"""

    queue_summary = ""
    if queued_count or posted_count:
        queue_summary = f'<p style="margin-bottom: 20px; color: #fcd34d;">📤 {queued_count} post(s) in queue · {posted_count} posted total · <a href="/queue">View Queue →</a></p>'

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TenXVA Content Dashboard</title>
<style>{SHARED_CSS}</style></head>
<body>
<a href="/logout" class="logout">Sign Out</a>
<div class="container">
  {_render_nav("content")}
  <div class="header">
    <h1>TenXVA Content Dashboard</h1>
    <p>Daily content pipeline output — {len(dates)} days of content</p>
  </div>
  {queue_summary}
  <div class="cards">{date_cards}</div>
</div>
</body></html>"""


def _render_day(date_str: str) -> str:
    reviews = _load_reviews(date_str)
    if not reviews:
        return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{date_str}</title>
        <style>{SHARED_CSS}</style>
        </head><body><div class="container"><h1>No content for {date_str}</h1><a href="/">← Back</a></div></body></html>"""

    # Load queue to check which posts are already queued
    from tools.posting_queue import get_queue
    queue = get_queue()
    queued_indices = set()
    for q in queue:
        if q.get("source_date") == date_str and q["status"] in ("queued", "posting", "posted"):
            queued_indices.add(q.get("post_index"))

    posts = reviews.get("posts", [])
    newsletters = reviews.get("newsletters", [])
    articles = reviews.get("articles", [])

    approved_count = sum(1 for p in posts if p.get("verdict") == "APPROVED")
    rejected_count = sum(1 for p in posts if p.get("verdict") == "REJECTED")

    post_cards = ""
    for i, post in enumerate(posts):
        verdict = post.get("verdict", "UNKNOWN")
        score = post.get("score", "?")
        text = post.get("final_text", post.get("text", "No text available"))
        notes = post.get("notes", "")
        issues = post.get("issues", [])
        is_queued = i in queued_indices

        if verdict == "APPROVED":
            badge_style = "background: #166534; color: #86efac;"
            border_color = "#166534"
        elif verdict == "REJECTED":
            badge_style = "background: #7f1d1d; color: #fca5a5;"
            border_color = "#7f1d1d"
        else:
            badge_style = "background: #334155; color: #94a3b8;"
            border_color = "#334155"

        score_color = "#22c55e" if isinstance(score, int) and score >= 85 else "#f59e0b" if isinstance(score, int) and score >= 75 else "#ef4444"

        issues_html = ""
        if issues:
            issues_list = "".join(f"<li>{_escape(issue)}</li>" for issue in issues)
            issues_html = f'<div class="issues"><strong>Issues:</strong><ul>{issues_list}</ul></div>'

        # Queue button
        if is_queued:
            queue_btn = '<button class="btn" style="background: #92400e; color: #fcd34d;" disabled>✓ In Queue</button>'
        elif verdict == "APPROVED":
            queue_btn = f'<button class="btn btn-approve" onclick="queuePost(\'{date_str}\', {i}, this)">📤 Queue for Posting</button>'
        else:
            queue_btn = f'<button class="btn btn-approve" onclick="queuePost(\'{date_str}\', {i}, this)">📤 Queue Anyway</button>'

        queued_badge = '<span class="badge" style="background: #92400e; color: #fcd34d;">IN QUEUE</span>' if is_queued else ""

        post_cards += f"""
        <div class="post-card" style="border-left: 4px solid {border_color};">
          <div class="post-header">
            <span class="post-num">Post {i + 1}</span>
            <div class="badges">
              <span class="badge" style="{badge_style}">{verdict}</span>
              <span class="badge" style="background: #1e3a5f; color: {score_color};">Score: {score}</span>
              {queued_badge}
            </div>
          </div>
          <div class="post-text">{_escape(text)}</div>
          {f'<div class="editor-notes"><strong>Editor:</strong> {_escape(notes)}</div>' if notes else ''}
          {issues_html}
          <div class="actions">
            {queue_btn}
            <button class="btn btn-copy" onclick="copyText(this)" data-text="{_escape(text).replace(chr(34), '&quot;')}">📋 Copy</button>
          </div>
        </div>"""

    # Approve all button
    approve_all_btn = ""
    unapproved_approved = [i for i, p in enumerate(posts) if p.get("verdict") == "APPROVED" and i not in queued_indices]
    if unapproved_approved:
        approve_all_btn = f"""
        <div class="approve-all">
          <button class="btn btn-approve" style="padding: 12px 28px; font-size: 15px;"
                  onclick="queueAllApproved('{date_str}', this)">
            📤 Queue All {len(unapproved_approved)} Approved Posts
          </button>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TenXVA — {date_str}</title>
<style>{SHARED_CSS}</style></head>
<body>
<a href="/logout" class="logout">Sign Out</a>
<div class="container">
  {_render_nav("content")}
  <a href="/" style="font-size: 14px; margin-bottom: 20px; display: inline-block;">← All Dates</a>
  <div class="header">
    <h1>{date_str}</h1>
    <div class="card-stats" style="margin-bottom: 15px;">
      <span class="stat approved">{approved_count} approved</span>
      <span class="stat rejected">{rejected_count} rejected</span>
      <span class="stat">{len(posts)} total</span>
    </div>
  </div>

  {approve_all_btn}
  <h2 class="section-title">LinkedIn Posts</h2>
  {post_cards}
</div>
<div id="toast" class="toast"></div>
<script>{SHARED_JS}</script>
</body></html>"""


def _render_queue() -> str:
    from tools.posting_queue import get_queue
    queue = get_queue()

    queued_items = [q for q in queue if q["status"] == "queued"]
    posting_items = [q for q in queue if q["status"] == "posting"]
    posted_items = [q for q in queue if q["status"] == "posted"]
    failed_items = [q for q in queue if q["status"] == "failed"]

    def _render_queue_section(title: str, items: list, status_style: str, show_remove: bool = False) -> str:
        if not items:
            return ""
        html = f'<h2 class="section-title">{title} ({len(items)})</h2>'
        for item in items:
            text_preview = (item.get("text", "")[:100] + "...") if len(item.get("text", "")) > 100 else item.get("text", "")
            scheduled = item.get("scheduled_for", "—")
            posted_at = item.get("posted_at", "")
            error = item.get("error", "")
            queue_id = item.get("id", "")

            meta_parts = [f'<span class="badge" style="{status_style}">{item["status"].upper()}</span>']
            meta_parts.append(f'<span style="font-size: 12px; color: #64748b;">Score: {item.get("score", "?")}</span>')

            if item["status"] == "queued":
                meta_parts.append(f'<span style="font-size: 12px; color: #fcd34d;">Scheduled: {scheduled}</span>')
            elif posted_at:
                meta_parts.append(f'<span style="font-size: 12px; color: #86efac;">Posted: {posted_at[:16]}</span>')
            if error:
                meta_parts.append(f'<span style="font-size: 12px; color: #fca5a5;">{_escape(error[:80])}</span>')

            remove_btn = f'<button class="btn btn-remove" onclick="removeFromQueue(\'{queue_id}\', this)" style="padding: 4px 12px; font-size: 12px;">✕ Remove</button>' if show_remove else ""

            html += f"""
            <div class="queue-item">
              <div class="queue-text-preview">{_escape(text_preview)}</div>
              <div class="queue-meta">
                {"".join(meta_parts)}
                {remove_btn}
              </div>
            </div>"""
        return html

    sections = ""
    sections += _render_queue_section("⏳ Queued", queued_items, "background: #92400e; color: #fcd34d;", show_remove=True)
    sections += _render_queue_section("📤 Posting", posting_items, "background: #1e3a5f; color: #93c5fd;")
    sections += _render_queue_section("✅ Posted", sorted(posted_items, key=lambda x: x.get("posted_at", ""), reverse=True)[:20], "background: #166534; color: #86efac;")
    sections += _render_queue_section("❌ Failed", failed_items, "background: #7f1d1d; color: #fca5a5;", show_remove=True)

    if not queue:
        sections = '<p style="color: #64748b; text-align: center; margin-top: 60px;">No posts in queue yet. Go to a date and click "Queue for Posting" on approved posts.</p>'

    pb_configured = bool(os.environ.get("PB_POST_PHANTOM_ID", ""))
    pb_status = '<span style="color: #86efac;">✓ Connected</span>' if pb_configured else '<span style="color: #fca5a5;">✗ Not configured (PB_POST_PHANTOM_ID needed)</span>'

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TenXVA — Posting Queue</title>
<style>{SHARED_CSS}</style></head>
<body>
<a href="/logout" class="logout">Sign Out</a>
<div class="container">
  {_render_nav("posting")}
  <div class="header">
    <h1>Posting Queue</h1>
    <p>PhantomBuster LinkedIn Poster: {pb_status}</p>
    <p style="color: #64748b; font-size: 13px; margin-top: 4px;">Auto-poster checks every 15 minutes. Posts are spaced throughout the day.</p>
  </div>
  {sections}
</div>
<div id="toast" class="toast"></div>
<script>{SHARED_JS}</script>
</body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.debug(f"[dashboard] {format % args}")

    def _send_html(self, html: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _send_json(self, data: dict, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _get_token(self) -> str | None:
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("token="):
                return part[6:]
        return None

    def _is_authed(self) -> bool:
        token = self._get_token()
        return token in _active_tokens if token else False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Public endpoints (no auth required)
        if path.startswith("/visuals/"):
            # Serve visual files (images/PDFs) — public so PhantomBuster can access
            filename = path[9:]  # strip /visuals/
            # Sanitize: allow alphanumeric, underscores, hyphens, dots, slashes for subdirs
            safe_name = "".join(c for c in filename if c.isalnum() or c in "._-/")
            safe_name = safe_name.replace("..", "").lstrip("/")  # prevent traversal
            visual_path = DATA_DIR / "visuals" / safe_name
            if visual_path.exists() and visual_path.is_file():
                # Determine content type
                suffix = visual_path.suffix.lower()
                content_types = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".pdf": "application/pdf",
                    ".gif": "image/gif",
                }
                ct = content_types.get(suffix, "application/octet-stream")
                data = visual_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Visual not found")
            return

        if path == "/post-content.csv":
            # CSV endpoint for PhantomBuster to read post content
            csv_path = DATA_DIR / "posting-queue" / "current_post.csv"
            if csv_path.exists():
                csv_data = csv_path.read_text()
            else:
                csv_data = "postContent\nNo content scheduled"
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Length", str(len(csv_data.encode())))
            self.end_headers()
            self.wfile.write(csv_data.encode())
            return

        if path == "/logout":
            token = self._get_token()
            _active_tokens.discard(token)
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", "token=; Path=/; Max-Age=0")
            self.end_headers()
            return

        if not self._is_authed():
            self._send_html(_render_login())
            return

        if path in ("/", ""):
            self._send_html(_render_index(_get_dates()))
        elif path.startswith("/day/"):
            date_str = path[5:].strip("/")
            self._send_html(_render_day(date_str))
        elif path == "/queue":
            self._send_html(_render_queue())
        elif path == "/api/dates":
            self._send_json(_get_dates())
        elif path.startswith("/api/reviews/"):
            date_str = path[13:].strip("/")
            self._send_json(_load_reviews(date_str) or {})
        elif path == "/api/queue":
            from tools.posting_queue import get_queue
            self._send_json(get_queue())
        else:
            self._send_html("<h1>404</h1>", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/login":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            params = {}
            for pair in body.split("&"):
                if "=" in pair:
                    key, val = pair.split("=", 1)
                    params[key] = unquote_plus(val)

            if params.get("password") == _get_password():
                token = secrets.token_hex(32)
                _active_tokens.add(token)
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", f"token={token}; Path=/; HttpOnly; Max-Age=604800")
                self.end_headers()
            else:
                self._send_html(_render_login(), 401)
            return

        # All API endpoints below require auth
        if not self._is_authed():
            self._send_json({"error": "unauthorized"}, 401)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, 400)
            return

        if path == "/api/queue/add":
            from tools.posting_queue import add_to_queue
            date_str = data.get("date", "")
            post_index = data.get("post_index", 0)

            # Load the post text from reviews
            reviews = _load_reviews(date_str)
            if not reviews:
                self._send_json({"error": "no reviews for that date"}, 404)
                return

            posts = reviews.get("posts", [])
            if post_index < 0 or post_index >= len(posts):
                self._send_json({"error": "invalid post index"}, 400)
                return

            post = posts[post_index]
            text = post.get("final_text", post.get("text", ""))
            score = post.get("score", 0)

            result = add_to_queue(date_str, post_index, text, score)
            self._send_json(result)

        elif path == "/api/queue/add-all":
            from tools.posting_queue import add_to_queue
            date_str = data.get("date", "")

            reviews = _load_reviews(date_str)
            if not reviews:
                self._send_json({"error": "no reviews for that date"}, 404)
                return

            posts = reviews.get("posts", [])
            queued = 0
            for i, post in enumerate(posts):
                if post.get("verdict") == "APPROVED":
                    text = post.get("final_text", post.get("text", ""))
                    score = post.get("score", 0)
                    r = add_to_queue(date_str, i, text, score)
                    if r.get("status") == "queued":
                        queued += 1

            self._send_json({"status": "ok", "queued": queued})

        elif path == "/api/queue/remove":
            from tools.posting_queue import remove_from_queue
            queue_id = data.get("queue_id", "")
            result = remove_from_queue(queue_id)
            self._send_json(result)

        else:
            self._send_json({"error": "not found"}, 404)


def start_dashboard(port: int | None = None, background: bool = True):
    port = port or DASHBOARD_PORT
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    logger.info(f"[dashboard] starting on port {port}")

    if background:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"[dashboard] running in background on :{port}")
        return server
    else:
        server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Starting dashboard on http://0.0.0.0:{DASHBOARD_PORT}")
    start_dashboard(background=False)
