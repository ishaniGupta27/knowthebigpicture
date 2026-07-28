import base64
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image, ImageDraw, ImageStat, UnidentifiedImageError

from .errors import KtwError
from .job import image_settings
from .secrets import secret_value
from . import settings

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"


def load_vibe_prompt(job, vibe_name):
    path = settings.brand_styles_path()
    if not path.is_file():
        raise KtwError(f"Brand style library not found: {path}")
    with path.open("r") as f:
        library = json.load(f)

    vibes = library.get("vibes", {})
    chosen = vibe_name or library.get("default_vibe") or settings.DEFAULT_VIBE
    if chosen not in vibes:
        available = ", ".join(sorted(vibes)) or "(none)"
        raise KtwError(
            f"Unknown image vibe '{chosen}'. Available vibes: {available}"
        )
    return chosen, vibes[chosen]["prompt"]


def build_prompt(vibe_prompt, scene):
    return f"{vibe_prompt} {scene} {settings.IMAGE_TECHNICAL_RULES}"


def parse_size(size):
    try:
        w, h = (int(part) for part in size.lower().split("x"))
        return w, h
    except Exception:
        return 1024, 1536


def make_neutral_background(path, size):
    w, h = parse_size(size)
    image = Image.new("RGB", (w, h), (18, 20, 24))
    draw = ImageDraw.Draw(image)
    for y in range(h):
        shade = int(10 + 26 * (y / h))
        draw.line([(0, y), (w, y)], fill=(shade, shade + 2, shade + 6))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=88)


def is_policy_refusal(status_code, body_text):
    if status_code != 400:
        return False
    lowered = body_text.lower()
    return any(
        marker in lowered
        for marker in ("content_policy", "safety", "moderation", "rejected")
    )


