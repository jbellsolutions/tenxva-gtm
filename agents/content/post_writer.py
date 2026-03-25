"""Post Writer agent — writes LinkedIn posts from briefs.

Updated March 10, 2026: Authority content engine with format rotation,
Todd Brown E5 method, Brian Kurtz overdeliver philosophy, 1st/3rd person variety.
"""

from __future__ import annotations

import json
import logging
import random

from agents.base import BaseAgent
from tools import swipe_reader

logger = logging.getLogger(__name__)

# Must match content types from content_calendar.yaml
POST_TYPES = {"pure_value", "use_case", "trend_commentary", "framework", "engagement"}

# Format rotation — each post gets a different format style
# Inspired by Todd Brown (E5, Unique Mechanism, Big Idea) and Brian Kurtz (Overdeliver, Legend Story, Behind Curtain)
FORMAT_STYLES = [
    "story_driven",       # Mueller/Kurtz: Open with a specific moment, build narrative, extract principle
    "big_idea",           # Todd Brown: Bold contrarian claim → mechanism reasoning → proof
    "framework_system",   # Hormozi/Brown: Named framework, step-by-step logic, save-worthy
    "myth_busting",       # Brown/Kurtz: Challenge popular belief with evidence and nuance
    "behind_the_curtain", # Kurtz: Share actual mechanics, numbers, failures, lessons
    "curated_lesson",     # Kurtz: Something learned from someone else, properly attributed, with own interpretation
    "blog_style",         # Long-form post (400-800 words): deeper exploration, multiple sections
]

# Perspective rotation
PERSPECTIVES = ["first_person", "first_person", "first_person", "third_person_case_study"]
# 75% first person, 25% third person case study


