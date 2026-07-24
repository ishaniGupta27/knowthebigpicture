import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
CODE_DIR = PACKAGE_DIR.parent
BASE_DIR = CODE_DIR.parent

PROMPTS_DIR = PACKAGE_DIR / "prompts"

# --- Canvas / encoding -------------------------------------------------------
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
# yuv420p + faststart are required for reliable phone / social playback.
FFMPEG_EXTRA_PARAMS = ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]

# --- Roles (narrative order) -------------------------------------------------
ROLE_PRESENT_HOOK = "present_hook"
ROLE_STARTING_POINT = "starting_point"
ROLE_DEVELOPMENT = "development"
ROLE_RESOLUTION = "resolution"

VALID_ROLES = (
    ROLE_PRESENT_HOOK,
    ROLE_STARTING_POINT,
    ROLE_DEVELOPMENT,
    ROLE_RESOLUTION,
)

# Roles whose headline must be backed by a verbatim source_quote.
QUOTED_ROLES = (
    ROLE_PRESENT_HOOK,
    ROLE_STARTING_POINT,
    ROLE_DEVELOPMENT,
    ROLE_RESOLUTION,
)

# Roles that carry a real event date and take part in the chronology check.
DATED_ROLES = (
    ROLE_STARTING_POINT,
    ROLE_DEVELOPMENT,
    ROLE_RESOLUTION,
)

# --- Parse defaults ----------------------------------------------------------
DEFAULT_PARSE_MODEL = "gpt-5-mini"
DEFAULT_MIN_DEVELOPMENTS = 3
DEFAULT_MAX_DEVELOPMENTS = 6
MAX_WORDS_PER_HEADLINE = 16

# --- Image defaults ----------------------------------------------------------
DEFAULT_IMAGE_MODEL = "gpt-image-1"
DEFAULT_VIBE = "cinematic_muted"
IMAGE_CONCURRENCY = 4
IMAGE_RETRIES = 2

# Portrait sizes the OpenAI models support; Stage 4 normalizes to the canvas.
IMAGE_SIZES = {
    "gpt-image-1": "1024x1536",
    "dall-e-3": "1024x1792",
}
DEFAULT_IMAGE_SIZE = "1024x1536"

# Constant, code-side technical rules appended to every image prompt so the
# "no text" guarantee can never be dropped from a vibe entry.
IMAGE_TECHNICAL_RULES = (
    "Vertical 9:16 composition with calm negative space in the center for a text "
    "overlay. Absolutely no text, words, letters, numbers, logos, or watermarks "
    "anywhere in the image."
)

# --- Compose (Pillow) defaults ----------------------------------------------
DEFAULT_BACKDROP = "scrim_plate"  # scrim_plate | full_blur | plate_only
DEFAULT_BLUR_RADIUS = 5
DEFAULT_PLATE_OPACITY = 0.45
DEFAULT_SHOW_DATE_KICKER = True
DEFAULT_SHOW_DETAIL = True
BRAND_SIGNATURE = "KnowTheTimeline"

# Safe-zone margins as fractions of the canvas (avoid platform UI overlays).
SAFE_MARGIN_X = 0.09
SAFE_MARGIN_TOP = 0.10
SAFE_MARGIN_BOTTOM = 0.16
SAFE_MARGIN_RIGHT = 0.12

# --- Timing (render plan) defaults ------------------------------------------
DEFAULT_MIN_SECONDS = 30.0
DEFAULT_MAX_SECONDS = 60.0
TIMING_BASE_BEAT = 2.0
TIMING_PER_WORD = 0.35
TIMING_READING_FLOOR = 3.5
TIMING_RESOLUTION_BONUS = 1.5
DEFAULT_OUTRO_DURATION = 3.5

# --- Video (stitch) defaults -------------------------------------------------
DEFAULT_MOTION = 0.06          # Ken Burns zoom fraction across a slide.
DEFAULT_TRANSITION = "cut"     # cut only for now.
DEFAULT_AUDIO_VOLUME = 0.25

# --- Shared assets -----------------------------------------------------------
ASSETS_DIR = BASE_DIR / "assets"
BRAND_STYLES_PATH = ASSETS_DIR / "brand" / "styles.json"
DEFAULT_OUTRO_IMAGE = ASSETS_DIR / "outro" / "outro.jpg"
DEFAULT_AUDIO_TRACK = ASSETS_DIR / "audio" / "tension.mp3"
FONTS_DIR = ASSETS_DIR / "fonts"

# Font resolution order: bundled brand fonts first, then common system fonts.
FONT_CANDIDATES = (
    FONTS_DIR / "Montserrat-Bold.ttf",
    FONTS_DIR / "headline.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
)


def jobs_dir():
    return Path(os.environ.get("KTT_JOBS_DIR", BASE_DIR / "jobs")).expanduser()


def brand_styles_path():
    return Path(os.environ.get("KTT_BRAND_STYLES", BRAND_STYLES_PATH)).expanduser()


def image_size_for_model(model):
    return IMAGE_SIZES.get(model, DEFAULT_IMAGE_SIZE)
