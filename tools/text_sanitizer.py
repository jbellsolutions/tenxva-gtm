"""LinkedIn Text Sanitizer — strips markdown artifacts and formatting issues before publishing.

LinkedIn doesn't render markdown. Any **bold**, ##headings, *italics*, or other
markdown syntax will show up as literal characters in the published post.

This module:
1. Strips all markdown formatting artifacts
2. Cleans up whitespace and line spacing for LinkedIn
3. Validates the final text is LinkedIn-ready
4. Optionally humanizes text patterns that flag AI detection
"""

from __future__ import annotations

import re
import logging
import random

logger = logging.getLogger(__name__)


# ── Markdown Stripping ──────────────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    """Remove all markdown formatting artifacts from text.

    Handles: **bold**, *italic*, __bold__, _italic_, ##headings,
    ```code blocks```, `inline code`, [links](url), > blockquotes,
    --- horizontal rules, bullet markers, numbered lists with markdown style.
    """
    if not text:
        return text

    original = text

    # Strip code blocks (```...```) — remove fences, keep content
    text = re.sub(r'```[\w]*\n?', '', text)

    # Strip inline code backticks — keep content inside
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Strip heading markers (## Heading → Heading, ##Heading → Heading)
    # Handle both start-of-line and inline occurrences
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Also strip inline ## markers (e.g., "and ##heading and")
    text = re.sub(r'#{2,6}(\w)', r'\1', text)

    # Strip bold+italic (***text*** or ___text___) → keep text
    text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text)
    text = re.sub(r'_{3}(.+?)_{3}', r'\1', text)

    # Strip bold (**text** or __text__) → keep text
    text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text)
    text = re.sub(r'_{2}(.+?)_{2}', r'\1', text)

    # Strip italic (*text* or _text_) → keep text
    # Be careful not to strip underscores in the middle of words
    text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)

    # Strip markdown links [text](url) → just text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Strip blockquote markers (> text → text)
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)

    # Strip horizontal rules (--- or ***)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Strip strikethrough (~~text~~ → text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)

    # Strip HTML tags that sometimes sneak in
    text = re.sub(r'</?(?:b|i|em|strong|br|p|div|span|a)[^>]*>', '', text)

    # Strip markdown image references
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

    # Strip hashtags (prohibited by content rules)
    text = re.sub(r'#(\w+)', r'\1', text)

    if text != original:
        logger.info("[sanitizer] stripped markdown formatting artifacts")

    return text


# ── LinkedIn Formatting ─────────────────────────────────────────────────────

def format_for_linkedin(text: str) -> str:
    """Optimize text formatting specifically for LinkedIn rendering.

    - Ensures proper line spacing (LinkedIn collapses single newlines)
    - Cleans up excessive blank lines
    - Trims trailing whitespace
    - Removes any remaining markdown bullet markers (- or *)
    """
    if not text:
        return text

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Convert markdown bullet lists to clean text
    # "- Item" or "* Item" at start of line → "Item" (or keep with Unicode bullet)
    text = re.sub(r'^[\-\*]\s+', '\u2022 ', text, flags=re.MULTILINE)

    # Clean up numbered list markers that have dot-space (1. Item → 1. Item — already clean)
    # But strip if it's "1) Item" style → "1. Item"
    text = re.sub(r'^(\d+)\)\s+', r'\1. ', text, flags=re.MULTILINE)

    # Collapse 3+ consecutive newlines to 2 (LinkedIn max useful spacing)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove trailing spaces on each line
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    # Remove leading/trailing whitespace from entire post
    text = text.strip()

    return text


# ── AI Detection Mitigation ─────────────────────────────────────────────────

# Patterns that AI detectors commonly flag
AI_TELLTALE_PATTERNS = [
    # Overused transition phrases
    (r'\bIn today\'s rapidly evolving\b', 'These days'),
    (r'\bIn the ever-evolving landscape\b', 'Right now in'),
    (r'\bIt\'s worth noting that\b', ''),
    (r'\bInterestingly enough\b', ''),
    (r'\bIt goes without saying\b', ''),
    (r'\bNeedless to say\b', ''),
    (r'\bAt the end of the day\b', 'Ultimately'),
    (r'\bMoving forward\b', 'Going ahead'),
    (r'\bLet\'s dive in\b', ''),
    (r'\bLet me break it down\b', ''),
    (r'\bHere\'s the thing\b', ''),
    (r'\bThe reality is\b', ''),
    (r'\bThe truth is\b', ''),
    (r'\bLet\'s be honest\b', ''),

    # Overused AI sentence starters
    (r'^Moreover,\s', 'Plus, ', re.MULTILINE),
    (r'^Furthermore,\s', 'And ', re.MULTILINE),
    (r'^Additionally,\s', 'Also, ', re.MULTILINE),
    (r'^However,\s', 'But ', re.MULTILINE),
    (r'^Nevertheless,\s', 'Still, ', re.MULTILINE),
    (r'^Consequently,\s', 'So ', re.MULTILINE),
    (r'^Subsequently,\s', 'Then ', re.MULTILINE),

    # Overused AI adjective patterns
    (r'\bseamlessly\b', 'smoothly'),
    (r'\bseamless\b', 'smooth'),
    (r'\bleverage\b', 'use'),
    (r'\bsynergy\b', 'combined effort'),
    (r'\bholistic\b', 'full'),
    (r'\bparadigm shift\b', 'big change'),
    (r'\bgame-?changing\b', 'serious'),
    (r'\bgroundbreaking\b', 'new'),
    (r'\bsupercharge\b', 'boost'),

    # Overused AI closing patterns
    (r'\bWhat are your thoughts\?\s*$', ''),
    (r'\bI\'d love to hear your thoughts\.?\s*$', ''),
    (r'\bDrop your thoughts below\.?\s*$', ''),
]

# Varied sentence starters to replace repetitive AI patterns
HUMAN_STARTERS = [
    "Look — ", "So ", "Here's what I mean: ", "Real talk: ",
    "Honestly, ", "The thing is, ", "What happened was ",
    "I'll be straight with you: ", "", "Okay so ",
]


def humanize_text(text: str) -> str:
    """Apply subtle humanization to reduce AI detection signals.

    This is NOT about being deceptive — it's about removing the robotic
    patterns that Claude defaults to, making the writing sound more like
    Justin's actual voice: direct, conversational, slightly informal.
    """
    if not text:
        return text

    changes = 0

    for pattern_entry in AI_TELLTALE_PATTERNS:
        if len(pattern_entry) == 3:
            pattern, replacement, flags = pattern_entry
        else:
            pattern, replacement = pattern_entry
            flags = 0

        new_text = re.sub(pattern, replacement, text, flags=flags)
        if new_text != text:
            changes += 1
            text = new_text

    # Add occasional contractions where they're missing (AI often uses full forms)
    contraction_map = {
        r"\bI am\b": "I'm",
        r"\bI have\b": "I've",
        r"\bI will\b": "I'll",
        r"\bI would\b": "I'd",
        r"\bdo not\b": "don't",
        r"\bdoes not\b": "doesn't",
        r"\bcannot\b": "can't",
        r"\bwill not\b": "won't",
        r"\bshould not\b": "shouldn't",
        r"\bwould not\b": "wouldn't",
        r"\bcould not\b": "couldn't",
        r"\bis not\b": "isn't",
        r"\bare not\b": "aren't",
        r"\bwas not\b": "wasn't",
        r"\bthey are\b": "they're",
        r"\bwe are\b": "we're",
        r"\byou are\b": "you're",
        r"\bit is\b": "it's",
        r"\bthat is\b": "that's",
        r"\bwhat is\b": "what's",
        r"\bthere is\b": "there's",
        r"\blet us\b": "let's",
    }

    for pattern, replacement in contraction_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        # Preserve capitalization for sentence starts
        text = re.sub(
            pattern.replace(r'\b', r'\b').replace(r'\b', ''),
            replacement, text
        )

    # Remove double spaces
    text = re.sub(r'  +', ' ', text)

    # Clean up dangling punctuation from phrase removal (e.g., " — AI" at line start)
    text = re.sub(r'^\s*[—–]\s+', '', text, flags=re.MULTILINE)

    if changes > 0:
        logger.info(f"[sanitizer] humanized {changes} AI-telltale patterns")

    return text


# ── Formatting Validation ────────────────────────────────────────────────────

def check_formatting_issues(text: str, content_type: str = "post") -> list[str]:
    """Check for formatting issues that would look bad on LinkedIn.

    Args:
        text: The content text to check.
        content_type: One of "post", "article", "newsletter". Adjusts length thresholds.

    Returns a list of issue descriptions (empty = clean).
    """
    issues = []

    if not text:
        return ["Empty text"]

    # Check for remaining markdown artifacts
    if re.search(r'\*{2}.+?\*{2}', text):
        issues.append("Contains **bold** markdown (will show as literal asterisks)")
    if re.search(r'(?<!\w)\*(?!\*).+?(?<!\*)\*(?!\w)', text):
        issues.append("Contains *italic* markdown")
    if re.search(r'^#{1,6}\s', text, re.MULTILINE) or re.search(r'^#{2,6}\w', text, re.MULTILINE):
        issues.append("Contains # heading markdown")
    if re.search(r'`[^`]+`', text):
        issues.append("Contains `code` backticks")
    if re.search(r'```', text):
        issues.append("Contains ``` code block markers")
    if re.search(r'\[.+?\]\(.+?\)', text):
        issues.append("Contains [markdown](links)")

    # Check for excessive length — thresholds vary by content type
    word_count = len(text.split())
    if content_type == "post" and word_count > 500:
        issues.append(f"Post is {word_count} words — may be too long for LinkedIn engagement")
    elif content_type == "newsletter" and word_count > 1500:
        issues.append(f"Newsletter is {word_count} words — over the 1200 word target")
    elif content_type == "article" and word_count > 2000:
        issues.append(f"Article is {word_count} words — over the 1500 word target")

    # Check for walls of text (posts only — articles/newsletters have natural sections)
    if content_type == "post":
        paragraphs = text.split('\n\n')
        for p in paragraphs:
            lines = p.strip().split('\n')
            if len(lines) > 5:
                issues.append("Contains a paragraph with 5+ lines — break it up for mobile readability")
                break

    # Check for hashtags (prohibited in our content rules)
    if re.search(r'#\w+', text):
        issues.append("Contains hashtags (prohibited by content rules)")

    return issues


# ── Main Pipeline Function ──────────────────────────────────────────────────

def sanitize_for_linkedin(text: str, humanize: bool = True) -> str:
    """Full sanitization pipeline for LinkedIn publishing.

    1. Strip markdown formatting
    2. Humanize AI patterns (if enabled)
    3. Format for LinkedIn rendering
    4. Log any remaining issues

    Args:
        text: Raw post text (may contain markdown artifacts)
        humanize: Whether to apply AI detection mitigation

    Returns:
        Cleaned text ready for LinkedIn
    """
    if not text:
        return text

    # Step 1: Strip markdown
    text = strip_markdown(text)

    # Step 2: Humanize (reduce AI detection signals)
    if humanize:
        text = humanize_text(text)

    # Step 3: Format for LinkedIn
    text = format_for_linkedin(text)

    # Step 4: Validate
    issues = check_formatting_issues(text)
    if issues:
        logger.warning(f"[sanitizer] remaining issues after sanitization: {issues}")

    return text
