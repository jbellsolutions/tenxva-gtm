"""Visual Generator — creates branded images and carousel PDFs for LinkedIn posts.

Visual Types:
- Quote cards: Bold insight text on branded dark background (1080x1080)
- Stat cards: Big number/stat with context — most saved visual format on LinkedIn
- Tip list images: Numbered tips in visual format — screenshot-worthy
- Insight cards: Clean minimalist card with key takeaway and gradient accent
- Comparison cards: Before/after or this vs that — high engagement
- Carousel PDFs: Multi-slide content for framework/save-worthy posts (1080x1350)
- Charts: Data visualizations for data-heavy posts (1080x1080)

Themes:
- dark_navy: Primary dark theme (default)
- gradient_blue: Modern blue gradient
- warm_dark: Warm dark tones
- clean_light: Light background with dark text

Brand:
- Primary: #1a1a2e (dark navy)
- Accent: #0096FF (electric blue)
- Text: #ffffff (white)
- Secondary: #e94560 (red-orange emphasis)
- Font: Inter (or fallback to Arial)
"""

from __future__ import annotations

import logging
import textwrap
import random
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Brand constants
BRAND = {
    "primary": "#1a1a2e",
    "accent": "#0096FF",
    "text": "#ffffff",
    "secondary": "#e94560",
    "font": "Inter",
    "font_fallback": "Arial",
    "author": "Justin Bellware",
    "handle": "Using AI to Scale",
}

# Theme variations for visual variety
THEMES = {
    "dark_navy": {
        "bg": "#1a1a2e",
        "accent": "#0096FF",
        "text": "#ffffff",
        "muted": "#888888",
        "secondary": "#e94560",
    },
    "gradient_blue": {
        "bg": "#0f1729",
        "accent": "#00d4ff",
        "text": "#ffffff",
        "muted": "#7a8ba8",
        "secondary": "#6c63ff",
    },
    "warm_dark": {
        "bg": "#1c1917",
        "accent": "#f59e0b",
        "text": "#fafaf9",
        "muted": "#a8a29e",
        "secondary": "#ef4444",
    },
    "clean_light": {
        "bg": "#f8fafc",
        "accent": "#0096FF",
        "text": "#1e293b",
        "muted": "#94a3b8",
        "secondary": "#e94560",
    },
}

