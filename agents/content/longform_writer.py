"""Long-Form Writer agent — writes newsletters and articles from briefs.

Updated March 10, 2026: Mueller 5-phase narrative, authority-focused context,
Todd Brown unique mechanism, Brian Kurtz overdeliver, format variety.
"""

from __future__ import annotations

import json
import logging
import random

from agents.base import BaseAgent
from tools import swipe_reader

logger = logging.getLogger(__name__)

# Newsletter format rotation — different structural approaches
NEWSLETTER_FORMATS = [
    "mueller_5_phase",     # Scene Entry → Escalation → Pivot → Insight → Clean Close
    "legend_story",        # Kurtz: Story about a specific person/moment + principle extracted
    "deep_dive_mechanism", # Todd Brown: Explain a unique mechanism in depth
    "behind_the_numbers",  # Data-driven + story context around the numbers
    "curated_synthesis",   # Kurtz: 2-3 ideas from different sources, synthesized with original take
]

# Article format rotation
ARTICLE_FORMATS = [
    "seo_mechanism",       # SEO headline → Problem as story → Mechanism reveal → Steps → Proof
    "complete_guide",      # Definitive guide format with comprehensive framework
    "contrarian_analysis", # Challenge a popular narrative with evidence
    "practitioner_playbook", # Step-by-step from real experience, with specific tools and timelines
]


