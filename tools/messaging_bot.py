"""
LinkedIn Messaging Bot — automated messaging sequences via Unipile.

Handles:
1. "Custom Prompt" connection trigger → 3-message sequence
2. "AI VA" comment trigger → DM sequence
3. Scheduled follow-ups (48hr no-response)
4. Polling for new messages + connection requests

Sequences are tracked in data/messaging/sequences.json
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from agents.base import BaseAgent
from agents.quality.quality_gate import QualityGate
from tools.unipile_client import UnipileClient

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
MSG_DIR = DATA_DIR / "messaging"
SEQUENCES_FILE = MSG_DIR / "sequences.json"
PROCESSED_FILE = MSG_DIR / "processed_connections.json"


# ─── Message Templates ────────────────────────────────────────────────

CUSTOM_PROMPT_SEQUENCE = {
    "trigger": "custom_prompt",
    "messages": {
        1: {
            "template": "Hey {first_name} \u2014 thanks for connecting. Saw your note.\n\nTell me what you're working on. Project, problem, process, idea \u2014 doesn't matter what stage it's at. Just give me the short version and I'll put together a custom prompt you can use in Claude Code to build it. Usually one shot.",
            "delay_hours": 0,
            "wait_for_reply": True,
        },
        2: {
            "template": "GENERATE_CUSTOM_PROMPT",  # Special: uses Claude to generate custom prompt
            "delay_hours": 0,
            "wait_for_reply": True,
            "followup_template": "Perfect. Here's the prompt I'd use:\n\n{custom_prompt}\n\nDrop this into Claude Code and let it run. Don't guide it manually \u2014 give it the full instruction up front and let it build. If it asks clarifying questions, answer them and tell it to keep going.\n\nIf you get stuck or don't know what to do next, just come back and describe exactly where you are and what you're seeing. I'll tell you the next move.",
        },
        3: {
            "template": "Still here if you want that prompt. Just tell me what you're building and I'll get it to you.",
            "delay_hours": 48,
            "wait_for_reply": False,
            "condition": "no_reply",
        },
    },
}

AI_VA_SEQUENCE = {
    "trigger": "ai_va_comment",
    "messages": {
        1: {
            "template": "Hey {first_name} \u2014 saw your comment on the post.\n\nHere's what we're doing right now: we recruit, hire, and personally train VAs from the Philippines on AI-native workflows. Claude Code, Cursor, ClickUp Brain \u2014 the full stack.\n\nThey work 6 hours a day, full focus, for $5/hr. And for the first 30 days, I'm managing their development alongside you.\n\nWhat's the biggest thing eating your time right now? That'll tell me if there's a fit here.",
            "delay_hours": 0,
            "wait_for_reply": True,
        },
        2: {
            "template": "GENERATE_CUSTOM_RESPONSE",
            "delay_hours": 0,
            "wait_for_reply": True,
        },
        3: {
            "template": "Hey {first_name} \u2014 just circling back. If you're still thinking about offloading some of that work, I'm here. No rush.",
            "delay_hours": 48,
            "wait_for_reply": False,
            "condition": "no_reply",
        },
    },
}


class MessagingBot(BaseAgent):
    """
    LinkedIn messaging automation via Unipile.
    Monitors for triggers and manages message sequences.
    """

    def __init__(self):
        super().__init__(name="messaging_bot", prompt_file=None)
        self.unipile = UnipileClient()
        self.quality_gate = QualityGate()
        MSG_DIR.mkdir(parents=True, exist_ok=True)

    # ─── Main Loop ─────────────────────────────────────────────────────

    def run_messaging_cycle(self) -> dict:
        """
        Full messaging cycle:
        1. Check for new connections with 'custom prompt' note
        2. Check for 'AI VA' comments that need DMs
        3. Check for replies to active sequences → generate next message
        4. Send scheduled follow-ups (48hr no-response)
        """
        result = {
            "new_connections_processed": 0,
            "ai_va_dms_sent": 0,
            "replies_processed": 0,
            "followups_sent": 0,
            "errors": 0,
        }

        try:
            # Step 1: Check for new connections with "custom prompt"
            result["new_connections_processed"] = self._process_new_connections()
        except Exception as e:
            logger.error(f"Error processing connections: {e}")
            result["errors"] += 1

        try:
            # Step 2: Process active sequences (check for replies, send follow-ups)
            seq_result = self._process_active_sequences()
            result["replies_processed"] = seq_result.get("replies", 0)
            result["followups_sent"] = seq_result.get("followups", 0)
        except Exception as e:
            logger.error(f"Error processing sequences: {e}")
            result["errors"] += 1

        logger.info(f"Messaging cycle complete: {result}")
        return result

    # ─── Connection Processing ─────────────────────────────────────────

    def _process_new_connections(self) -> int:
        """Check for new connections with 'custom prompt' in note."""
        processed = self._load_processed()
        count = 0

        # Get recent chats to find new conversations
        chats = self._get_recent_chats(limit=20)

        for chat in chats:
            chat_id = chat.get("id", "")
            attendee_id = chat.get("attendee_provider_id", "")

            if chat_id in processed:
                continue

            # Check messages for connection note / trigger
            messages = self._get_chat_messages(chat_id, limit=5)
            if not messages:
                continue

            # Check if this is a new connection with "custom prompt" or similar trigger
            for msg in messages:
                text = (msg.get("text", "") or "").lower()
                is_sender = msg.get("is_sender", 0)

                # Only check incoming messages (not from us)
                if is_sender:
                    continue

                if "custom prompt" in text:
                    # Trigger custom prompt sequence
                    first_name = self._extract_first_name(chat, messages)
                    self._start_sequence(chat_id, attendee_id, first_name, "custom_prompt")
                    # Send Message 1
                    msg_text = CUSTOM_PROMPT_SEQUENCE["messages"][1]["template"].format(
                        first_name=first_name
                    )
                    self._send_message(chat_id, msg_text)
                    processed[chat_id] = {
                        "trigger": "custom_prompt",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    count += 1
                    break

                elif "ai va" in text:
                    # Trigger AI VA sequence
                    first_name = self._extract_first_name(chat, messages)
                    self._start_sequence(chat_id, attendee_id, first_name, "ai_va_comment")
                    msg_text = AI_VA_SEQUENCE["messages"][1]["template"].format(
                        first_name=first_name
                    )
                    self._send_message(chat_id, msg_text)
                    processed[chat_id] = {
                        "trigger": "ai_va_comment",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    count += 1
                    break

        self._save_processed(processed)
        return count

    # ─── Sequence Processing ───────────────────────────────────────────

    def _process_active_sequences(self) -> dict:
        """Process all active message sequences — handle replies and follow-ups."""
        sequences = self._load_sequences()
        replies_processed = 0
        followups_sent = 0

        for chat_id, seq in list(sequences.items()):
            if seq.get("status") == "complete":
                continue

            current_step = seq.get("current_step", 1)
            trigger = seq.get("trigger", "custom_prompt")
            first_name = seq.get("first_name", "there")
            last_message_time = seq.get("last_message_time", "")

            # Get latest messages in this chat
            messages = self._get_chat_messages(chat_id, limit=5)
            if not messages:
                continue

            # Check for new incoming reply
            latest_incoming = None
            for msg in messages:
                if not msg.get("is_sender", 0):
                    latest_incoming = msg
                    break

            if latest_incoming:
                incoming_time = latest_incoming.get("timestamp", "")
                if incoming_time > last_message_time:
                    # New reply detected!
                    reply_text = latest_incoming.get("text", "")

                    if trigger == "custom_prompt" and current_step == 1:
                        # They described their project — generate custom prompt
                        response = self._generate_custom_prompt_response(
                            first_name, reply_text
                        )
                        if response:
                            self._send_message(chat_id, response)
                            seq["current_step"] = 2
                            seq["last_message_time"] = datetime.now(timezone.utc).isoformat()
                            seq["status"] = "awaiting_reply"
                            replies_processed += 1

                    elif trigger == "ai_va_comment" and current_step == 1:
                        # They replied about their pain point — respond personally
                        response = self._generate_ai_va_response(
                            first_name, reply_text
                        )
                        if response:
                            self._send_message(chat_id, response)
                            seq["current_step"] = 2
                            seq["last_message_time"] = datetime.now(timezone.utc).isoformat()
                            seq["status"] = "awaiting_reply"
                            replies_processed += 1

                    elif current_step >= 2:
                        # They replied to a later message — mark as engaged
                        seq["status"] = "engaged"
                        replies_processed += 1

            else:
                # No reply — check if 48hr follow-up is due
                if last_message_time and current_step <= 2:
                    last_time = datetime.fromisoformat(last_message_time.replace("Z", "+00:00"))
                    hours_since = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600

                    if hours_since >= 48 and seq.get("status") != "followup_sent":
                        # Send 48hr follow-up
                        seq_config = CUSTOM_PROMPT_SEQUENCE if trigger == "custom_prompt" else AI_VA_SEQUENCE
                        followup_msg = seq_config["messages"][3]["template"].format(
                            first_name=first_name
                        )
                        self._send_message(chat_id, followup_msg)
                        seq["status"] = "followup_sent"
                        seq["current_step"] = 3
                        seq["last_message_time"] = datetime.now(timezone.utc).isoformat()
                        followups_sent += 1

        self._save_sequences(sequences)
        return {"replies": replies_processed, "followups": followups_sent}

    # ─── AI Response Generation ────────────────────────────────────────

    def _generate_custom_prompt_response(self, first_name: str, project_description: str) -> str:
        """Generate a custom Claude Code prompt based on their project description."""
        prompt = f"""A LinkedIn connection named {first_name} described their project/problem after we offered to give them a custom Claude Code prompt.

