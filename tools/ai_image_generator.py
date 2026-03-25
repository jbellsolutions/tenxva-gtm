"""AI Image Generator — creates intense, scroll-stopping images for LinkedIn posts.

Backends (in priority order):
1. OpenAI DALL-E 3 — high quality, $0.04-0.08/image
2. Replicate Flux — photorealistic, artistic, $0.003-0.05/image
3. Pillow Fallback — branded cards (existing visual_generator.py)

Image Philosophy:
- INTENSE. Dramatic. Stops the scroll.
- Cinematic lighting, bold contrast, emotional weight.
- Think movie poster thumbnails, not corporate graphics.
- Every image should make someone pause mid-scroll.

Visual Rotation System:
- AI-generated images (DALL-E/Flux) for story-driven posts
- Branded Pillow cards (stat, comparison, insight) for framework/data posts
- Carousel PDFs for step-by-step, tip list, and save-worthy content

LinkedIn 2026 Specs:
- Portrait 4:5 (1080x1350) for max mobile feed real estate
- Carousels: PDF upload, 8-10 slides, 1080x1350 per slide
- Saves > Shares > Comments > Likes (algorithm priority)

Usage:
    from tools.ai_image_generator import generate_post_image, generate_smart_visual
    path = generate_post_image(post_text, post_theme, style="cinematic")
    path = generate_smart_visual(post_data)  # auto-picks best format
"""

from __future__ import annotations

import os
import json
import logging
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
AI_VISUALS_DIR = DATA_DIR / "visuals" / "ai-generated"

# ── Image Style Presets ──────────────────────────────────────────────────

STYLE_PRESETS = {
    "cinematic": {
        "suffix": "cinematic lighting, dramatic shadows, high contrast, moody atmosphere, "
                  "film grain, anamorphic lens flare, 8k ultra detailed, dark tones with "
                  "accent lighting, professional color grading",
        "negative": "text, words, letters, watermark, logo, cartoon, anime, low quality, blurry",
    },
    "intense_tech": {
        "suffix": "cyberpunk aesthetic, neon glow against dark background, futuristic, "
                  "dramatic lighting, high contrast, volumetric fog, ray tracing, "
                  "tech noir atmosphere, circuit board patterns in shadows, 8k",
        "negative": "text, words, letters, watermark, cartoon, bright cheerful colors, clipart",
    },
    "dark_editorial": {
        "suffix": "editorial photography style, dark moody studio lighting, "
                  "dramatic chiaroscuro, shallow depth of field, professional portrait lighting, "
                  "high-end magazine aesthetic, desaturated with one accent color, 8k",
        "negative": "text, words, letters, watermark, cartoon, oversaturated, amateur",
    },
    "war_room": {
        "suffix": "war room atmosphere, multiple screens glowing in dark room, "
                  "dramatic overhead lighting, tension and urgency, command center aesthetic, "
                  "blue and orange color palette, cinematic composition, 8k ultra detailed",
        "negative": "text, words, letters, watermark, cartoon, bright, cheerful",
    },
    "collision": {
        "suffix": "two forces colliding, dramatic impact, particle explosion, "
                  "dark background with intense light burst at point of collision, "
                  "shockwave ripples, cinematic slow motion freeze frame, 8k ultra detailed",
        "negative": "text, words, letters, watermark, cartoon, peaceful, calm",
    },
    "before_after": {
        "suffix": "split composition, left side dark chaotic and manual, right side "
                  "clean futuristic and automated, dramatic contrast between old and new, "
                  "cinematic lighting on both halves, dark tones, 8k",
        "negative": "text, words, letters, watermark, cartoon, same on both sides",
    },
    "lone_operator": {
        "suffix": "single person silhouette against massive wall of glowing screens and data, "
                  "dramatic scale contrast, cyberpunk atmosphere, volumetric light rays, "
                  "the feeling of one person controlling immense power, 8k ultra detailed",
        "negative": "text, words, letters, watermark, cartoon, crowd, multiple people",
    },
}

# ── Theme-to-Style Mapping ───────────────────────────────────────────────