def retry_wait_seconds(response, body, attempt):
    """How long to wait before retrying, honoring what OpenAI tells us."""
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    # Rate-limit errors include e.g. "Please try again in 12s" / "in 1.5s".
    match = re.search(r"try again in ([0-9.]+)\s*(ms|s)?", body, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        if (match.group(2) or "s").lower() == "ms":
            value /= 1000.0
        return value
    # Fall back to exponential backoff for 5xx / unlabeled 429s.
    return 2.0 * (attempt + 1)


def request_image(prompt, model, size, quality, api_key):
    import requests

    payload = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if model.startswith("gpt-image"):
        payload["quality"] = quality
    else:
        payload["response_format"] = "b64_json"

    last_error = None
    for attempt in range(settings.IMAGE_RETRIES + 1):
        try:
            response = requests.post(
                OPENAI_IMAGES_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=(
                    settings.IMAGE_CONNECT_TIMEOUT,
                    settings.IMAGE_READ_TIMEOUT,
                ),
            )
        except requests.exceptions.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < settings.IMAGE_RETRIES:
                wait = 2.0 * (attempt + 1)
                print(
                    f"  image request timed out/failed; retrying in {wait:.0f}s "
                    f"({attempt + 1}/{settings.IMAGE_RETRIES})"
                )
                time.sleep(wait)
                continue
            break

        if response.status_code < 400:
            return response.json()

        body = response.text[:500]
        if is_policy_refusal(response.status_code, body):
            raise PolicyRefusal(body)
        if response.status_code in (429, 500, 502, 503, 504):
            last_error = body
            if attempt < settings.IMAGE_RETRIES:
                wait = retry_wait_seconds(response, body, attempt) + 1.0
                print(f"  rate limited/transient error; retrying in {wait:.0f}s")
                time.sleep(wait)
            continue
        raise KtwError(
            f"OpenAI image request failed: HTTP {response.status_code}: {body}"
        )

    raise KtwError(f"OpenAI image request failed after retries: {last_error}")


class PolicyRefusal(Exception):
    pass


class InvalidGeneratedImage(KtwError):
    pass


def validate_generated_image(image):
    width, height = image.size
    if width < 256 or height < 256:
        raise InvalidGeneratedImage(
            f"generated image dimensions are unusable: {width}x{height}"
        )

    sample = image.convert("L")
    sample.thumbnail((64, 64))
    statistics = ImageStat.Stat(sample)
    mean = statistics.mean[0]
    deviation = statistics.stddev[0]
    if mean < 8:
        raise InvalidGeneratedImage("generated image is effectively black")
    if mean > 247:
        raise InvalidGeneratedImage("generated image is effectively blank white")
    if deviation < 2:
        raise InvalidGeneratedImage("generated image has no usable visual detail")


def decode_image_response(response_json):
    data = response_json.get("data", [])
    if not data:
        raise InvalidGeneratedImage("OpenAI image response contained no data")

    item = data[0]
    try:
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        elif item.get("url"):
            import requests

            response = requests.get(item["url"], timeout=120)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
        else:
            raise InvalidGeneratedImage(
                "OpenAI image response had neither b64_json nor url"
            )
    except (ValueError, OSError, UnidentifiedImageError) as exc:
        raise InvalidGeneratedImage(
            f"OpenAI returned an unreadable image: {exc}"
        ) from exc

    validate_generated_image(image)
    return image


def save_image_response(response_json, path):
    image = decode_image_response(response_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95, subsampling=0)


def save_pil_image(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95, subsampling=0)


def request_image_gemini(prompt, model, aspect_ratio, api_key):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                try:
                    return Image.open(io.BytesIO(inline.data)).convert("RGB")
                except (ValueError, OSError, UnidentifiedImageError) as exc:
                    raise InvalidGeneratedImage(
                        f"Gemini returned an unreadable image: {exc}"
                    ) from exc
    # No image returned: distinguish a safety block from an empty response.
    for candidate in candidates:
        reason = str(getattr(candidate, "finish_reason", "") or "").upper()
        if any(marker in reason for marker in ("SAFETY", "PROHIBITED", "BLOCK")):
            raise PolicyRefusal(f"Gemini blocked image ({reason})")
    feedback = getattr(response, "prompt_feedback", None)
    if feedback is not None and getattr(feedback, "block_reason", None):
        raise PolicyRefusal(f"Gemini blocked prompt ({feedback.block_reason})")
    raise InvalidGeneratedImage("Gemini image response contained no image")


def _provider_image(provider, prompt, cfg):
    """Return a validated PIL image from the configured provider, or raise.

    Gemini is the default. There is no automatic cross-provider fallback: set
    images.provider to "openai" explicitly to use OpenAI.
    """
    if provider == "gemini":
        api_key = secret_value("GEMINI_API_KEY") or secret_value("GOOGLE_API_KEY")
        if not api_key:
            raise KtwError("GEMINI_API_KEY is not set")
        model = secret_value("GEMINI_IMAGE_MODEL") or cfg["gemini_model"]
        image = request_image_gemini(prompt, model, cfg["aspect_ratio"], api_key)
        validate_generated_image(image)
        return image
    if provider == "openai":
        api_key = secret_value("OPENAI_API_KEY", required=True)
        result = request_image(prompt, cfg["model"], cfg["size"], cfg["quality"], api_key)
        return decode_image_response(result)
    raise KtwError(f"Unknown image provider: {provider}")


def generate_node_background(node, job, vibe_prompt, cfg, force=False):
    node_id = node["id"]
    path = job.backgrounds_dir / f"{node_id}.jpg"
    if path.is_file() and not force:
        return {"id": node_id, "status": "cached"}

    scene = node.get("image_prompt")
    if not scene:
        make_neutral_background(path, cfg["size"])
        return {"id": node_id, "status": "neutral_no_prompt"}

    prompt = build_prompt(vibe_prompt, scene)
    provider = cfg["provider"]
    for attempt in range(2):
        try:
            image = _provider_image(provider, prompt, cfg)
            save_pil_image(image, path)
            status = "generated" if attempt == 0 else "generated_after_invalid_retry"
            return {"id": node_id, "status": status}
        except PolicyRefusal:
            make_neutral_background(path, cfg["size"])
            return {"id": node_id, "status": "neutral_fallback"}
        except InvalidGeneratedImage as exc:
            if attempt == 0:
                print(
                    f"  node {node_id}: unusable image ({exc}); "
                    "making one replacement request"
                )
                continue
            print(
                f"  node {node_id}: replacement image also unusable ({exc}); "
                "using local neutral background"
            )
            make_neutral_background(path, cfg["size"])
            return {"id": node_id, "status": "neutral_after_invalid_retry"}

    raise InvalidGeneratedImage("image generation ended without a usable result")


def run_images(job, explainer, force=False):
    """Stage 3: generate one 9:16 educational background per slide."""
    cfg = image_settings(job)
    vibe_name, vibe_prompt = load_vibe_prompt(job, cfg["vibe"])

    job.backgrounds_dir.mkdir(parents=True, exist_ok=True)
    nodes = explainer.get("slides", [])
    if cfg["provider"] == "gemini":
        model_desc = f"model={cfg['gemini_model']}, aspect_ratio={cfg['aspect_ratio']}"
    else:
        model_desc = f"model={cfg['model']}, size={cfg['size']}, quality={cfg['quality']}"
    print(
        "Generating backgrounds: "
        f"provider={cfg['provider']}, {model_desc}, vibe={vibe_name}"
    )

    results = []
    with ThreadPoolExecutor(max_workers=settings.IMAGE_CONCURRENCY) as pool:
        futures = {
            pool.submit(
                generate_node_background, node, job, vibe_prompt, cfg, force
            ): node["id"]
            for node in nodes
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"  node {result['id']}: {result['status']}")

    return sorted(results, key=lambda r: r["id"])
