import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
CODE_DIR = PACKAGE_DIR.parent
BASE_DIR = CODE_DIR.parent
PROMPTS_DIR = PACKAGE_DIR / "prompts"
FORMAT_PROMPTS_DIR = PROMPTS_DIR / "formats"

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
ROLE_TYPE = "type"
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
    ROLE_TYPE,
)

FORMAT_WHY = "why"
FORMAT_HOW = "how"
FORMAT_TYPES = "types"
FORMAT_COMPARISON = "comparison"
FORMAT_WHAT_IS_IT = "what_is_it"
FORMAT_MYTH_VS_FACT = "myth_vs_fact"
VALID_CONTENT_FORMATS = (
    FORMAT_WHY,
    FORMAT_HOW,
    FORMAT_TYPES,
    FORMAT_COMPARISON,
    FORMAT_WHAT_IS_IT,
    FORMAT_MYTH_VS_FACT,
)
DEFAULT_CONTENT_FORMAT = FORMAT_WHY
DEFAULT_TYPES_ITEM_COUNT = 5
MIN_TYPES_ITEM_COUNT = 4
MAX_TYPES_ITEM_COUNT = 12

# Script/explainer text generation. Gemini is the default provider; OpenAI is
# an explicit opt-in (set provider to "openai"), never an automatic fallback.
DEFAULT_LLM_PROVIDER = "gemini"
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
DEFAULT_LLM_TEMPERATURE = 0.7
VALID_LLM_PROVIDERS = ("gemini", "openai")


def gemini_supports_temperature(model):
    """Gemini 3.x manages its own sampling; temperature/top_p/top_k are
    deprecated and will error in future model generations. Only send
    temperature to pre-3.x Gemini models."""
    name = (model or "").lower()
    for major in ("gemini-3", "gemini-4", "gemini-5"):
        if name.startswith(major):
            return False
    return True

DEFAULT_PARSE_MODEL = "gpt-5-mini"
DEFAULT_MIN_SLIDES = 5
DEFAULT_MAX_SLIDES = 6
MAX_WORDS_PER_HEADING = 8
MAX_WORDS_PER_EXPLANATION = 12

DEFAULT_IMAGE_PROVIDER = "openai"
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_IMAGE_ASPECT_RATIO = "9:16"
DEFAULT_IMAGE_MODEL = "gpt-image-1-mini"
DEFAULT_IMAGE_QUALITY = "low"
DEFAULT_VIBE = "educational_documentary"
IMAGE_CONCURRENCY = 3
IMAGE_RETRIES = 0
IMAGE_CONNECT_TIMEOUT = 30
IMAGE_READ_TIMEOUT = 300
IMAGE_SIZES = {
    "gpt-image-1": "1024x1536",
    "dall-e-3": "1024x1792",
}
DEFAULT_IMAGE_SIZE = "1024x1536"
IMAGE_TECHNICAL_RULES = (
    "STRICT REQUIREMENT: the image itself must contain zero writing and zero "
    "text-like marks. No words, letters, numbers, typography, captions, labels, "
    "logos, brands, watermarks, signatures, symbols that resemble writing, or "
    "invented pseudo-text anywhere. Do not include signs, labeled packaging, "
    "book or newspaper pages, screens with interfaces, license plates, clothing "
    "graphics, charts, maps, or documents. Vertical 9:16 composition. Create one "
    "clear subject or one simple action with physically coherent shapes, realistic "
    "materials, clean edges, natural proportions, controlled lighting, and premium "
    "editorial-photography quality. Use very few objects and a simple uncluttered "
    "setting. Leave the central area naturally calm and unobstructed; do not draw "
    "a text box or placeholder. Avoid diagrams, split screens, multiple panels, "
    "floating icons, arrows, equations, data graphics, borders, and decorative "
    "clutter. Final reminder: render absolutely no text or text-like detail."
)