THEME_STYLE_MAP = {
    "implementing_ai": "intense_tech",
    "hiring_ai": "war_room",
    "working_with_developers": "collision",
    "lessons_learned": "dark_editorial",
    "structural_shift": "before_after",
    "systems_first": "lone_operator",
    "coachability": "dark_editorial",
    "student_mentality": "cinematic",
    "developer_quit": "collision",
    "ai_va": "lone_operator",
    "default": "cinematic",
}


# ── Prompt Engineering ───────────────────────────────────────────────────

def craft_image_prompt(
    post_text: str,
    post_theme: str = "",
    style: str = "cinematic",
    custom_scene: str = "",
) -> dict:
    """Craft an intense image prompt from post content.

    Args:
        post_text: The LinkedIn post text
        post_theme: Theme category (implementing_ai, hiring_ai, etc.)
        style: Style preset name
        custom_scene: Optional custom scene description override

    Returns:
        Dict with 'prompt', 'negative_prompt', 'style' keys
    """
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["cinematic"])

    if custom_scene:
        scene = custom_scene
    else:
        scene = _extract_scene_from_post(post_text, post_theme)

    full_prompt = f"{scene}, {preset['suffix']}"

    return {
        "prompt": full_prompt,
        "negative_prompt": preset["negative"],
        "style": style,
        "scene": scene,
    }


def _extract_scene_from_post(post_text: str, theme: str = "") -> str:
    """Extract a visual scene description from post content.

    Uses keyword analysis to pick the most dramatic visual.
    """
    text_lower = post_text.lower()

    # Check for specific story patterns and return dramatic scenes
    if "developer" in text_lower and ("quit" in text_lower or "left" in text_lower):
        return ("Empty office chair in front of glowing computer monitors in a dark room, "
                "one monitor showing code being written by itself, chair pushed back like "
                "someone just stood up and walked away, dramatic blue light from screens")

    if "30 minutes" in text_lower and ("built" in text_lower or "deployed" in text_lower):
        return ("Hourglass with glowing sand running out, reflected in a laptop screen "
                "showing a deployed application dashboard, time distortion effect, "
                "dramatic contrast between speed and complexity")

    if "claude code" in text_lower or "ai agent" in text_lower:
        return ("Massive holographic AI interface floating above a minimalist desk in a dark room, "
                "streams of code and data flowing like rivers of light, single person's hands "
                "on keyboard directing the flow, feeling of immense power being channeled")

    if "coachable" in text_lower or "student mentality" in text_lower:
        return ("Two paths diverging in a dark landscape, one path lit by warm golden light "
                "leading upward, the other fading into shadow and obsolescence, "
                "dramatic atmospheric perspective, crossroads moment")

    if "hire" in text_lower and ("va" in text_lower or "virtual" in text_lower):
        return ("Command center with one operator managing multiple glowing screens, "
                "each screen showing a different automated workflow running simultaneously, "
                "dramatic overhead lighting, feeling of force multiplication")

    if "system" in text_lower and ("manual" in text_lower or "structural" in text_lower):
        return ("Split scene: left half shows a person drowning in paper and manual tasks "
                "under harsh fluorescent light, right half shows the same desk transformed "
                "into a sleek command center with AI agents running on screens, dramatic contrast")

    if "fail" in text_lower or "broke" in text_lower or "wrong" in text_lower:
        return ("Shattered glass floating in mid-air in a dark room, each shard reflecting "
                "a different screen or dashboard, dramatic backlighting creating a "
                "beautiful destruction moment, lessons learned aesthetic")

    if "5 days" in text_lower or "48 hours" in text_lower or "prototype" in text_lower:
        return ("Time-lapse composition showing construction of a digital building in fast motion, "
                "wireframes becoming solid interfaces, dramatic speed lines and motion blur, "
                "dark background with neon construction light")

    # Theme-based fallbacks
    theme_scenes = {
        "implementing_ai": "Person standing before a massive wall of interconnected AI systems "
                          "in a dark operations center, nodes and connections pulsing with light",
        "hiring_ai": "Interview table in a dark dramatic room, one seat empty with holographic "
                    "AI assistant floating above it, tension and possibility",
        "working_with_developers": "Two monitors side by side in a dark room — one showing "
                                  "manual line-by-line code, the other showing AI building entire "
                                  "systems autonomously, dramatic contrast in productivity",
        "lessons_learned": "Person standing at the edge of a cliff overlooking a vast digital "
                          "landscape of interconnected systems below, dramatic sunset backlighting",
    }

    if theme in theme_scenes:
        return theme_scenes[theme]

    # Default dramatic scene
    return ("Solitary figure in a dark room illuminated by the glow of multiple screens "
            "running AI systems, dramatic volumetric light rays cutting through the darkness, "
            "feeling of quiet power and control over complex systems")


