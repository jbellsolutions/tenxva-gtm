"""Thin wrapper around the Anthropic API. Used by BaseAgent internally."""

import os
from anthropic import Anthropic


def get_client() -> Anthropic:
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
