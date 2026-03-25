"""Strategic Influencer Tagger — identifies and adds @mentions to LinkedIn posts.

Rules:
1. Only tag when genuinely relevant (person was mentioned, topic overlaps)
2. Max 2 tags per post — never spam
3. Never tag competitors aggressively
4. Only tag from curated list of known, safe contacts
5. Tag format: "@Name" in the post body (LinkedIn resolves to profile on publish)

Categories:
- MENTIONED: Person or their work is directly referenced in the post
- TOPICAL: Person is a known authority on the specific topic
- ENGAGED: Person has previously engaged with Justin's content

The tagger runs AFTER quality review, BEFORE publishing.
"""

from __future__ import annotations

import re
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
INFLUENCER_FILE = CONFIG_DIR / "influencers.json"


# ── Influencer Registry ─────────────────────────────────────────────────────

# Default curated list — loaded from config/influencers.json if it exists
DEFAULT_INFLUENCERS = [
    {
        "name": "Alex Hormozi",
        "linkedin_name": "Alex Hormozi",
        "topics": ["business", "scaling", "offers", "marketing", "frameworks"],
        "relationship": "inspiration",
        "safe_to_tag": True,
        "notes": "Major influencer. Only tag when directly referencing his frameworks.",
    },
    {
        "name": "Liam Ottley",
        "linkedin_name": "Liam Ottley",
        "topics": ["ai_agents", "automation", "ai_agency", "saas"],
        "relationship": "industry_peer",
        "safe_to_tag": True,
        "notes": "AI agency space leader. Tag when discussing AI agent businesses.",
    },
    {
        "name": "Tom Bilyeu",
        "linkedin_name": "Tom Bilyeu",
        "topics": ["mindset", "entrepreneurship", "personal_development"],
        "relationship": "inspiration",
        "safe_to_tag": False,
        "notes": "Very large audience. Don't tag directly — mention instead.",
    },
    {
        "name": "Sam Altman",
        "linkedin_name": "Sam Altman",
        "topics": ["openai", "ai_models", "gpt", "ai_future"],
        "relationship": "industry_figure",
        "safe_to_tag": False,
        "notes": "Too big to tag. Reference by name only.",
    },
    {
        "name": "Dario Amodei",
        "linkedin_name": "Dario Amodei",
        "topics": ["anthropic", "claude", "ai_safety", "ai_models"],
        "relationship": "industry_figure",
        "safe_to_tag": False,
        "notes": "Reference by name. Tag only if directly quoting.",
    },
]


def _load_influencers() -> list[dict]:
    """Load influencer registry from config file, falling back to defaults."""
    if INFLUENCER_FILE.exists():
        try:
            with open(INFLUENCER_FILE) as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[tagger] failed to load influencers.json: {e}")
    return DEFAULT_INFLUENCERS


