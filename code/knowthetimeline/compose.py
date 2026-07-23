from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .errors import KttError
from .job import compose_settings
from . import settings

W = settings.VIDEO_WIDTH
H = settings.VIDEO_HEIGHT


@lru_cache(maxsize=16)
def load_font(size):
    for candidate in settings.FONT_CANDIDATES:
        try:
            if candidate.is_file():
                return ImageFont.truetype(str(candidate), size)
        except Exception:
            continue
    return ImageFont.load_default()


def fit_cover(image, width, height):
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    new_size = (max(1, round(src_w * scale)), max(1, round(src_h * scale)))
    resized = image.resize(new_size, Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def line_height(font):
    ascent, descent = font.getmetrics()
    return ascent + descent


def text_width(draw, text, font):
    return draw.textlength(text, font=font)


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if text_width(draw, candidate, font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_centered(draw, cx, y, text, font, fill, shadow=(0, 0, 0, 200)):
    w = text_width(draw, text, font)
    x = cx - w / 2
    draw.text((x + 2, y + 2), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def build_lockup(node, cfg, draw):
    """Return an ordered list of rendered lines: (text, font, color, gap_after)."""
    margin_x = int(W * settings.SAFE_MARGIN_X)
    max_width = W - 2 * margin_x

    headline_font = load_font(int(W * 0.072))
    kicker_font = load_font(int(W * 0.036))
    subtitle_font = load_font(int(W * 0.036))
    signature_font = load_font(int(W * 0.030))

    lines = []

    if cfg["show_date_kicker"] and node.get("event_date_display"):
        lines.append(
            (node["event_date_display"].upper(), kicker_font, (214, 214, 214, 255), 18)
        )

    headline = node.get("headline", "")
    for line in wrap_text(draw, headline, headline_font, max_width):
        lines.append((line, headline_font, (255, 255, 255, 255), 8))
    if lines:
        text, font, color, _ = lines[-1]
        lines[-1] = (text, font, color, 24)

    if node.get("subtitle"):
        for line in wrap_text(draw, node["subtitle"], subtitle_font, max_width):
            lines.append((line, subtitle_font, (206, 206, 206, 255), 6))
        text, font, color, _ = lines[-1]
        lines[-1] = (text, font, color, 26)

    lines.append((settings.BRAND_SIGNATURE, signature_font, (176, 190, 210, 255), 0))
    return lines


def lockup_metrics(lines):
    total = 0
    for _, font, _, gap in lines:
        total += line_height(font) + gap
    return total


def apply_backdrop(base, cfg, bbox):
    mode = cfg["backdrop"]
    base = base.convert("RGBA")

    if mode == "full_blur":
        base = base.filter(ImageFilter.GaussianBlur(cfg["blur_radius"])).convert("RGBA")

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if mode == "scrim_plate":
        # Subtle vertical scrim, darker toward the center/bottom of the frame.
        scrim = Image.new("RGBA", base.size, (0, 0, 0, 0))
        scrim_draw = ImageDraw.Draw(scrim)
        for y in range(base.height):
            alpha = int(90 * (y / base.height))
            scrim_draw.line([(0, y), (base.width, y)], fill=(0, 0, 0, alpha))
        base = Image.alpha_composite(base, scrim)

    if mode in ("scrim_plate", "plate_only"):
        pad_x, pad_y = 46, 40
        plate_box = (
            bbox[0] - pad_x,
            bbox[1] - pad_y,
            bbox[2] + pad_x,
            bbox[3] + pad_y,
        )
        alpha = int(255 * cfg["plate_opacity"])
        draw.rounded_rectangle(plate_box, radius=36, fill=(0, 0, 0, alpha))

    base = Image.alpha_composite(base, overlay)
    return base


def compose_node(node, background_path, out_path, cfg):
    if not background_path.is_file():
        raise KttError(f"Background missing for node {node['id']}: {background_path}")

    background = Image.open(background_path).convert("RGB")
    base = fit_cover(background, W, H)

    measure = ImageDraw.Draw(base)
    lines = build_lockup(node, cfg, measure)
    total_h = lockup_metrics(lines)

    # Center the lockup group slightly above the true vertical center.
    group_center_y = int(H * 0.46)
    start_y = group_center_y - total_h // 2

    widest = 0
    for text, font, _, _ in lines:
        widest = max(widest, text_width(measure, text, font))
    cx = W // 2
    bbox = (cx - widest / 2, start_y, cx + widest / 2, start_y + total_h)

    composited = apply_backdrop(base, cfg, bbox)
    draw = ImageDraw.Draw(composited)

    y = start_y
    for text, font, color, gap in lines:
        draw_centered(draw, cx, y, text, font, color)
        y += line_height(font) + gap

    out_path.parent.mkdir(parents=True, exist_ok=True)
    composited.convert("RGB").save(out_path, "JPEG", quality=92)
    return out_path


def run_compose(job, timeline):
    """Stage 4: lay text onto each background -> frames/<id>.jpg."""
    cfg = compose_settings(job)
    job.frames_dir.mkdir(parents=True, exist_ok=True)

    print(f"Composing frames: backdrop={cfg['backdrop']}")
    frames = []
    for node in timeline.get("nodes", []):
        node_id = node["id"]
        background_path = job.backgrounds_dir / f"{node_id}.jpg"
        out_path = job.frames_dir / f"{node_id}.jpg"
        compose_node(node, background_path, out_path, cfg)
        frames.append(str(out_path))
        print(f"  node {node_id}: {out_path.name}")
    return frames
