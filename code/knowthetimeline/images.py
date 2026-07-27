import base64
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image, ImageDraw

from .errors import KttError
from .job import image_settings
from .secrets import secret_value
from . import settings

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"


def load_vibe_prompt(job, vibe_name):
    path = settings.brand_styles_path()
    if not path.is_file():
        raise KttError(f"Brand style library not found: {path}")
    with path.open("r") as f:
        library = json.load(f)

    vibes = library.get("vibes", {})
    chosen = vibe_name or library.get("default_vibe") or settings.DEFAULT_VIBE
    if chosen not in vibes:
        available = ", ".join(sorted(vibes)) or "(none)"
        raise KttError(
            f"Unknown image vibe '{chosen}'. Available vibes: {available}"
        )
    return chosen, vibes[chosen]["prompt"]


def build_prompt(vibe_prompt, scene):
    return f"{vibe_prompt} {scene} {settings.IMAGE_TECHNICAL_RULES}"


def soften_scene(scene):
    return (
        "An abstract, symbolic, non-graphic interpretation representing the "
        f"subject of: {scene}. Mood and atmosphere over literal or graphic detail."
    )


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


def request_image(prompt, model, size, api_key):
    import requests

    payload = {"model": model, "prompt": prompt, "size": size, "n": 1}
    if not model.startswith("gpt-image"):
        payload["response_format"] = "b64_json"

    last_error = None
    for attempt in range(settings.IMAGE_RETRIES + 1):
        response = requests.post(
            OPENAI_IMAGES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
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
        raise KttError(
            f"OpenAI image request failed: HTTP {response.status_code}: {body}"
        )

    raise KttError(f"OpenAI image request failed after retries: {last_error}")


class PolicyRefusal(Exception):
    pass


def save_image_response(response_json, path):
    data = response_json.get("data", [])
    if not data:
        raise KttError("OpenAI image response contained no data")

    item = data[0]
    if item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    elif item.get("url"):
        import requests

        raw = requests.get(item["url"], timeout=120).content
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    else:
        raise KttError("OpenAI image response had neither b64_json nor url")

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=90)


def generate_node_background(node, job, vibe_prompt, model, size, api_key):
    node_id = node["id"]
    path = job.backgrounds_dir / f"{node_id}.jpg"
    if path.is_file():
        return {"id": node_id, "status": "cached"}

    scene = node.get("image_prompt")
    if not scene:
        make_neutral_background(path, size)
        return {"id": node_id, "status": "neutral_no_prompt"}

    # Fallback ladder: full prompt -> softened prompt -> neutral background.
    try:
        result = request_image(build_prompt(vibe_prompt, scene), model, size, api_key)
        save_image_response(result, path)
        return {"id": node_id, "status": "generated"}
    except PolicyRefusal:
        pass

    try:
        softened = build_prompt(vibe_prompt, soften_scene(scene))
        result = request_image(softened, model, size, api_key)
        save_image_response(result, path)
        return {"id": node_id, "status": "generated_softened"}
    except PolicyRefusal:
        make_neutral_background(path, size)
        return {"id": node_id, "status": "neutral_fallback"}


def run_images(job, timeline):
    """Stage 3: generate one 9:16 background per node, in parallel, with cache."""
    cfg = image_settings(job)
    vibe_name, vibe_prompt = load_vibe_prompt(job, cfg["vibe"])
    api_key = secret_value("OPENAI_API_KEY", required=True)
    model = cfg["model"]
    size = cfg["size"]

    job.backgrounds_dir.mkdir(parents=True, exist_ok=True)
    nodes = timeline.get("nodes", [])
    print(f"Generating backgrounds: model={model}, vibe={vibe_name}, size={size}")

    results = []
    with ThreadPoolExecutor(max_workers=settings.IMAGE_CONCURRENCY) as pool:
        futures = {
            pool.submit(
                generate_node_background, node, job, vibe_prompt, model, size, api_key
            ): node["id"]
            for node in nodes
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"  node {result['id']}: {result['status']}")

    return sorted(results, key=lambda r: r["id"])
