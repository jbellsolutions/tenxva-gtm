"""Generate branded images for the 4-Day Content Blitz.

Image 7 (Monday): "Manual: 2 Weeks / Claude Code: 30 Mins" — comparison card
Image 3 (Tuesday): "Student Mentality = Exponential Growth" — insight card
Image 1 (Wednesday): "System Over Manual" — comparison card
Image 2 (Thursday): "AI VA: $5/hr Force Multiplier" — stat card

Run: python3 -m tools.generate_blitz_images
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.visual_generator import (
    generate_comparison_card,
    generate_insight_card,
    generate_stat_card,
    generate_quote_card,
    VISUAL_DIR,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BLITZ_DIR = VISUAL_DIR / "blitz"


def generate_all_blitz_images():
    """Generate all 4 content blitz images with fixed filenames."""
    BLITZ_DIR.mkdir(parents=True, exist_ok=True)

    images = {}

    # ─── Image 7 (Monday): Manual 2 Weeks vs Claude Code 30 Mins ─────
    logger.info("Generating Image 7 (Monday): comparison card...")
    path = generate_comparison_card(
        left_title="Manual Dev",
        left_items=[
            "2 weeks of work",
            "$800 spent",
            "Still not finished",
            "Developer quit",
            "Manual coding line by line",
        ],
        right_title="Claude Code",
        right_items=[
            "30 minutes",
            "$0 extra cost",
            "Built, tested, deployed",
            "Admin dashboard included",
            "AI agent runs the build",
        ],
        headline="Manual: 2 Weeks vs Claude Code: 30 Minutes",
        theme="dark_navy",
    )
    # Copy to fixed filename
    dest = BLITZ_DIR / "image_7_monday.png"
    dest.write_bytes(path.read_bytes())
    images["image_7"] = dest
    logger.info(f"  ✓ Image 7 → {dest}")

    # ─── Image 3 (Tuesday): Student Mentality = Exponential Growth ────
    logger.info("Generating Image 3 (Tuesday): insight card...")
    path = generate_insight_card(
        insight_text="The operators who are winning right now aren't the most technically skilled. They're the most curious. Student mentality. Open hands.",
        category="AI Workforce",
        theme="gradient_blue",
    )
    dest = BLITZ_DIR / "image_3_tuesday.png"
    dest.write_bytes(path.read_bytes())
    images["image_3"] = dest
    logger.info(f"  ✓ Image 3 → {dest}")

    # ─── Image 1 (Wednesday): System Over Manual ─────────────────────
    logger.info("Generating Image 1 (Wednesday): comparison card...")
    path = generate_comparison_card(
        left_title="Manual-First",
        left_items=[
            "Hire for skill, hope for output",
            "Output scales with headcount",
            "80-90% manual work",
            "Linear growth curve",
            "Competing on labor cost",
        ],
        right_title="Systems-First",
        right_items=[
            "Recruit for coachability, train for AI",
            "1 VA runs 5 AI-powered systems",
            "30-40% manual and falling",
            "Compounding advantage",
            "Competing on leverage",
        ],
        headline="System Over Manual — The Shift That Changes Everything",
        theme="warm_dark",
    )
    dest = BLITZ_DIR / "image_1_wednesday.png"
    dest.write_bytes(path.read_bytes())
    images["image_1"] = dest
    logger.info(f"  ✓ Image 1 → {dest}")

    # ─── Image 2 (Thursday): AI VA: $5/hr Force Multiplier ───────────
    logger.info("Generating Image 2 (Thursday): stat card...")
    path = generate_stat_card(
        big_number="$5/hr",
        context_text="AI-Trained VA running 5 systems.\nOutreach. Content. Research. Ops. Dev.\n6 hours/day. Full focus. Force multiplier.",
        subtitle="AI VA: The New Category",
        theme="gradient_blue",
    )
    dest = BLITZ_DIR / "image_2_thursday.png"
    dest.write_bytes(path.read_bytes())
    images["image_2"] = dest
    logger.info(f"  ✓ Image 2 → {dest}")

    logger.info(f"\n✓ All 4 blitz images generated in {BLITZ_DIR}/")
    for name, p in images.items():
        logger.info(f"  {name}: {p} ({p.stat().st_size / 1024:.0f} KB)")

    return images


if __name__ == "__main__":
    generate_all_blitz_images()