DATA_DIR = Path(__file__).parent.parent / "data"
VISUAL_DIR = DATA_DIR / "visuals"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _get_font(size: int, bold: bool = False):
    """Get a PIL font, falling back gracefully."""
    from PIL import ImageFont

    font_names = [
        "Inter-Bold.ttf" if bold else "Inter-Regular.ttf",
        "Inter.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue

    # Last resort: default font
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
                                   else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", size)
    except (OSError, IOError):
        return ImageFont.load_default()


def generate_quote_card(
    quote_text: str,
    author: str = BRAND["author"],
    handle: str = BRAND["handle"],
    accent_color: str | None = None,
) -> Path:
    """Generate a branded quote card image (1080x1080).

    Args:
        quote_text: The main insight/quote text
        author: Author name (default: Justin Bellware)
        handle: Author handle/brand (default: Using AI to Scale)
        accent_color: Override accent color (hex)

    Returns:
        Path to the generated PNG file
    """
    from PIL import Image, ImageDraw

    width, height = 1080, 1080
    bg_color = _hex_to_rgb(BRAND["primary"])
    text_color = _hex_to_rgb(BRAND["text"])
    accent = _hex_to_rgb(accent_color or BRAND["accent"])

    # Create image
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Accent bar at top
    draw.rectangle([(0, 0), (width, 6)], fill=accent)

    # Quote text — wrap and size dynamically
    quote_font_size = 48 if len(quote_text) < 100 else 40 if len(quote_text) < 200 else 34
    quote_font = _get_font(quote_font_size, bold=True)

    # Wrap text
    max_chars = 32 if quote_font_size >= 48 else 38 if quote_font_size >= 40 else 44
    wrapped = textwrap.fill(quote_text, width=max_chars)
    lines = wrapped.split("\n")

    # Calculate text block height
    line_height = int(quote_font_size * 1.4)
    text_block_height = len(lines) * line_height

    # Center text vertically (slightly above center)
    y_start = (height - text_block_height) // 2 - 60
    x_margin = 80

    # Draw quote mark
    quote_mark_font = _get_font(120, bold=True)
    draw.text((x_margin - 10, y_start - 100), "\u201c", fill=accent, font=quote_mark_font)

    # Draw each line
    for i, line in enumerate(lines):
        y = y_start + (i * line_height)
        draw.text((x_margin, y), line, fill=text_color, font=quote_font)

    # Author section at bottom
    author_font = _get_font(24, bold=True)
    handle_font = _get_font(20, bold=False)

    # Accent line above author
    author_y = height - 140
    draw.line([(x_margin, author_y), (x_margin + 60, author_y)], fill=accent, width=3)

    # Author name
    draw.text((x_margin, author_y + 15), author, fill=text_color, font=author_font)

    # Handle
    draw.text((x_margin, author_y + 50), handle, fill=_hex_to_rgb("#888888"), font=handle_font)

    # Save
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"quote_card_{timestamp}.png"
    path = VISUAL_DIR / filename
    img.save(str(path), "PNG", quality=95)

    logger.info(f"[visual_generator] created quote card: {path}")
    return path


def generate_carousel_pdf(
    slides: list[dict],
    title: str = "",
) -> Path:
    """Generate a carousel PDF for LinkedIn (1080x1350 per slide, portrait 4:5).

    LinkedIn 2026 best practices:
    - Portrait 1080x1350 for max mobile feed real estate
    - 8-10 slides optimal, engagement drops after 10
    - Swipe cue arrow on right edge (reduces drop-off)
    - Min 28px font size for mobile readability
    - Progress bar at bottom for orientation
    - Hook/Value/CTA framework

    Args:
        slides: List of dicts with 'title' and 'body' keys per slide.
                 First slide should be the cover. Last slide can be the CTA.
        title: Overall carousel title (used in filename)

    Returns:
        Path to the generated PDF file
    """
    from PIL import Image, ImageDraw

    width, height = 1080, 1350
    bg_color = _hex_to_rgb(BRAND["primary"])
    text_color = _hex_to_rgb(BRAND["text"])
    accent = _hex_to_rgb(BRAND["accent"])
    muted = _hex_to_rgb("#888888")

    images = []

    for idx, slide in enumerate(slides):
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Gradient accent bar at top (12px fade)
        for i in range(12):
            alpha = 1.0 - (i / 12.0)
            r = int(accent[0] * alpha + bg_color[0] * (1 - alpha))
            g = int(accent[1] * alpha + bg_color[1] * (1 - alpha))
            b = int(accent[2] * alpha + bg_color[2] * (1 - alpha))
            draw.rectangle([(0, i), (width, i + 1)], fill=(r, g, b))

        # Slide number indicator (top right)
        if len(slides) > 1:
            num_font = _get_font(22, bold=False)
            slide_num = f"{idx + 1}/{len(slides)}"
            draw.text((width - 110, 24), slide_num, fill=_hex_to_rgb("#666666"), font=num_font)

        slide_title = slide.get("title", "")
        slide_body = slide.get("body", "")

        if idx == 0:
            # Cover slide — big title, dramatic
            title_font = _get_font(60, bold=True)
            wrapped_title = textwrap.fill(slide_title, width=22)
            title_lines = wrapped_title.split("\n")
            title_line_height = 76

            title_block = len(title_lines) * title_line_height
            y_start = (height - title_block) // 2 - 60

            for i, line in enumerate(title_lines):
                draw.text((80, y_start + i * title_line_height), line, fill=text_color, font=title_font)

            # Author at bottom
            author_font = _get_font(26, bold=True)
            handle_font = _get_font(22, bold=False)
            draw.line([(80, height - 180), (150, height - 180)], fill=accent, width=3)
            draw.text((80, height - 155), BRAND["author"], fill=text_color, font=author_font)
            draw.text((80, height - 120), BRAND["handle"], fill=muted, font=handle_font)

            if slide_body:
                sub_font = _get_font(30, bold=False)
                sub_y = y_start + title_block + 40
                wrapped_sub = textwrap.fill(slide_body, width=34)
                for i, line in enumerate(wrapped_sub.split("\n")[:3]):
                    draw.text((80, sub_y + i * 40), line, fill=_hex_to_rgb("#cccccc"), font=sub_font)

        else:
            # Content slide
            title_font = _get_font(40, bold=True)
            y = 60
            if slide_title:
                wrapped_title = textwrap.fill(slide_title, width=26)
                for line in wrapped_title.split("\n"):
                    draw.text((80, y), line, fill=accent, font=title_font)
                    y += 54
                y += 30  # Space after title

                # Accent underline below title
                draw.rectangle([(80, y - 20), (200, y - 17)], fill=accent)
                y += 10

            # Body text — larger for mobile readability (min 28px)
            body_font = _get_font(30, bold=False)
            if slide_body:
                wrapped_body = textwrap.fill(slide_body, width=34)
                body_line_height = 42
                for line in wrapped_body.split("\n"):
                    if y > height - 120:
                        break
                    draw.text((80, y), line, fill=text_color, font=body_font)
                    y += body_line_height

        # Swipe cue arrow (right edge, middle) — reduces drop-off between slides
        if idx < len(slides) - 1:
            arrow_font = _get_font(36, bold=True)
            arrow_y = height // 2
            # Subtle chevron ">"
            draw.text((width - 50, arrow_y - 18), "\u203a", fill=_hex_to_rgb("#444444"), font=arrow_font)

        # Progress bar at bottom
        if len(slides) > 1:
            bar_y = height - 24
            bar_width = width - 160
            progress = (idx + 1) / len(slides)
            # Background bar
            draw.rectangle([(80, bar_y), (80 + bar_width, bar_y + 5)], fill=_hex_to_rgb("#333333"))
            # Progress fill
            draw.rectangle([(80, bar_y), (80 + int(bar_width * progress), bar_y + 5)], fill=accent)

        images.append(img)

    # Save as PDF (LinkedIn accepts PDF for carousel/document posts)
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " _-").strip().replace(" ", "_")
    filename = f"carousel_{safe_title}_{timestamp}.pdf"
    path = VISUAL_DIR / filename

    if images:
        images[0].save(
            str(path),
            "PDF",
            save_all=True,
            append_images=images[1:],
            resolution=150,
        )

    size_kb = path.stat().st_size / 1024 if path.exists() else 0
    logger.info(f"[visual_generator] created carousel PDF ({len(slides)} slides, {size_kb:.0f} KB): {path}")
    return path