DEFAULT_BACKDROP = "scrim_plate"
DEFAULT_BLUR_RADIUS = 3
DEFAULT_PLATE_OPACITY = 1.0
DEFAULT_SHOW_EXPLANATION = True
DEFAULT_SHOW_ROLE_KICKER = False
BRAND_SIGNATURE = "Know the Big Picture"
# Channel handle shown on the outro card.
CHANNEL_HANDLE = "@knowthebigpicture"
# On-screen call-to-action lines for the outro card (mirrors the spoken CTA).
OUTRO_CARD_HOOK = "Enjoyed this?"
OUTRO_CARD_CTA = "Like & Subscribe"
OUTRO_CARD_SUBLINE = "You won't want to miss tomorrow's question."

SAFE_MARGIN_X = 0.09
SAFE_MARGIN_TOP = 0.10
SAFE_MARGIN_BOTTOM = 0.16
SAFE_MARGIN_RIGHT = 0.12

DEFAULT_MIN_SECONDS = 30.0
DEFAULT_MAX_SECONDS = 75.0
TIMING_BASE_BEAT = 1.7
TIMING_PER_WORD = 0.24
TIMING_READING_FLOOR = 3.8
TIMING_FINAL_BONUS = 1.0
DEFAULT_OUTRO_DURATION = 3.5
# Spoken call-to-action over the outro card. Set to "" (or override
# video.voiceover.outro_narration in job.json) to leave the outro silent.
DEFAULT_OUTRO_NARRATION = (
      "Enjoyed this? Give it a like, and subscribe—you won't want to miss tomorrow's question."
)

# Format-aware reading rhythm. Durations remain dynamic by combined heading and
# explanation word count, with bounds that protect legibility and pacing.
TIMING_PROFILES = {
    FORMAT_WHY: {"base": 2.2, "per_word": 0.30, "min": 4.0, "max": 8.0},
    FORMAT_HOW: {"base": 2.0, "per_word": 0.28, "min": 4.0, "max": 7.0},
    FORMAT_TYPES: {"base": 1.8, "per_word": 0.26, "min": 3.5, "max": 5.5},
    FORMAT_COMPARISON: {"base": 2.2, "per_word": 0.30, "min": 4.0, "max": 7.0},
    FORMAT_WHAT_IS_IT: {"base": 2.2, "per_word": 0.30, "min": 4.0, "max": 8.0},
    FORMAT_MYTH_VS_FACT: {"base": 2.2, "per_word": 0.30, "min": 4.0, "max": 8.0},
}
TITLE_TIMING_PROFILE = {"base": 3.5, "per_word": 0.15, "min": 3.5, "max": 5.0}
MYTH_VERDICT_BONUS = 0.5

DEFAULT_MOTION = 0.06
DEFAULT_TRANSITION = "cut"
DEFAULT_AUDIO_VOLUME = 0.25

# Voice-over (narration). Default on; flip video.voiceover.enabled to false in
# job.json to fall back to today's silent-slides + looped-music behavior.
DEFAULT_VOICEOVER_ENABLED = True
DEFAULT_TTS_ENGINE = "edge"
DEFAULT_TTS_VOICE = "en-US-AndrewNeural"
DEFAULT_TTS_RATE = "+0%"
# Background music volume while narration plays (ducked well below the
# music-only DEFAULT_AUDIO_VOLUME above).
DEFAULT_VOICEOVER_MUSIC_VOLUME = 0.10
# Silence padding, in seconds, around each slide's spoken line.
NARRATION_LEAD_IN = 0.35
NARRATION_TAIL_PAD = 0.6
NARRATION_LEAD_IN_FLOOR = 0.15
NARRATION_TAIL_PAD_FLOOR = 0.25
# When narration cannot fit max_seconds, speed speech up (pitch-preserving)
# by at most this factor before falling back to a small tolerance.
ATEMPO_MAX = 1.15
# Allow the finished plan to run up to this many seconds over max_seconds
# rather than cutting a spoken line mid-sentence.
OVERFLOW_TOLERANCE = 3.0
# What to do if speech synthesis fails: "music" (silent slides + music) or
# "fail_job".
DEFAULT_ON_TTS_FAIL = "music"

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