THEIR DESCRIPTION:
---
{project_description}
---

Generate TWO things:
1. A detailed Claude Code prompt they can paste directly into Claude Code to build what they described. Be specific — include file structure, tech stack suggestions, step-by-step instructions for the AI agent.
2. A brief, casual message wrapping the prompt.

The message should follow this format:
- Start with "Perfect. Here's the prompt I'd use:"
- Include the full prompt in a clear format
- End with "Drop this into Claude Code and let it run. Don't guide it manually — give it the full instruction up front and let it build. If it asks clarifying questions, answer them and tell it to keep going."
- Add: "If you get stuck or don't know what to do next, just come back and describe exactly where you are and what you're seeing. I'll tell you the next move."

Return JSON with: message (the full message to send), prompt_summary (1-line description of what the prompt does)."""

        result = self.call_json(prompt, temperature=0.7)
        if result and result.get("message"):
            # Quality check
            qr = self.quality_gate.check(result["message"], content_type="message")
            if qr.get("verdict") != "FAIL":
                return qr.get("final_text", result["message"])
        return ""

    def _generate_ai_va_response(self, first_name: str, pain_point: str) -> str:
        """Generate a personalized response about AI VA services based on their pain point."""
        prompt = f"""A LinkedIn connection named {first_name} told us about their biggest time-sink/pain point after we messaged them about AI VAs.