class PostWriter(BaseAgent):
    max_tokens = 8192

    def __init__(self):
        super().__init__("post_writer")
        self._format_index = 0
        self._perspective_index = 0

    def _next_format(self) -> str:
        """Rotate through format styles."""
        style = FORMAT_STYLES[self._format_index % len(FORMAT_STYLES)]
        self._format_index += 1
        return style

    def _next_perspective(self) -> str:
        """Rotate through perspectives."""
        perspective = PERSPECTIVES[self._perspective_index % len(PERSPECTIVES)]
        self._perspective_index += 1
        return perspective

    def _get_swipe_examples(self, brief: dict) -> str:
        """Pull relevant swipe examples for this specific brief."""
        dna_keys = brief.get("copywriter_dna", [])
        sections = []

        for key in dna_keys:
            subjects = swipe_reader.get_subjects_by_sender(key, limit=8)
            if subjects:
                style = swipe_reader.get_style_profile(key)
                name = style["name"] if style else key
                sections.append(
                    f"### {name} Subject Lines for Inspiration\n"
                    + "\n".join(f"- {s}" for s in subjects)
                )

        # Also get body examples if available
        for key in dna_keys[:2]:
            bodies = swipe_reader.get_emails_with_body(key, limit=1)
            for b in bodies:
                sections.append(
                    f"### {b['sender']} Full Email Example\n"
                    f"Subject: {b['subject']}\n\n{b['body'][:800]}"
                )

        return "\n\n".join(sections)

    def run(self, briefs: list[dict]) -> dict:
        """Write all LinkedIn posts for today from briefs."""
        post_briefs = [b for b in briefs if b.get("content_type") in POST_TYPES]
        logger.info(f"[post_writer] writing {len(post_briefs)} posts from {len(briefs)} total briefs")

        # Shuffle format order for daily variety
        random.shuffle(FORMAT_STYLES)

        all_posts = []
        for brief in post_briefs:
            swipe_context = self._get_swipe_examples(brief)
            format_style = self._next_format()
            perspective = self._next_perspective()

            # Determine word count based on format
            if format_style == "blog_style":
                word_range = "400-800"
            elif format_style in ("framework_system", "behind_the_curtain"):
                word_range = "250-400"
            else:
                word_range = "150-300"

            prompt = (
                f"Write a LinkedIn post based on this brief.\n\n"
                f"## Brief\n```json\n{json.dumps(brief, indent=2)}\n```\n\n"
                f"## Format Style: {format_style.upper()}\n"
                f"{self._get_format_instructions(format_style)}\n\n"
                f"## Perspective: {perspective.upper()}\n"
                f"{self._get_perspective_instructions(perspective)}\n\n"
                f"## Swipe File Inspiration\n{swipe_context[:3000]}\n\n"
                f"## Business Context\n"
                f"- Author: Justin Bellware — AI implementation practitioner\n"
                f"- Perspective: Shares insights from building AI teams, testing tools daily, implementing across industries\n"
                f"- Content Philosophy: 85% of posts have ZERO business mention. Authority through value.\n"
                f"- Voice: Knowledgeable peer sharing what he's learning. Not guru. Not salesperson.\n"
                f"- Named mechanisms: The 30-Day AI Bootcamp, The 5-Tool Power Stack, The AI Growth Hacker Certification\n"
                f"- Case studies: Ops manager running 5 AI agent teams, Prototype to alpha in 5 days, Custom CRM in 48 hours\n\n"
                f"## Word Count Target: {word_range} words\n\n"
                f"Write the post now. Return valid JSON with: type, scheduled_time, format_style, perspective, "
                f"headline, body, cta, word_count, content_mix_category, mueller_principle_used, "
                f"specificity_stack, copywriter_dna_applied, save_worthy_element"
            )

            post = self.call_json(prompt)
            post["format_style"] = format_style
            post["perspective"] = perspective
            # Pass through visual metadata from brief for visual generation
            post["visual_type"] = brief.get("visual_type", "none")
            post["key_insight"] = post.get("key_insight") or brief.get("key_insight", "")
            post["save_worthy_element"] = post.get("save_worthy_element") or brief.get("save_worthy_element", "")
            all_posts.append(post)

        result = {"posts": all_posts, "date": self.today_str()}

        self.save_output(
            result,
            f"drafts/{self.today_str()}",
            "posts.json",
        )

        logger.info(f"[post_writer] wrote {len(all_posts)} posts")
        return result

    @staticmethod
    def _get_format_instructions(style: str) -> str:
        """Return format-specific writing instructions."""
        instructions = {
            "story_driven": (
                "STORY-DRIVEN (Mueller/Kurtz): Open with a specific moment — a time, place, "
                "and what happened. Build the narrative. Let the reader live the experience before "
                "you extract the principle. Use 'I was...' or 'Last Tuesday...' openings. "
                "The insight comes AFTER the story, not before. End cleanly."
            ),
            "big_idea": (
                "BIG IDEA (Todd Brown): Lead with one bold, contrarian claim that challenges "
                "conventional wisdom. Support it with mechanism-based reasoning — WHY your claim "
                "is true. Use specific evidence. The reader should feel like they just learned "
                "something nobody else is saying. Short, punchy paragraphs."
            ),
            "framework_system": (
                "FRAMEWORK/SYSTEM (Hormozi/Brown): Present a named framework, decision matrix, "
                "or step-by-step system. Use numbered steps or clear stages. Explain the LOGIC "
                "of each step, not just what to do. This should be 'Screenshot This' worthy — "
                "designed to be bookmarked and referenced."
            ),
            "myth_busting": (
                "MYTH-BUSTING (Brown/Kurtz): Directly challenge a commonly held belief. "
                "'Most people think X. Here's what actually happens...' Structure: popular belief → "
                "why it fails → what the evidence actually shows → nuanced position. Don't be "
                "contrarian for attention — be contrarian because you have data."
            ),
            "behind_the_curtain": (
                "BEHIND THE CURTAIN (Kurtz): Share the actual mechanics of something you built, "
                "tested, or discovered. Include the real numbers, the failures, and what you learned. "
                "This is vulnerability-as-authority. 'Here's what actually happened...' Don't hide "
                "the messy parts — those are what build trust."
            ),
            "curated_lesson": (
                "CURATED LESSON (Kurtz): Share something you learned from someone else — a tool creator, "
                "a colleague, a client, a book. Give full credit. Add YOUR interpretation and how you "
                "applied it. Position yourself as the curator-connector who synthesizes the best thinking."
            ),
            "blog_style": (
                "BLOG-STYLE LONG POST (400-800 words): A deeper exploration with 2-3 clear sections. "
                "Use line breaks between sections. Can combine story + framework + proof. "
                "This is your most authority-building format — it demonstrates depth of thinking. "
                "Include subheadings or section breaks for scannability. Write for the person who "
                "reads every word, not the person scrolling past."
            ),
        }
        return instructions.get(style, instructions["story_driven"])

    @staticmethod
    def _get_perspective_instructions(perspective: str) -> str:
        """Return perspective-specific writing instructions."""
        if perspective == "third_person_case_study":
            return (
                "Write this from a THIRD-PERSON case study perspective. Instead of 'I built...', "
                "use 'The operations manager discovered...' or 'When the startup founder asked...'. "
                "Tell someone ELSE'S story. Justin is the narrator observing and sharing the lesson, "
                "not the hero. Start with 'I' for the frame ('I was working with...' or 'A client called me...'), "
                "transition to 'they/she/he' for the case study details, then return to 'I' for the takeaway."
            )
        return (
            "Write in FIRST-PERSON as Justin Bellware. 'I tested...', 'Last week I discovered...', "
            "'Here's what happened when I tried...'. Share from direct personal experience. "
            "Use parenthetical asides to reveal personality. Be willing to admit mistakes and surprises."
        )
