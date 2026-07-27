import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
CODE_DIR = PACKAGE_DIR.parent
BASE_DIR = CODE_DIR.parent
PROMPTS_DIR = PACKAGE_DIR / "prompts"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
FFMPEG_EXTRA_PARAMS = ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]

# The question is always first. All other roles are optional editorial tools.
ROLE_QUESTION = "question"
ROLE_DEFINITION = "definition"
ROLE_PURPOSE = "purpose"
ROLE_MECHANISM = "mechanism"
ROLE_COMPONENT = "component"
ROLE_EXAMPLE = "example"
ROLE_COMPARISON = "comparison"
ROLE_CONTEXT = "context"
ROLE_MISCONCEPTION = "misconception"
ROLE_SURPRISING_FACT = "surprising_fact"
VALID_ROLES = (
    ROLE_QUESTION,
    ROLE_DEFINITION,
    ROLE_PURPOSE,
    ROLE_MECHANISM,
    ROLE_COMPONENT,
    ROLE_EXAMPLE,
    ROLE_COMPARISON,
    ROLE_CONTEXT,
    ROLE_MISCONCEPTION,
    ROLE_SURPRISING_FACT,
)

DEFAULT_PARSE_MODEL = "gpt-5-mini"
DEFAULT_MIN_SLIDES = 5
DEFAULT_MAX_SLIDES = 6
MAX_WORDS_PER_HEADING = 8
MAX_WORDS_PER_EXPLANATION = 14

DEFAULT_IMAGE_MODEL = "gpt-image-1"
DEFAULT_VIBE = "educational_documentary"
IMAGE_CONCURRENCY = 3
IMAGE_RETRIES = 5
IMAGE_CONNECT_TIMEOUT = 30
IMAGE_READ_TIMEOUT = 300
IMAGE_SIZES = {
    "gpt-image-1": "1024x1536",
    "dall-e-3": "1024x1792",
}
DEFAULT_IMAGE_SIZE = "1024x1536"
IMAGE_TECHNICAL_RULES = (
    "Vertical 9:16 composition. Show one clear subject or one simple action only. "
    "Use very few objects, a plain uncluttered background, and generous calm "
    "negative space in the center for a solid black text box. Avoid complex "
    "diagrams, split screens, multiple panels, floating icons, arrows, equations, "
    "data graphics, and decorative details. Absolutely no text, words, letters, "
    "numbers, logos, labels, or watermarks."
)

DEFAULT_BACKDROP = "scrim_plate"
DEFAULT_BLUR_RADIUS = 3
DEFAULT_PLATE_OPACITY = 1.0
DEFAULT_SHOW_EXPLANATION = True
DEFAULT_SHOW_ROLE_KICKER = False
BRAND_SIGNATURE = "Know the Big Picture"

SAFE_MARGIN_X = 0.09
SAFE_MARGIN_TOP = 0.10
SAFE_MARGIN_BOTTOM = 0.16
SAFE_MARGIN_RIGHT = 0.12

DEFAULT_MIN_SECONDS = 30.0
DEFAULT_MAX_SECONDS = 60.0
TIMING_BASE_BEAT = 1.7
TIMING_PER_WORD = 0.24
TIMING_READING_FLOOR = 3.8
TIMING_FINAL_BONUS = 1.0
DEFAULT_OUTRO_DURATION = 3.5

DEFAULT_MOTION = 0.06
DEFAULT_TRANSITION = "cut"
DEFAULT_AUDIO_VOLUME = 0.25

ASSETS_DIR = BASE_DIR / "assets"
BRAND_STYLES_PATH = ASSETS_DIR / "brand" / "styles.json"
DEFAULT_OUTRO_IMAGE = ASSETS_DIR / "outro" / "outro.jpg"
DEFAULT_AUDIO_TRACK = ASSETS_DIR / "audio" / "tension.mp3"
FONTS_DIR = ASSETS_DIR / "fonts"
FONT_CANDIDATES = (
    FONTS_DIR / "Montserrat-Bold.ttf",
    FONTS_DIR / "headline.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
)


def jobs_dir():
    return Path(os.environ.get("KBP_JOBS_DIR", BASE_DIR / "jobs")).expanduser()


def brand_styles_path():
    return Path(os.environ.get("KBP_BRAND_STYLES", BRAND_STYLES_PATH)).expanduser()


def image_size_for_model(model):
    return IMAGE_SIZES.get(model, DEFAULT_IMAGE_SIZE)