THEIR PAIN POINT:
---
{pain_point}
---

Write a SHORT, CASUAL response (3-5 sentences max) that:
1. Acknowledges their specific pain point
2. Connects it to how an AI-trained VA would handle it
3. Suggests a quick call to map it out
4. NO hard sell, NO pressure — just "here's what I'd do, want to talk through it?"

Tone: like texting a business friend. Use contractions. Be direct.

Return JSON with: message (the full message to send)."""

        result = self.call_json(prompt, temperature=0.7)
        if result and result.get("message"):
            qr = self.quality_gate.check(result["message"], content_type="message")
            if qr.get("verdict") != "FAIL":
                return qr.get("final_text", result["message"])
        return ""

    # ─── Trigger from Comments ─────────────────────────────────────────

    def trigger_ai_va_dm(self, commenter: dict) -> bool:
        """
        Trigger AI VA DM sequence when someone comments "AI VA" on a post.
        Called by the engagement monitor.
        """
        user_id = commenter.get("user_id", "")
        name = commenter.get("name", "")
        first_name = name.split()[0] if name else "there"

        if not user_id:
            return False

        # Start a new chat with this person
        msg_text = AI_VA_SEQUENCE["messages"][1]["template"].format(
            first_name=first_name
        )

        # Create chat and send message
        result = self.unipile.send_message(user_id, msg_text)
        if result:
            chat_id = result.get("id", "") or result.get("chat_id", "")
            if chat_id:
                self._start_sequence(chat_id, user_id, first_name, "ai_va_comment")
                logger.info(f"AI VA DM triggered for {name}")
                return True

        return False

    # ─── Unipile Helpers ───────────────────────────────────────────────

    def _get_recent_chats(self, limit: int = 20) -> list:
        """Get recent LinkedIn chats."""
        account_id = self.unipile.get_account_id()
        resp = self.unipile._get("/chats", params={
            "account_id": account_id,
            "limit": limit,
        })
        return resp.get("items", []) if resp else []

    def _get_chat_messages(self, chat_id: str, limit: int = 10) -> list:
        """Get messages from a chat."""
        resp = self.unipile._get(f"/chats/{chat_id}/messages", params={"limit": limit})
        return resp.get("items", []) if resp else []

    def _send_message(self, chat_id: str, text: str) -> bool:
        """Send a message to a chat."""
        result = self.unipile._post(f"/chats/{chat_id}/messages", {"text": text})
        if result:
            logger.info(f"Message sent to chat {chat_id[:12]}...")
            return True
        return False

    def _extract_first_name(self, chat: dict, messages: list) -> str:
        """Try to extract the person's first name from chat or message data."""
        # Try from chat attendee info
        for msg in messages:
            if not msg.get("is_sender"):
                sender = msg.get("sender_id", "")
                # Try to get profile
                profile = self.unipile.get_profile(sender)
                if profile:
                    name = profile.get("first_name", "") or profile.get("name", "").split()[0]
                    if name:
                        return name
        return "there"

    # ─── Persistence ───────────────────────────────────────────────────

    def _load_sequences(self) -> dict:
        if SEQUENCES_FILE.exists():
            try:
                return json.loads(SEQUENCES_FILE.read_text())
            except Exception:
                return {}
        return {}

    def _save_sequences(self, data: dict):
        SEQUENCES_FILE.write_text(json.dumps(data, indent=2))

    def _start_sequence(self, chat_id: str, attendee_id: str, first_name: str, trigger: str):
        sequences = self._load_sequences()
        sequences[chat_id] = {
            "trigger": trigger,
            "attendee_id": attendee_id,
            "first_name": first_name,
            "current_step": 1,
            "status": "awaiting_reply",
            "started": datetime.now(timezone.utc).isoformat(),
            "last_message_time": datetime.now(timezone.utc).isoformat(),
        }
        self._save_sequences(sequences)

    def _load_processed(self) -> dict:
        if PROCESSED_FILE.exists():
            try:
                return json.loads(PROCESSED_FILE.read_text())
            except Exception:
                return {}
        return {}

    def _save_processed(self, data: dict):
        PROCESSED_FILE.write_text(json.dumps(data, indent=2))


def run_messaging_cycle():
    """Entry point for scheduler."""
    bot = MessagingBot()
    return bot.run_messaging_cycle()
