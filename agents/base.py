"""Base agent class. Every agent inherits from this."""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
CONFIG_DIR = PROJECT_ROOT / "config"


def load_yaml(path: str) -> dict:
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def load_config(name: str) -> dict:
    return load_yaml(str(CONFIG_DIR / name))


class BaseAgent:
    """Wraps a Claude API call with a system prompt and structured I/O."""

    model = "claude-sonnet-4-20250514"
    max_tokens = 4096

    def __init__(self, name: str, prompt_file: str | None = None):
        self.name = name
        self.client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.system_prompt = self._load_prompt(prompt_file or f"{name}.md")
        self.business = load_config("business.yaml")

    def _load_prompt(self, filename: str) -> str:
        path = PROMPTS_DIR / filename
        if path.exists():
            return path.read_text()
        logger.warning(f"Prompt file not found: {path}")
        return ""

    def call(self, user_message: str, temperature: float = 0.7) -> str:
        """Single Claude API call with system prompt."""
        logger.info(f"[{self.name}] calling Claude ({len(user_message)} chars input)")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=temperature,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text
        logger.info(f"[{self.name}] got {len(text)} chars response")
        return text

    def call_json(self, user_message: str, temperature: float = 0.5) -> dict | list:
        """Claude call that expects JSON output. Parses and returns it.

        Handles common issues:
        - Markdown code fences around JSON
        - Extra text before/after JSON
        - Multiple JSON blocks (takes the first valid one)
        """
        raw = self.call(user_message, temperature=temperature)
        cleaned = raw.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]  # Remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # Remove closing fence
            cleaned = "\n".join(lines).strip()

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from the response — find first [ or {
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start_idx = cleaned.find(start_char)
            if start_idx == -1:
                continue
            # Find matching closing bracket by counting nesting
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start_idx, len(cleaned)):
                c = cleaned[i]
                if escape_next:
                    escape_next = False
                    continue
                if c == "\\":
                    escape_next = True
                    continue
                if c == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == start_char:
                    depth += 1
                elif c == end_char:
                    depth -= 1
                    if depth == 0:
                        candidate = cleaned[start_idx : i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break

        # Last resort: try json.JSONDecoder for partial parsing
        decoder = json.JSONDecoder()
        for i, c in enumerate(cleaned):
            if c in "{[":
                try:
                    obj, _ = decoder.raw_decode(cleaned, i)
                    return obj
                except json.JSONDecodeError:
                    continue

        # If nothing works, raise with context
        raise ValueError(
            f"[{self.name}] Could not parse JSON from response. "
            f"First 500 chars: {cleaned[:500]}"
        )

    def save_output(self, data: dict | list | str, subdir: str, filename: str | None = None):
        """Save agent output to data directory."""
        out_dir = DATA_DIR / subdir
        out_dir.mkdir(parents=True, exist_ok=True)
        if filename is None:
            filename = f"{self.name}_{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
        path = out_dir / filename
        if isinstance(data, str):
            path.write_text(data)
        else:
            path.write_text(json.dumps(data, indent=2))
        logger.info(f"[{self.name}] saved output to {path}")
        return path

    def load_latest(self, subdir: str, prefix: str | None = None) -> dict | list | None:
        """Load the most recent JSON file from a data subdirectory."""
        data_path = DATA_DIR / subdir
        if not data_path.exists():
            return None
        files = sorted(data_path.glob("*.json"), reverse=True)
        if prefix:
            files = [f for f in files if f.name.startswith(prefix)]
        if not files:
            return None
        with open(files[0]) as f:
            return json.load(f)

    def today_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def run(self, **kwargs):
        """Override in subclass. This is the main entry point."""
        raise NotImplementedError(f"{self.name}.run() not implemented")