# ── Backend: OpenAI DALL-E 3 ─────────────────────────────────────────────

def _generate_dalle(prompt: str, size: str = "1024x1792") -> Path | None:
    """Generate image using OpenAI DALL-E 3.

    Args:
        prompt: Full image prompt
        size: Image dimensions (1024x1024, 1792x1024, 1024x1792)
              Default: 1024x1792 (portrait) for max LinkedIn mobile feed real estate

    Returns:
        Path to saved image or None
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("[ai_image] OPENAI_API_KEY not set")
        return None

    try:
        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": "hd",
                "style": "vivid",
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        image_url = data["data"][0]["url"]
        revised_prompt = data["data"][0].get("revised_prompt", "")

        # Download the image
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()

        AI_VISUALS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dalle_{timestamp}.png"
        path = AI_VISUALS_DIR / filename
        path.write_bytes(img_resp.content)

        logger.info(f"[ai_image] DALL-E 3 generated: {path} ({len(img_resp.content) / 1024:.0f} KB)")
        if revised_prompt:
            logger.info(f"[ai_image] revised prompt: {revised_prompt[:200]}")

        return path

    except requests.exceptions.HTTPError as e:
        logger.error(f"[ai_image] DALL-E error: {e} — {resp.text[:300]}")
        return None
    except Exception as e:
        logger.error(f"[ai_image] DALL-E error: {e}")
        return None


# ── Backend: Replicate (Flux) ────────────────────────────────────────────

def _generate_flux(
    prompt: str,
    negative_prompt: str = "",
    model: str = "black-forest-labs/flux-1.1-pro",
    aspect_ratio: str = "9:16",
) -> Path | None:
    """Generate image using Replicate's Flux models.

    Args:
        prompt: Full image prompt
        negative_prompt: Things to avoid
        model: Replicate model identifier
        aspect_ratio: Image aspect ratio (default 9:16 for LinkedIn portrait,
                       Flux supports: 1:1, 16:9, 9:16, 3:2, 2:3, 4:3, 3:4, etc.)

    Returns:
        Path to saved image or None
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN", "")
    if not api_token:
        logger.warning("[ai_image] REPLICATE_API_TOKEN not set")
        return None

    try:
        # Use the models endpoint (not predictions with version)
        # Format: POST /v1/models/{owner}/{name}/predictions
        model_owner, model_name = model.split("/", 1)
        resp = requests.post(
            f"https://api.replicate.com/v1/models/{model_owner}/{model_name}/predictions",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Prefer": "wait",  # Wait for completion (up to 60s)
            },
            json={
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "png",
                    "output_quality": 95,
                    "safety_tolerance": 5,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        prediction = resp.json()

        # Poll for completion
        import time
        poll_url = prediction.get("urls", {}).get("get", "")
        if not poll_url:
            poll_url = f"https://api.replicate.com/v1/predictions/{prediction['id']}"

        for _ in range(60):  # Max 60 seconds
            time.sleep(2)
            poll_resp = requests.get(
                poll_url,
                headers={"Authorization": f"Bearer {api_token}"},
                timeout=10,
            )
            poll_data = poll_resp.json()
            status = poll_data.get("status", "")

            if status == "succeeded":
                output = poll_data.get("output")
                if isinstance(output, list):
                    image_url = output[0]
                elif isinstance(output, str):
                    image_url = output
                else:
                    logger.error(f"[ai_image] Flux unexpected output format: {type(output)}")
                    return None

                # Download
                img_resp = requests.get(image_url, timeout=60)
                img_resp.raise_for_status()

                AI_VISUALS_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"flux_{timestamp}.png"
                path = AI_VISUALS_DIR / filename
                path.write_bytes(img_resp.content)

                logger.info(f"[ai_image] Flux generated: {path} ({len(img_resp.content) / 1024:.0f} KB)")
                return path

            elif status == "failed":
                error = poll_data.get("error", "unknown")
                logger.error(f"[ai_image] Flux failed: {error}")
                return None

        logger.error("[ai_image] Flux generation timed out")
        return None

    except Exception as e:
        logger.error(f"[ai_image] Flux error: {e}")
        return None


# ── Backend: Enhanced Pillow (Upgraded) ──────────────────────────────────

def _generate_intense_pillow(
    scene_text: str,
    headline: str = "",
    style: str = "cinematic",
) -> Path | None:
    """Generate an intense branded image using Pillow with upgraded effects.

    This is the fallback when no AI image API is available.
    Uses dramatic gradients, glow effects, and bold typography.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
    except ImportError:
        logger.error("[ai_image] Pillow not available")
        return None

    width, height = 1080, 1350  # LinkedIn optimal 4:5 portrait (max mobile feed space)

    # Color palettes by style
    palettes = {
        "cinematic": {"bg1": (10, 10, 30), "bg2": (30, 15, 50), "accent": (0, 150, 255), "glow": (0, 100, 200)},
        "intense_tech": {"bg1": (5, 5, 20), "bg2": (10, 25, 40), "accent": (0, 255, 200), "glow": (0, 200, 150)},
        "dark_editorial": {"bg1": (15, 12, 10), "bg2": (35, 25, 20), "accent": (233, 69, 96), "glow": (180, 50, 70)},
        "war_room": {"bg1": (8, 12, 25), "bg2": (15, 25, 45), "accent": (255, 150, 0), "glow": (200, 100, 0)},
        "collision": {"bg1": (15, 5, 5), "bg2": (40, 10, 20), "accent": (255, 80, 50), "glow": (200, 60, 30)},
        "before_after": {"bg1": (10, 10, 10), "bg2": (20, 30, 50), "accent": (0, 150, 255), "glow": (0, 100, 200)},
        "lone_operator": {"bg1": (5, 8, 20), "bg2": (10, 20, 45), "accent": (100, 180, 255), "glow": (60, 120, 200)},
    }
    pal = palettes.get(style, palettes["cinematic"])

    # Create base with gradient
    img = Image.new("RGB", (width, height), pal["bg1"])
    draw = ImageDraw.Draw(img)

    # Dramatic diagonal gradient
    for y in range(height):
        for x in range(width):
            # Diagonal blend factor
            factor = (x / width * 0.6 + y / height * 0.4)
            r = int(pal["bg1"][0] * (1 - factor) + pal["bg2"][0] * factor)
            g = int(pal["bg1"][1] * (1 - factor) + pal["bg2"][1] * factor)
            b = int(pal["bg1"][2] * (1 - factor) + pal["bg2"][2] * factor)
            img.putpixel((x, y), (r, g, b))

    draw = ImageDraw.Draw(img)

    # Dramatic light burst from center-right
    glow_layer = Image.new("RGB", (width, height), (0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    cx, cy = int(width * 0.7), int(height * 0.4)
    for radius in range(400, 0, -2):
        alpha = max(0, min(255, int(30 * (1 - radius / 400))))
        r = min(255, pal["glow"][0] + alpha)
        g = min(255, pal["glow"][1] + alpha)
        b = min(255, pal["glow"][2] + alpha)
        glow_draw.ellipse(
            [(cx - radius, cy - radius), (cx + radius, cy + radius)],
            fill=(r, g, b),
        )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=40))

    # Blend glow onto main image
    from PIL import ImageChops
    img = ImageChops.add(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # Accent line at top (intense)
    for i in range(6):
        intensity = 1.0 - (i / 6.0)
        r = int(pal["accent"][0] * intensity)
        g = int(pal["accent"][1] * intensity)
        b = int(pal["accent"][2] * intensity)
        draw.rectangle([(0, i), (width, i + 1)], fill=(r, g, b))

    # Accent line at bottom
    for i in range(4):
        intensity = 1.0 - (i / 4.0)
        r = int(pal["accent"][0] * intensity * 0.5)
        g = int(pal["accent"][1] * intensity * 0.5)
        b = int(pal["accent"][2] * intensity * 0.5)
        draw.rectangle([(0, height - 4 + i), (width, height - 3 + i)], fill=(r, g, b))

    # Get fonts
    import textwrap

    def get_font(size, bold=False):
        names = [
            "Inter-Bold.ttf" if bold else "Inter-Regular.ttf",
            "Arial Bold.ttf" if bold else "Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        from PIL import ImageFont
        for name in names:
            try:
                return ImageFont.truetype(name, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    # Headline text (big, bold, dramatic)
    if headline:
        display_text = headline.upper()
    else:
        # Extract first impactful line from scene_text
        display_text = scene_text.split(".")[0].strip().upper()
        if len(display_text) > 60:
            display_text = display_text[:57] + "..."

    # Size text dynamically
    font_size = 52 if len(display_text) < 40 else 44 if len(display_text) < 60 else 36
    font = get_font(font_size, bold=True)

    # Wrap text
    max_chars = 24 if font_size >= 52 else 30 if font_size >= 44 else 36
    wrapped = textwrap.fill(display_text, width=max_chars)
    lines = wrapped.split("\n")

    # Position text (left-aligned, vertically centered)
    line_height = int(font_size * 1.4)
    text_block_height = len(lines) * line_height
    y_start = (height - text_block_height) // 2 - 20
    x_margin = 80

    # Draw text with glow effect
    for i, line in enumerate(lines):
        y = y_start + (i * line_height)
        # Glow behind text
        for offset in range(3, 0, -1):
            glow_color = (
                min(255, pal["accent"][0] // (offset * 2)),
                min(255, pal["accent"][1] // (offset * 2)),
                min(255, pal["accent"][2] // (offset * 2)),
            )
            draw.text((x_margin - offset, y - offset), line, fill=glow_color, font=font)
            draw.text((x_margin + offset, y + offset), line, fill=glow_color, font=font)
        # Main text
        draw.text((x_margin, y), line, fill=(255, 255, 255), font=font)

    # Author bar at bottom
    author_font = get_font(18, bold=True)
    brand_font = get_font(15, bold=False)
    draw.text((x_margin, height - 65), "JUSTIN BELLWARE", fill=(200, 200, 200), font=author_font)
    draw.text((x_margin, height - 42), "Using AI to Scale", fill=(120, 120, 120), font=brand_font)

    # Save
    AI_VISUALS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = AI_VISUALS_DIR / f"intense_{style}_{timestamp}.png"
    img.save(str(path), "PNG", quality=95)

    logger.info(f"[ai_image] Pillow intense generated: {path} ({path.stat().st_size / 1024:.0f} KB)")
    return path


# ── Main Generation Function ─────────────────────────────────────────────

def generate_post_image(
    post_text: str,
    post_theme: str = "",
    style: str = "",
    custom_scene: str = "",
    headline: str = "",
    backend: str = "auto",
) -> Path | None:
    """Generate an intense, scroll-stopping image for a LinkedIn post.

    Args:
        post_text: The full post text
        post_theme: Theme category for style selection
        style: Style preset override (cinematic, intense_tech, etc.)
        custom_scene: Custom scene description override
        headline: Headline text for Pillow fallback
        backend: Force specific backend (auto, dalle, flux, pillow)

    Returns:
        Path to generated image, or None if all backends fail
    """
    # Auto-select style from theme if not specified
    if not style:
        style = THEME_STYLE_MAP.get(post_theme, THEME_STYLE_MAP["default"])

    # Craft the prompt
    prompt_data = craft_image_prompt(post_text, post_theme, style, custom_scene)
    logger.info(f"[ai_image] generating {style} image, backend={backend}")
    logger.info(f"[ai_image] scene: {prompt_data['scene'][:150]}...")

    # Try backends in order
    if backend == "auto":
        backends = ["dalle", "flux", "pillow"]
    else:
        backends = [backend]

    for be in backends:
        try:
            if be == "dalle":
                path = _generate_dalle(prompt_data["prompt"], size="1024x1792")
                if path:
                    return path

            elif be == "flux":
                path = _generate_flux(
                    prompt_data["prompt"],
                    negative_prompt=prompt_data["negative_prompt"],
                    aspect_ratio="9:16",
                )
                if path:
                    return path

            elif be == "pillow":
                path = _generate_intense_pillow(
                    prompt_data["scene"],
                    headline=headline,
                    style=style,
                )
                if path:
                    return path

        except Exception as e:
            logger.warning(f"[ai_image] {be} backend failed: {e}")
            continue

    logger.error("[ai_image] all backends failed")
    return None


def generate_batch_for_week(posts: list[dict]) -> dict:
    """Generate images for a batch of posts (e.g., weekly content).

    Args:
        posts: List of dicts with 'text', 'theme', 'headline' keys

    Returns:
        Dict mapping post index to image path
    """
    results = {}
    for i, post in enumerate(posts):
        logger.info(f"[ai_image] generating image {i + 1}/{len(posts)}")
        path = generate_post_image(
            post_text=post.get("text", ""),
            post_theme=post.get("theme", ""),
            headline=post.get("headline", ""),
        )
        if path:
            results[i] = str(path)
        else:
            results[i] = None
    return results


# ── Smart Visual Rotation ─────────────────────────────────────────────

# Visual format selection based on content type and style
VISUAL_FORMAT_MAP = {
    # format_style → preferred visual format
    "story_driven": "ai_image",
    "big_idea": "ai_image",
    "behind_the_curtain": "ai_image",
    "framework_system": "carousel",
    "blog_style": "ai_image",
    "myth_busting": "branded_card",  # comparison card
    "curated_lesson": "branded_card",  # insight card
    # article formats
    "seo_mechanism": "ai_image",
    "complete_guide": "carousel",
    "contrarian_analysis": "ai_image",
    "practitioner_playbook": "carousel",
    # newsletter formats
    "mueller_5_phase": "ai_image",
    "legend_story": "ai_image",
    "deep_dive_mechanism": "carousel",
    "behind_the_numbers": "branded_card",  # stat card
    "curated_synthesis": "branded_card",  # insight card
}


def _detect_visual_format(post_data: dict) -> str:
    """Detect the best visual format based on post content and metadata.

    Returns: "ai_image", "carousel", or "branded_card"
    """
    import re

    format_style = post_data.get("format_style", "")
    body = post_data.get("body", post_data.get("final_text", ""))
    content_type = post_data.get("content_type", "post")

    # Check explicit format mapping first
    if format_style in VISUAL_FORMAT_MAP:
        return VISUAL_FORMAT_MAP[format_style]

    # Content analysis heuristics
    has_numbered_list = bool(re.findall(r'(?:^|\n)\s*\d+[\.\)]\s+', body))
    has_steps = "step" in body.lower() or "framework" in body.lower()
    has_big_numbers = bool(re.findall(r'\b\d{2,}[xX%]|\$[\d,]+', body))
    has_comparison = any(w in body.lower() for w in ["before", "vs", "versus", "instead of"])

    # Carousel for listy/framework content
    if has_numbered_list and has_steps:
        return "carousel"

    # Branded stat card for number-heavy content
    if has_big_numbers and len(body) < 600:
        return "branded_card"

    # Branded comparison card
    if has_comparison:
        return "branded_card"

    # Default: AI-generated image for story-driven content
    return "ai_image"


def _detect_branded_card_type(post_data: dict) -> str:
    """Detect which branded card type to use.

    Returns: "stat_card", "comparison", "insight_card", "tip_list", or "quote_card"
    """
    import re

    body = post_data.get("body", post_data.get("final_text", ""))
    format_style = post_data.get("format_style", "")

    has_comparison = any(w in body.lower() for w in ["before", "vs", "versus", "instead of"])
    has_numbers = bool(re.findall(r'\b\d{2,}[xX%]|\$[\d,]+', body))
    has_list = bool(re.findall(r'(?:^|\n)\s*\d+[\.\)]\s+', body))

    if has_comparison:
        return "comparison"
    if has_numbers:
        return "stat_card"
    if has_list:
        return "tip_list"
    if format_style in ("curated_lesson", "curated_synthesis"):
        return "insight_card"
    return "quote_card"


def generate_smart_visual(post_data: dict) -> tuple[Path | None, str]:
    """Generate the optimal visual for a post using intelligent rotation.

    Analyzes post content, format style, and theme to pick the best visual
    format: AI-generated image, branded Pillow card, or carousel PDF.

    Args:
        post_data: Dict with keys like 'body'/'final_text', 'headline',
                   'format_style', 'story_theme', 'content_type', etc.

    Returns:
        Tuple of (path_to_visual, visual_type_string)
        visual_type_string is one of: "ai_image", "carousel", "stat_card",
        "comparison", "insight_card", "tip_list", "quote_card"
    """
    visual_format = _detect_visual_format(post_data)
    body = post_data.get("body", post_data.get("final_text", ""))
    headline = post_data.get("headline", "")
    theme = post_data.get("story_theme", post_data.get("content_mix_category", ""))

    logger.info(f"[smart_visual] detected format: {visual_format} for theme={theme}")

    if visual_format == "ai_image":
        # Use the AI image pipeline (DALL-E → Flux → Pillow fallback)
        path = generate_post_image(
            post_text=body,
            post_theme=theme,
            headline=headline,
        )
        return path, "ai_image"

    elif visual_format == "carousel":
        # Generate a carousel PDF
        try:
            from tools.visual_generator import generate_carousel_pdf
            slides = _build_carousel_slides(post_data)
            if slides and len(slides) >= 3:
                path = generate_carousel_pdf(slides, title=headline[:30])
                return path, "carousel"
        except Exception as e:
            logger.warning(f"[smart_visual] carousel generation failed: {e}")

        # Fallback to AI image
        path = generate_post_image(post_text=body, post_theme=theme, headline=headline)
        return path, "ai_image"

    elif visual_format == "branded_card":
        # Generate a branded Pillow card (stat, comparison, insight, etc.)
        card_type = _detect_branded_card_type(post_data)
        try:
            path = _generate_branded_card(post_data, card_type)
            if path:
                return path, card_type
        except Exception as e:
            logger.warning(f"[smart_visual] branded card failed: {e}")

        # Fallback to AI image
        path = generate_post_image(post_text=body, post_theme=theme, headline=headline)
        return path, "ai_image"

    # Ultimate fallback
    path = generate_post_image(post_text=body, post_theme=theme, headline=headline)
    return path, "ai_image"


def _build_carousel_slides(post_data: dict) -> list[dict]:
    """Extract carousel slides from post content.

    Parses the post body to create 6-10 slides following
    the Hook / Value / CTA framework.
    """
    import re

    body = post_data.get("body", post_data.get("final_text", ""))
    headline = post_data.get("headline", "")
    save_worthy = post_data.get("save_worthy_element", "")

    slides = []

    # Slide 1: Hook/Cover
    slides.append({
        "title": headline or body.split("\n")[0][:80],
        "body": "",
    })

    # Try to extract numbered items
    numbered = re.findall(r'(?:^|\n)\s*(\d+[\.\)]\s*.+?)(?=\n\s*\d+[\.\)]|\n\n|$)', body, re.DOTALL)

    if numbered and len(numbered) >= 3:
        # Use numbered items as individual slides
        for item in numbered[:8]:
            clean = re.sub(r'^\d+[\.\)]\s*', '', item.strip())
            if len(clean) > 200:
                title = clean[:80]
                body_text = clean[80:]
            else:
                title = clean
                body_text = ""
            slides.append({"title": title, "body": body_text})
    else:
        # Split by paragraphs
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and len(p.strip()) > 30]
        for para in paragraphs[:8]:
            lines = para.split("\n")
            title = lines[0][:100] if lines else ""
            body_text = "\n".join(lines[1:]) if len(lines) > 1 else ""
            slides.append({"title": title, "body": body_text})

    # Save-worthy slide (if we have one)
    if save_worthy and len(slides) < 10:
        slides.append({
            "title": "Key Takeaway",
            "body": save_worthy,
        })

    # CTA slide
    slides.append({
        "title": "Found this useful?",
        "body": "Save this post for later.\n\nFollow Justin Bellware for more\nUsing AI to Scale",
    })

    return slides


def _generate_branded_card(post_data: dict, card_type: str) -> Path | None:
    """Generate a specific branded card type using visual_generator."""
    import re
    from tools.visual_generator import (
        generate_stat_card,
        generate_comparison_card,
        generate_insight_card,
        generate_tip_list_image,
        generate_quote_card,
    )

    body = post_data.get("body", post_data.get("final_text", ""))
    headline = post_data.get("headline", "")
    key_insight = post_data.get("key_insight", post_data.get("save_worthy_element", ""))

    if card_type == "stat_card":
        numbers = re.findall(
            r'(\$[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?[xX%]?'
            r'(?:\s*(?:hours?|hrs?|days?|weeks?|months?|minutes?|mins?))?)',
            body
        )
        big_num = numbers[0].strip() if numbers else "10X"
        context = key_insight or headline or "The numbers tell the story"
        return generate_stat_card(big_num, context)

    elif card_type == "comparison":
        # Try to build comparison data from body
        paragraphs = body.split("\n\n")
        left_items = ["Manual processes", "Hiring slowly", "Scaling with headcount"]
        right_items = ["AI-powered systems", "AI VA in 48 hours", "Scaling with agents"]
        if len(paragraphs) >= 2:
            left = [s.strip() for s in paragraphs[0].split("\n") if s.strip()][:5]
            right = [s.strip() for s in paragraphs[-1].split("\n") if s.strip()][:5]
            if left and right:
                left_items, right_items = left, right
        return generate_comparison_card(
            "Before", left_items, "After", right_items, headline=headline
        )

    elif card_type == "insight_card":
        insight = key_insight or headline or body.split(".")[0]
        category = post_data.get("type", "").replace("_", " ").title() or "AI Implementation"
        return generate_insight_card(insight, category=category)

    elif card_type == "tip_list":
        tips = re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|[\-\*]\s*)(.+?)(?:\n|$)', body)
        if tips and len(tips) >= 3:
            return generate_tip_list_image(tips[:7], title=headline)
        sentences = [s.strip() for s in body.split(".") if len(s.strip()) > 20]
        if len(sentences) >= 3:
            return generate_tip_list_image(sentences[:6], title=headline)
        return None

    elif card_type == "quote_card":
        quote = key_insight or headline or body.split(".")[0]
        return generate_quote_card(quote)

    return None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if "--test" in sys.argv:
        # Test with a sample post
        test_text = """I hired a developer two weeks ago. Last Friday he quit.
        This morning I finished his work in 30 minutes.
        He was using AI as a spell checker. I was using it as a factory floor."""

        print("Testing image generation (portrait 4:5)...")
        path = generate_post_image(
            post_text=test_text,
            post_theme="developer_quit",
            headline="Two Weeks of Work. 30 Minutes.",
        )
        if path:
            print(f"✓ Generated: {path} ({Path(path).stat().st_size / 1024:.0f} KB)")
        else:
            print("✗ Failed")

    elif "--smart" in sys.argv:
        # Test smart visual rotation
        test_data = {
            "body": "1. Audit your current manual processes\n2. Identify the 3 highest-leverage tasks\n"
                    "3. Build an AI agent for each one\n4. Let it run for a week\n5. Measure the delta",
            "headline": "5 Steps to Replace Your First Department with AI",
            "format_style": "framework_system",
            "story_theme": "systems_first",
        }
        print("Testing smart visual rotation...")
        path, vtype = generate_smart_visual(test_data)
        if path:
            print(f"✓ Generated {vtype}: {path} ({Path(path).stat().st_size / 1024:.0f} KB)")
        else:
            print(f"✗ Failed (detected type: {vtype})")
    else:
        print("Usage: python3 -m tools.ai_image_generator --test|--smart")