def generate_chart_image(
    data: dict,
    chart_type: str = "bar",
    title: str = "",
) -> Path:
    """Generate a branded chart image (1080x1080).

    Args:
        data: Dict with 'labels' and 'values' keys (and optionally 'colors')
        chart_type: 'bar', 'horizontal_bar', or 'comparison'
        title: Chart title

    Returns:
        Path to the generated PNG file
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10.8, 10.8), dpi=100)
    fig.patch.set_facecolor(BRAND["primary"])
    ax.set_facecolor(BRAND["primary"])

    labels = data.get("labels", [])
    values = data.get("values", [])
    colors = data.get("colors", [BRAND["accent"]] * len(labels))

    if chart_type == "horizontal_bar":
        bars = ax.barh(labels, values, color=colors)
        ax.invert_yaxis()
        # Add value labels
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", color="white", fontsize=14, fontweight="bold",
            )
    elif chart_type == "comparison":
        x_pos = range(len(labels))
        bars = ax.bar(x_pos, values, color=colors, width=0.6)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, rotation=0)
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(val), ha="center", color="white", fontsize=14, fontweight="bold",
            )
    else:  # default bar
        x_pos = range(len(labels))
        bars = ax.bar(x_pos, values, color=colors, width=0.6)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, rotation=45, ha="right")
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                str(val), ha="center", color="white", fontsize=12, fontweight="bold",
            )

    # Style
    if title:
        ax.set_title(title, color="white", fontsize=20, fontweight="bold", pad=20)
    ax.tick_params(colors="white", labelsize=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#333333")
    ax.spines["bottom"].set_color("#333333")

    # Author watermark
    fig.text(
        0.95, 0.02, f"{BRAND['author']} | {BRAND['handle']}",
        color="#666666", fontsize=10, ha="right",
    )

    plt.tight_layout()

    # Save
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chart_{timestamp}.png"
    path = VISUAL_DIR / filename
    fig.savefig(str(path), dpi=100, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

    logger.info(f"[visual_generator] created chart: {path}")
    return path


def _pick_theme(exclude: str = "clean_light") -> dict:
    """Pick a random theme for variety, excluding light theme by default."""
    options = [t for name, t in THEMES.items() if name != exclude]
    return random.choice(options)


def generate_stat_card(
    big_number: str,
    context_text: str,
    subtitle: str = "",
    theme: str = "dark_navy",
) -> Path:
    """Generate a stat card image — most saved visual format on LinkedIn.

    Big bold number/stat with context text below. Popular for:
    - "48 hours to build a custom CRM"
    - "5 AI agent teams managed by one ops manager"
    - "$1,100 in API tokens saved"

    Args:
        big_number: The hero stat/number ("48 hrs", "5x", "$1,100")
        context_text: What the number means (1-2 lines)
        subtitle: Optional smaller context line
        theme: Theme name from THEMES

    Returns:
        Path to the generated PNG file
    """
    from PIL import Image, ImageDraw

    width, height = 1080, 1080
    t = THEMES.get(theme, THEMES["dark_navy"])
    bg_color = _hex_to_rgb(t["bg"])
    text_color = _hex_to_rgb(t["text"])
    accent = _hex_to_rgb(t["accent"])
    muted = _hex_to_rgb(t["muted"])

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Accent bar at top
    draw.rectangle([(0, 0), (width, 8)], fill=accent)

    # Big number — hero element
    num_font_size = 120 if len(big_number) <= 5 else 96 if len(big_number) <= 8 else 72
    num_font = _get_font(num_font_size, bold=True)

    # Center the number
    try:
        bbox = draw.textbbox((0, 0), big_number, font=num_font)
        num_w = bbox[2] - bbox[0]
    except (AttributeError, TypeError):
        num_w = len(big_number) * num_font_size * 0.6
    num_x = (width - num_w) // 2
    num_y = height // 2 - 160

    draw.text((num_x, num_y), big_number, fill=accent, font=num_font)

    # Context text
    ctx_font = _get_font(32, bold=False)
    wrapped_ctx = textwrap.fill(context_text, width=36)
    ctx_lines = wrapped_ctx.split("\n")
    ctx_y = num_y + num_font_size + 40

    for i, line in enumerate(ctx_lines):
        try:
            bbox = draw.textbbox((0, 0), line, font=ctx_font)
            line_w = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            line_w = len(line) * 18
        draw.text(((width - line_w) // 2, ctx_y + i * 44), line, fill=text_color, font=ctx_font)

    # Subtitle
    if subtitle:
        sub_font = _get_font(22, bold=False)
        sub_y = ctx_y + len(ctx_lines) * 44 + 20
        try:
            bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
            sub_w = bbox[2] - bbox[0]
        except (AttributeError, TypeError):
            sub_w = len(subtitle) * 12
        draw.text(((width - sub_w) // 2, sub_y), subtitle, fill=muted, font=sub_font)

    # Author watermark at bottom
    author_font = _get_font(20, bold=False)
    author_text = f"{BRAND['author']}  |  {BRAND['handle']}"
    try:
        bbox = draw.textbbox((0, 0), author_text, font=author_font)
        aw = bbox[2] - bbox[0]
    except (AttributeError, TypeError):
        aw = len(author_text) * 11
    draw.text(((width - aw) // 2, height - 60), author_text, fill=muted, font=author_font)

    # Save
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = VISUAL_DIR / f"stat_card_{timestamp}.png"
    img.save(str(path), "PNG", quality=95)

    logger.info(f"[visual_generator] created stat card: {path}")
    return path


def generate_tip_list_image(
    tips: list[str],
    title: str = "",
    theme: str = "dark_navy",
) -> Path:
    """Generate a numbered tip list image — screenshot-worthy format.

    Popular on LinkedIn for frameworks, step-by-step, and "save this" content.

    Args:
        tips: List of 3-7 tips/steps (short text each)
        title: Optional header title
        theme: Theme name

    Returns:
        Path to the generated PNG file
    """
    from PIL import Image, ImageDraw

    width, height = 1080, 1080
    t = THEMES.get(theme, THEMES["dark_navy"])
    bg_color = _hex_to_rgb(t["bg"])
    text_color = _hex_to_rgb(t["text"])
    accent = _hex_to_rgb(t["accent"])
    muted = _hex_to_rgb(t["muted"])

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Accent bar
    draw.rectangle([(0, 0), (width, 6)], fill=accent)

    x_margin = 80
    y = 60

    # Title
    if title:
        title_font = _get_font(40, bold=True)
        wrapped_title = textwrap.fill(title, width=28)
        for line in wrapped_title.split("\n"):
            draw.text((x_margin, y), line, fill=text_color, font=title_font)
            y += 52
        y += 30  # Space after title
        # Divider line
        draw.line([(x_margin, y), (x_margin + 100, y)], fill=accent, width=3)
        y += 30

    # Tips
    num_font = _get_font(36, bold=True)
    tip_font = _get_font(26, bold=False)
    tip_spacing = max(60, (height - y - 120) // max(len(tips), 1))

    for i, tip in enumerate(tips[:7]):
        if y > height - 100:
            break

        # Number circle
        circle_x = x_margin + 20
        circle_y = y + 5
        circle_r = 22
        draw.ellipse(
            [(circle_x - circle_r, circle_y - circle_r),
             (circle_x + circle_r, circle_y + circle_r)],
            fill=accent,
        )
        draw.text((circle_x - 8, circle_y - 16), str(i + 1), fill=bg_color, font=num_font)

        # Tip text
        tip_x = x_margin + 65
        wrapped_tip = textwrap.fill(tip, width=34)
        tip_lines = wrapped_tip.split("\n")
        for j, line in enumerate(tip_lines):
            draw.text((tip_x, y + j * 32), line, fill=text_color, font=tip_font)

        y += max(tip_spacing, len(tip_lines) * 32 + 20)

    # Author watermark
    author_font = _get_font(18, bold=False)
    draw.text((x_margin, height - 50),
              f"{BRAND['author']}  |  {BRAND['handle']}",
              fill=muted, font=author_font)

    # Save
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = VISUAL_DIR / f"tip_list_{timestamp}.png"
    img.save(str(path), "PNG", quality=95)

    logger.info(f"[visual_generator] created tip list ({len(tips)} tips): {path}")
    return path


def generate_insight_card(
    insight_text: str,
    category: str = "",
    theme: str = "gradient_blue",
) -> Path:
    """Generate a clean insight card — modern minimalist style.

    Single key takeaway with clean typography and subtle gradient accent.
    Popular on LinkedIn for thought leadership content.

    Args:
        insight_text: The key insight (1-3 sentences)
        category: Optional category label ("AI Implementation", "Leadership", etc.)
        theme: Theme name

    Returns:
        Path to the generated PNG file
    """
    from PIL import Image, ImageDraw

    width, height = 1080, 1080
    t = THEMES.get(theme, THEMES["gradient_blue"])
    bg_color = _hex_to_rgb(t["bg"])
    text_color = _hex_to_rgb(t["text"])
    accent = _hex_to_rgb(t["accent"])
    muted = _hex_to_rgb(t["muted"])
    secondary = _hex_to_rgb(t.get("secondary", t["accent"]))

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    x_margin = 100

    # Gradient accent bar at top (simulate with multiple thin lines)
    for i in range(12):
        alpha = 1.0 - (i / 12.0)
        r = int(accent[0] * alpha + bg_color[0] * (1 - alpha))
        g = int(accent[1] * alpha + bg_color[1] * (1 - alpha))
        b = int(accent[2] * alpha + bg_color[2] * (1 - alpha))
        draw.rectangle([(0, i * 2), (width, i * 2 + 2)], fill=(r, g, b))

    # Category label
    y = 120
    if category:
        cat_font = _get_font(18, bold=True)
        draw.text((x_margin, y), category.upper(), fill=accent, font=cat_font)
        y += 50

    # Accent vertical line
    draw.rectangle([(x_margin - 20, y), (x_margin - 14, y + 300)], fill=accent)

    # Insight text — large, clean typography
    font_size = 42 if len(insight_text) < 120 else 36 if len(insight_text) < 200 else 30
    insight_font = _get_font(font_size, bold=True)

    max_chars = 28 if font_size >= 42 else 32 if font_size >= 36 else 38
    wrapped = textwrap.fill(insight_text, width=max_chars)
    lines = wrapped.split("\n")

    line_height = int(font_size * 1.5)
    for i, line in enumerate(lines):
        draw.text((x_margin, y + i * line_height), line, fill=text_color, font=insight_font)

    # Author section at bottom
    author_y = height - 120
    draw.line([(x_margin, author_y), (x_margin + 50, author_y)], fill=accent, width=2)

    author_font = _get_font(22, bold=True)
    handle_font = _get_font(18, bold=False)
    draw.text((x_margin, author_y + 15), BRAND["author"], fill=text_color, font=author_font)
    draw.text((x_margin, author_y + 45), BRAND["handle"], fill=muted, font=handle_font)

    # Save
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = VISUAL_DIR / f"insight_card_{timestamp}.png"
    img.save(str(path), "PNG", quality=95)

    logger.info(f"[visual_generator] created insight card: {path}")
    return path


def generate_comparison_card(
    left_title: str,
    left_items: list[str],
    right_title: str,
    right_items: list[str],
    headline: str = "",
    theme: str = "dark_navy",
) -> Path:
    """Generate a before/after or this-vs-that comparison card.

    Two-column layout showing contrast. High engagement on LinkedIn.

    Args:
        left_title: Left column header (e.g., "Before AI VAs", "Most People")
        left_items: Left column items (negatives/old way)
        right_title: Right column header (e.g., "After AI VAs", "Top Performers")
        right_items: Right column items (positives/new way)
        headline: Optional top headline
        theme: Theme name

    Returns:
        Path to the generated PNG file
    """
    from PIL import Image, ImageDraw

    width, height = 1080, 1080
    t = THEMES.get(theme, THEMES["dark_navy"])
    bg_color = _hex_to_rgb(t["bg"])
    text_color = _hex_to_rgb(t["text"])
    accent = _hex_to_rgb(t["accent"])
    muted = _hex_to_rgb(t["muted"])
    secondary = _hex_to_rgb(t.get("secondary", "#e94560"))

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Accent bar
    draw.rectangle([(0, 0), (width, 6)], fill=accent)

    x_margin = 60
    mid_x = width // 2
    y = 50

    # Headline
    if headline:
        hl_font = _get_font(34, bold=True)
        wrapped_hl = textwrap.fill(headline, width=30)
        for line in wrapped_hl.split("\n"):
            draw.text((x_margin, y), line, fill=text_color, font=hl_font)
            y += 44
        y += 20

    # Divider
    draw.line([(mid_x, y), (mid_x, height - 80)], fill=_hex_to_rgb("#333333"), width=2)

    # Column headers
    col_font = _get_font(28, bold=True)

    # Left header (with X marker for "bad")
    draw.text((x_margin, y), "\u2717", fill=secondary, font=col_font)
    draw.text((x_margin + 35, y), left_title, fill=secondary, font=col_font)

    # Right header (with check marker for "good")
    draw.text((mid_x + 30, y), "\u2713", fill=accent, font=col_font)
    draw.text((mid_x + 65, y), right_title, fill=accent, font=col_font)
    y += 60

    # Items
    item_font = _get_font(22, bold=False)
    max_items = max(len(left_items), len(right_items))
    item_spacing = min(80, (height - y - 100) // max(max_items, 1))

    for i in range(max_items):
        item_y = y + i * item_spacing

        # Left item
        if i < len(left_items):
            wrapped = textwrap.fill(left_items[i], width=22)
            for j, line in enumerate(wrapped.split("\n")):
                draw.text((x_margin, item_y + j * 28), line, fill=muted, font=item_font)

        # Right item
        if i < len(right_items):
            wrapped = textwrap.fill(right_items[i], width=22)
            for j, line in enumerate(wrapped.split("\n")):
                draw.text((mid_x + 30, item_y + j * 28), line, fill=text_color, font=item_font)

    # Author watermark
    author_font = _get_font(18, bold=False)
    draw.text((x_margin, height - 50),
              f"{BRAND['author']}  |  {BRAND['handle']}",
              fill=muted, font=author_font)

    # Save
    VISUAL_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = VISUAL_DIR / f"comparison_{timestamp}.png"
    img.save(str(path), "PNG", quality=95)

    logger.info(f"[visual_generator] created comparison card: {path}")
    return path


def generate_visual_for_post(post: dict) -> Path | None:
    """Auto-generate the right visual based on post metadata.

    Reads the post's visual_type and content to generate the appropriate visual.
    Supports: quote_card, stat_card, tip_list, insight_card, comparison,
              carousel, chart, auto (picks best type based on content).

    Args:
        post: Post dict with at minimum 'visual_type' and 'body' keys

    Returns:
        Path to generated visual file, or None if visual_type is 'none'
    """
    visual_type = post.get("visual_type", "none")

    if visual_type == "none" or not visual_type:
        return None

    # Pick a random theme for variety (except clean_light for most types)
    theme_name = random.choice([k for k in THEMES if k != "clean_light"])

    if visual_type == "quote_card":
        # Extract the key insight or headline as the quote
        quote = post.get("save_worthy_element") or post.get("headline") or post.get("key_insight", "")
        if not quote:
            body = post.get("body", "")
            sentences = body.split(".")
            quote = sentences[0].strip() + "." if sentences else ""

        if quote:
            return generate_quote_card(quote)

    elif visual_type == "stat_card":
        # Extract numbers from the post
        import re
        body = post.get("body", "")
        key_insight = post.get("key_insight", "")

        # Try to find a stat/number in the content
        numbers = re.findall(
            r'(\$[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?[xX%]?(?:\s*(?:hours?|hrs?|days?|weeks?|months?|minutes?|mins?))?)',
            body + " " + key_insight
        )
        if numbers:
            big_num = numbers[0].strip()
            context = key_insight or post.get("save_worthy_element", "") or post.get("headline", "")
            return generate_stat_card(big_num, context, theme=theme_name)

    elif visual_type == "tip_list":
        # Extract tips from the post body
        body = post.get("body", "")
        headline = post.get("headline", "")

        # Try to find numbered items or bullet points
        import re
        tip_patterns = re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|[\-\*\u2022]\s*)(.+?)(?:\n|$)', body)

        if tip_patterns and len(tip_patterns) >= 3:
            return generate_tip_list_image(tip_patterns[:7], title=headline, theme=theme_name)

        # Fallback: split by sentences for framework posts
        sentences = [s.strip() for s in body.split(".") if len(s.strip()) > 20]
        if len(sentences) >= 3:
            return generate_tip_list_image(sentences[:6], title=headline, theme=theme_name)

    elif visual_type == "insight_card":
        insight = post.get("key_insight") or post.get("save_worthy_element") or post.get("headline", "")
        if insight:
            category = post.get("type", "").replace("_", " ").title()
            return generate_insight_card(insight, category=category, theme=theme_name)

    elif visual_type == "comparison":
        # Comparison cards need structured data — try to extract from body
        body = post.get("body", "")
        headline = post.get("headline", "")

        # Look for before/after or vs patterns
        import re
        # Simple heuristic: if post contains "before" and "after" or "vs"
        if any(word in body.lower() for word in ["before", "vs", "versus", "instead of", "not this"]):
            paragraphs = body.split("\n\n")
            if len(paragraphs) >= 2:
                left_items = [s.strip() for s in paragraphs[0].split("\n") if s.strip()][:5]
                right_items = [s.strip() for s in paragraphs[-1].split("\n") if s.strip()][:5]
                if left_items and right_items:
                    return generate_comparison_card(
                        "Before", left_items,
                        "After", right_items,
                        headline=headline,
                        theme=theme_name,
                    )

    elif visual_type == "carousel":
        body = post.get("body", "")
        headline = post.get("headline", "")

        slides = [{"title": headline, "body": ""}]

        sections = body.split("\n\n")
        for section in sections:
            section = section.strip()
            if section and len(section) > 20:
                lines = section.split("\n")
                if len(lines) > 1:
                    slides.append({"title": lines[0], "body": "\n".join(lines[1:])})
                else:
                    slides.append({"title": "", "body": section})

        cta = post.get("cta", "")
        if cta and cta != "none":
            slides.append({
                "title": "Found this useful?",
                "body": f"Follow {BRAND['author']} for more AI insights\n{BRAND['handle']}",
            })

        if len(slides) >= 3:
            return generate_carousel_pdf(slides, title=headline[:30])

    elif visual_type == "chart":
        logger.info("[visual_generator] chart type requested but no structured data available")
        return None

    elif visual_type == "auto":
        # Auto-select best visual type based on content analysis
        body = post.get("body", "")
        format_style = post.get("format_style", "")

        import re
        has_numbers = bool(re.findall(r'\d+', body))
        has_list = bool(re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|[\-\*\u2022]\s*)', body))

        if format_style == "framework_system" and has_list:
            post["visual_type"] = "tip_list"
        elif has_numbers and len(body) < 500:
            post["visual_type"] = "stat_card"
        elif format_style in ("big_idea", "curated_lesson"):
            post["visual_type"] = "insight_card"
        elif format_style == "myth_busting":
            post["visual_type"] = "comparison"
        else:
            post["visual_type"] = "quote_card"

        return generate_visual_for_post(post)

    return None