class LongFormWriter(BaseAgent):
    max_tokens = 16384

    def __init__(self):
        super().__init__("longform_writer")

    def _get_deep_swipe_context(self, copywriter_keys: list[str], topic: str) -> str:
        """Pull rich swipe context for long-form content."""
        return swipe_reader.get_swipe_context_for_brief(
            topic=topic,
            copywriter_keys=copywriter_keys,
            max_subjects=15,
            max_body_examples=3,
        )

    def _write_newsletter(self, brief: dict) -> dict:
        """Write a single newsletter from a brief."""
        dna_keys = brief.get("copywriter_dna", ["jay_abraham", "brian_kurtz"])
        topic = brief.get("trend_source", brief.get("angle", "AI implementation"))
        swipe_context = self._get_deep_swipe_context(dna_keys, topic)
        nl_format = random.choice(NEWSLETTER_FORMATS)

        prompt = (
            f"Write a LinkedIn newsletter based on this brief.\n\n"
            f"## Brief\n```json\n{json.dumps(brief, indent=2)}\n```\n\n"
            f"## Newsletter Format: {nl_format.upper()}\n"
            f"{self._get_newsletter_format_instructions(nl_format)}\n\n"
            f"## Swipe File Inspiration\n{swipe_context[:5000]}\n\n"
            f"## Business Context\n"
            f"- Author: Justin Bellware — AI implementation practitioner\n"
            f"- Builds and manages AI-powered teams, tests tools daily\n"
            f"- Content Philosophy: 90% pure value and insight, 10% natural business context\n"
            f"- Voice: Practitioner sharing what works and what doesn't. Not lecturing — sharing.\n"
            f"- Named mechanisms: The 30-Day AI Bootcamp, The 5-Tool Power Stack, The AI Growth Hacker Certification\n"
            f"- Cast of characters: Audrey (ops manager running 5 AI agent teams), startup founders, agency owners\n\n"
            f"## Newsletter Structure (Mueller 5-Phase Narrative)\n"
            f"Scene Entry (specific moment) → Escalation (build tension/curiosity) → "
            f"Pivot (the discovery/realization) → Insight (the lesson, now that reader has lived "
            f"the story) → Clean Close (a thought to sit with, not a pitch).\n"
            f"90% pure value and insight, 10% natural business context.\n"
            f"EVERY newsletter MUST include a saveable framework, checklist, or template.\n"
            f"Target: 800-1200 words.\n\n"
            f"## CRITICAL: Plain Text Output\n"
            f"Write the body in CLEAN PLAIN TEXT. NO markdown — no **bold**, no *italic*, "
            f"no ## headings, no ``` code blocks, no [links](url). LinkedIn doesn't render markdown.\n"
            f"Use ALL CAPS for section titles. Use bullet character • for lists. Use line breaks for structure.\n\n"
            f"Return valid JSON with: type, newsletter_format, headline, subheadline, body, word_count, "
            f"framework_name, key_takeaways, save_worthy_element, mueller_phase_used, "
            f"cta, copywriter_dna_applied, content_mix_category"
        )

        result = self.call_json(prompt)
        result["newsletter_format"] = nl_format
        return result

    def _write_article(self, brief: dict) -> dict:
        """Write a single article from a brief."""
        dna_keys = brief.get("copywriter_dna", ["todd_brown", "alex_hormozi"])
        topic = brief.get("trend_source", brief.get("angle", "AI automation"))
        swipe_context = self._get_deep_swipe_context(dna_keys, topic)
        art_format = random.choice(ARTICLE_FORMATS)

        prompt = (
            f"Write a LinkedIn article based on this brief.\n\n"
            f"## Brief\n```json\n{json.dumps(brief, indent=2)}\n```\n\n"
            f"## Article Format: {art_format.upper()}\n"
            f"{self._get_article_format_instructions(art_format)}\n\n"
            f"## Swipe File Inspiration\n{swipe_context[:5000]}\n\n"
            f"## Business Context\n"
            f"- Author: Justin Bellware — AI implementation practitioner\n"
            f"- Builds and manages AI-powered teams, tests tools daily\n"
            f"- Content Philosophy: Primarily pure value and use case. Business is background, never headline.\n"
            f"- Voice: Practitioner sharing what works and what doesn't. Direct, specific, save-worthy.\n"
            f"- Named mechanisms: The 30-Day AI Bootcamp, The 5-Tool Power Stack, The AI Growth Hacker Certification\n"
            f"- Specificity Stack: Always name the tool, state the timeline, quantify the result\n\n"
            f"## Article Structure\n"
            f"SEO headline → Problem (told as a scene/story) → Mechanism reveal (the insight) → "
            f"Step-by-step framework → Real-world proof → Clean close.\n"
            f"Target: 1000-1500 words.\n\n"
            f"## CRITICAL: Plain Text Output\n"
            f"Write the body in CLEAN PLAIN TEXT. NO markdown — no **bold**, no *italic*, "
            f"no ## headings, no ``` code blocks, no [links](url). LinkedIn doesn't render markdown.\n"
            f"Use ALL CAPS for section titles. Use bullet character • for lists. Use numbered steps (1. 2. 3.).\n"
            f"Use line breaks for structure. The article should read cleanly as plain text.\n\n"
            f"Return valid JSON with: type, article_format, headline, body, word_count, seo_keywords, "
            f"mechanism_name, steps, proof_element, save_worthy_element, "
            f"cta, copywriter_dna_applied, content_mix_category"
        )

        result = self.call_json(prompt)
        result["article_format"] = art_format
        return result

    def run(self, briefs: list[dict]) -> dict:
        """Write all long-form content for today."""
        results = {"newsletters": [], "articles": [], "date": self.today_str()}

        newsletter_briefs = [b for b in briefs if b.get("content_type") == "newsletter"]
        article_briefs = [b for b in briefs if b.get("content_type") == "article"]

        for brief in newsletter_briefs:
            logger.info("[longform_writer] writing newsletter")
            nl = self._write_newsletter(brief)
            results["newsletters"].append(nl)

        for brief in article_briefs:
            logger.info("[longform_writer] writing article")
            article = self._write_article(brief)
            results["articles"].append(article)

        self.save_output(
            results,
            f"drafts/{self.today_str()}",
            "longform.json",
        )

        total = len(results["newsletters"]) + len(results["articles"])
        logger.info(f"[longform_writer] wrote {total} pieces")
        return results

    @staticmethod
    def _get_newsletter_format_instructions(fmt: str) -> str:
        """Return format-specific instructions for newsletter writing."""
        instructions = {
            "mueller_5_phase": (
                "MUELLER 5-PHASE: Follow the full Mueller narrative arc. Open with a specific scene "
                "(time, place, sensory detail). Escalate the tension or curiosity. Hit the pivot moment "
                "(the discovery or realization). Deliver the insight NOW that the reader has lived the story. "
                "Close cleanly with a thought to sit with. The insight lands harder because the reader "
                "experienced the journey."
            ),
            "legend_story": (
                "LEGEND STORY (Brian Kurtz style): Tell a story about a specific person — a client, "
                "a team member, an AI practitioner — and what happened when they encountered a specific "
                "challenge. You are the narrator who was in the room. Include the person's exact words "
                "or reactions. Extract the principle after the story. Build a recurring cast of characters "
                "that readers start to recognize across newsletters."
            ),
            "deep_dive_mechanism": (
                "DEEP DIVE MECHANISM (Todd Brown style): Take one specific mechanism, system, or approach "
                "and explain it in depth. WHY does it work? What makes it different from the obvious approach? "
                "Use a 'Unique Mechanism' structure: name the mechanism, explain the logic, show the proof, "
                "give enough detail that the reader understands the WHY but wants to go deeper on the HOW."
            ),
            "behind_the_numbers": (
                "BEHIND THE NUMBERS: Start with a surprising data point or result. Then tell the STORY "
                "behind those numbers — what actually happened, what decisions were made, what went wrong "
                "and right. The data is the hook, but the story is the content. Include a framework or "
                "checklist that readers can apply to their own situation."
            ),
            "curated_synthesis": (
                "CURATED SYNTHESIS (Brian Kurtz style): Take 2-3 ideas from different sources — tools you tested, "
                "articles you read, conversations you had — and synthesize them into one original insight. "
                "Give proper credit to each source. Your value-add is the CONNECTION between ideas and the "
                "practical application. Position yourself as the curator-connector."
            ),
        }
        return instructions.get(fmt, instructions["mueller_5_phase"])

    @staticmethod
    def _get_article_format_instructions(fmt: str) -> str:
        """Return format-specific instructions for article writing."""
        instructions = {
            "seo_mechanism": (
                "SEO MECHANISM (Todd Brown + SEO): Lead with an SEO-optimized headline that targets "
                "a specific search query. Present the problem as a scene/story. Reveal the mechanism "
                "(the insight that changes the reader's understanding). Walk through the framework "
                "step by step. Prove it with a real-world example. Close with a practical next step."
            ),
            "complete_guide": (
                "COMPLETE GUIDE: The definitive resource on this topic. Structure with clear H2 subheadings. "
                "Cover the topic comprehensively — but through the lens of a practitioner, not a textbook. "
                "Include specific tools, exact steps, real timelines. This should be the article someone "
                "bookmarks and shares with their team."
            ),
            "contrarian_analysis": (
                "CONTRARIAN ANALYSIS: Challenge a popular narrative in the AI/business space. "
                "Start with what 'everyone' is saying. Then present evidence from your direct experience "
                "that tells a different story. Be nuanced — not 'they're wrong' but 'here's what they're missing.' "
                "Include specific examples and data points. End with a more complete picture."
            ),
            "practitioner_playbook": (
                "PRACTITIONER PLAYBOOK: A step-by-step guide from someone who has actually done the thing. "
                "Every step should include: the specific tool used, the exact process, common mistakes to avoid, "
                "and a real example. This is not theory — it's a playbook someone can follow tomorrow. "
                "Include estimated timelines and expected results for each step."
            ),
        }
        return instructions.get(fmt, instructions["seo_mechanism"])