def save_influencers(influencers: list[dict]):
    """Save influencer registry to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(INFLUENCER_FILE, "w") as f:
        json.dump(influencers, f, indent=2)
    logger.info(f"[tagger] saved {len(influencers)} influencers to {INFLUENCER_FILE}")


def add_influencer(
    name: str,
    linkedin_name: str,
    topics: list[str],
    relationship: str = "industry_peer",
    safe_to_tag: bool = True,
    notes: str = "",
):
    """Add a new influencer to the registry."""
    influencers = _load_influencers()

    # Check for duplicate
    for inf in influencers:
        if inf["name"].lower() == name.lower():
            logger.info(f"[tagger] influencer {name} already exists, updating")
            inf.update({
                "linkedin_name": linkedin_name,
                "topics": topics,
                "relationship": relationship,
                "safe_to_tag": safe_to_tag,
                "notes": notes,
            })
            save_influencers(influencers)
            return

    influencers.append({
        "name": name,
        "linkedin_name": linkedin_name,
        "topics": topics,
        "relationship": relationship,
        "safe_to_tag": safe_to_tag,
        "notes": notes,
    })
    save_influencers(influencers)
    logger.info(f"[tagger] added influencer: {name}")


# ── Tag Detection ────────────────────────────────────────────────────────────

def _extract_mentioned_names(text: str) -> list[str]:
    """Extract names that appear to be mentioned in the post text."""
    influencers = _load_influencers()
    mentioned = []

    text_lower = text.lower()
    for inf in influencers:
        name = inf["name"]
        # Check if the person's name appears in the text
        if name.lower() in text_lower:
            mentioned.append(name)
        # Also check linkedin_name if different
        elif inf.get("linkedin_name", "").lower() in text_lower:
            mentioned.append(name)

    return mentioned


def _match_topics(text: str, topics: list[str]) -> int:
    """Score how well a post's text matches an influencer's topics."""
    text_lower = text.lower()
    matches = 0
    for topic in topics:
        # Convert topic_slug to searchable terms
        search_terms = topic.replace("_", " ").split()
        for term in search_terms:
            if term.lower() in text_lower:
                matches += 1
    return matches


def find_tag_opportunities(text: str, max_tags: int = 2) -> list[dict]:
    """Find strategic tagging opportunities for a post.

    Returns a list of tag suggestions, ranked by relevance.
    Each suggestion includes the influencer info and the reason for tagging.

    Rules:
    - Only influencers with safe_to_tag=True can be @mentioned
    - Max 2 tags per post
    - Must have a legitimate reason (mentioned or strong topic match)
    - Never force a tag — if nothing fits, return empty list
    """
    influencers = _load_influencers()
    opportunities = []

    mentioned_names = _extract_mentioned_names(text)

    for inf in influencers:
        if not inf.get("safe_to_tag", False):
            continue

        name = inf["name"]
        score = 0
        reason = ""

        # Highest priority: directly mentioned
        if name in mentioned_names:
            score = 10
            reason = f"MENTIONED: {name} is directly referenced in the post"

        # Second priority: strong topic match (3+ topic keywords match)
        else:
            topic_score = _match_topics(text, inf.get("topics", []))
            if topic_score >= 3:
                score = topic_score
                reason = f"TOPICAL: Post aligns with {name}'s expertise ({topic_score} topic matches)"
            elif topic_score >= 2:
                score = topic_score
                reason = f"TOPICAL: Moderate topic overlap with {name} ({topic_score} matches)"

        if score > 0:
            opportunities.append({
                "name": name,
                "linkedin_name": inf.get("linkedin_name", name),
                "score": score,
                "reason": reason,
                "relationship": inf.get("relationship", "unknown"),
            })

    # Sort by score descending, take top max_tags
    opportunities.sort(key=lambda x: x["score"], reverse=True)
    return opportunities[:max_tags]


# ── Tag Insertion ────────────────────────────────────────────────────────────

def insert_tags(text: str, tags: list[dict]) -> str:
    """Insert @mentions into post text strategically.

    Rules:
    - If person is MENTIONED by name, replace first occurrence with @Name
    - If person is TOPICAL only, add a brief mention at end (before any CTA)
    - Never add more than 2 tags
    - Never make the tag feel forced

    LinkedIn note: @Name won't auto-link in the CSV/API — PhantomBuster
    may or may not resolve it. The text will still reference the person
    by name which is the primary goal for visibility.
    """
    if not tags:
        return text

    tagged_text = text
    tags_inserted = 0

    for tag in tags:
        if tags_inserted >= 2:
            break

        name = tag["name"]
        linkedin_name = tag.get("linkedin_name", name)

        # If the person is mentioned by name, no need to add — just ensure visible
        if name.lower() in tagged_text.lower():
            tags_inserted += 1
            logger.info(f"[tagger] {name} already mentioned in post (no insertion needed)")
            continue

        # For topical matches — don't force a tag into the post
        # Only add if the topic match is very strong (score >= 4)
        if tag.get("score", 0) >= 4:
            # Add a subtle reference at the very end
            # Find the last paragraph
            paragraphs = tagged_text.rsplit("\n\n", 1)
            if len(paragraphs) > 1:
                # Check if the last paragraph looks like a CTA or closing
                last = paragraphs[-1].strip()
                # Insert before closing paragraph
                tagged_text = (
                    paragraphs[0]
                    + f"\n\n(h/t {linkedin_name} for pioneering work in this space)"
                    + "\n\n"
                    + last
                )
            else:
                tagged_text += f"\n\n(h/t {linkedin_name})"

            tags_inserted += 1
            logger.info(f"[tagger] added h/t mention of {linkedin_name}")

    return tagged_text


# ── Pipeline Integration ─────────────────────────────────────────────────────

def apply_strategic_tags(reviews: dict) -> int:
    """Apply strategic tagging to all approved posts.

    Modifies reviews in place — adds tag info and updates final_text.

    Returns:
        Number of posts that received tags.
    """
    tagged_count = 0

    for category in ["posts", "newsletters", "articles"]:
        for review in reviews.get(category, []):
            if review.get("verdict") != "APPROVED":
                continue

            final_text = review.get("final_text", "")
            if not final_text:
                continue

            # Find tag opportunities
            opportunities = find_tag_opportunities(final_text)

            if opportunities:
                # Insert tags
                tagged_text = insert_tags(final_text, opportunities)
                if tagged_text != final_text:
                    review["final_text"] = tagged_text
                    tagged_count += 1

                # Store tag metadata
                review["tags_applied"] = [
                    {"name": t["name"], "reason": t["reason"]}
                    for t in opportunities
                ]
                logger.info(
                    f"[tagger] tagged post with: "
                    + ", ".join(t["name"] for t in opportunities)
                )

    return tagged_count
