import json
import os
import re
import time
from pathlib import Path

from .errors import KttError
from .remote import (
    rclone_bin_from_env,
    rclone_copy_file,
    rclone_public_link,
    remote_join,
    remote_root_from_env,
)
from .secrets import secret_value
from .status import utc_now
from .youtube import load_youtube_metadata


UPLOAD_RESULT_FILE = "instagram_upload.json"
FACEBOOK_GRAPH_BASE = "https://graph.facebook.com"
INSTAGRAM_GRAPH_BASE = "https://graph.instagram.com"
DEFAULT_GRAPH_VERSION = "v21.0"

MAX_CAPTION_LENGTH = 2200
MAX_HASHTAGS = 30

# Container processing can lag behind the API response; poll until FINISHED.
POLL_INTERVAL_SECONDS = 5.0
POLL_TIMEOUT_SECONDS = 300.0

# Instagram has no "draft"/"private" publish status like YouTube. The safe
# default builds and validates the media container but stops before it goes
# live; "live" performs the final media_publish call.
PUBLISH_MODE_CONTAINER_ONLY = "container_only"
PUBLISH_MODE_LIVE = "live"


def upload_result_path(job):
    return job.outputs_dir / UPLOAD_RESULT_FILE


def read_json(path, label):
    try:
        with Path(path).open("r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise KttError(f"Invalid {label}: {path}: {e}") from e


def graph_version():
    return os.environ.get("IG_GRAPH_VERSION") or DEFAULT_GRAPH_VERSION


def graph_base(token):
    # "Instagram API with Instagram Login" tokens start with "IG" and must use
    # graph.instagram.com. Facebook-login tokens start with "EAA" and use
    # graph.facebook.com.
    return INSTAGRAM_GRAPH_BASE if token.startswith("IG") else FACEBOOK_GRAPH_BASE


def graph_url(base, *parts):
    suffix = "/".join(str(part).strip("/") for part in parts if str(part).strip("/"))
    return f"{base}/{graph_version()}/{suffix}"


def resolve_ig_user_id(base, token, configured):
    if configured and str(configured).strip().isdigit():
        return str(configured).strip()

    # Instagram-login tokens can resolve their own numeric id from /me.
    if base == INSTAGRAM_GRAPH_BASE:
        payload = _get(
            graph_url(base, "me"),
            {"fields": "user_id,username", "access_token": token},
        )
        uid = payload.get("user_id") or payload.get("id")
        if uid:
            return str(uid)

    raise KttError(
        "INSTAGRAM_USER_ID must be the numeric Instagram account id "
        f"(got {configured!r}). For Facebook-login tokens use the IG Business "
        "account id; for Instagram-login tokens it can be auto-resolved."
    )


def validate_instagram_config(job):
    instagram = job.section("instagram")
    if not instagram.get("enabled", False):
        raise KttError("instagram.enabled must be true to publish")

    mode = instagram.get("publish_mode", PUBLISH_MODE_CONTAINER_ONLY)
    if mode not in (PUBLISH_MODE_CONTAINER_ONLY, PUBLISH_MODE_LIVE):
        raise KttError(
            "instagram.publish_mode must be 'container_only' or 'live', "
            f"got {mode!r}"
        )
    return instagram


def hashtag_from_tag(tag):
    cleaned = re.sub(r"[^0-9A-Za-z]+", "", tag)
    return f"#{cleaned}" if cleaned else ""


def build_hashtags(instagram, tags):
    override = instagram.get("hashtags")
    if isinstance(override, list) and override:
        raw = override
    else:
        raw = tags or []

    hashtags = []
    seen = set()
    for tag in raw:
        if not isinstance(tag, str):
            continue
        tag = tag.strip()
        if not tag:
            continue
        token = tag if tag.startswith("#") else hashtag_from_tag(tag)
        key = token.lower()
        if token and key not in seen:
            seen.add(key)
            hashtags.append(token)
        if len(hashtags) >= MAX_HASHTAGS:
            break
    return hashtags


def build_caption(job):
    instagram = job.section("instagram")
    override = instagram.get("caption")
    if isinstance(override, str) and override.strip():
        return override.strip()[:MAX_CAPTION_LENGTH]

    metadata = load_youtube_metadata(job)
    blocks = [metadata["title"].strip()]

    body = "\n".join(line for line in metadata["description"] if line).strip()
    if body:
        blocks.append(body)

    hashtags = build_hashtags(instagram, metadata.get("tags"))
    if hashtags:
        blocks.append(" ".join(hashtags))

    caption = "\n\n".join(block for block in blocks if block)
    return caption[:MAX_CAPTION_LENGTH]


def extract_drive_file_id(link):
    match = re.search(r"/d/([A-Za-z0-9_-]{20,})", link)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([A-Za-z0-9_-]{20,})", link)
    if match:
        return match.group(1)
    return None


def drive_direct_url(file_id):
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def resolve_video_url(job, remote_root=None, rclone_bin=None):
    instagram = job.section("instagram")
    override = instagram.get("video_url")
    if isinstance(override, str) and override.strip():
        return override.strip()

    remote_root = remote_root or remote_root_from_env()
    if not remote_root:
        raise KttError(
            "Instagram publish needs a public video URL. Set instagram.video_url "
            "in job.json, or run with --remote (KTT_REMOTE_ROOT) so the video is "
            "on Drive and a public link can be generated."
        )

    rclone_bin = rclone_bin or rclone_bin_from_env()
    remote_path = remote_join(remote_root, "jobs", job.job_id, "outputs", "timeline.mp4")

    # Ensure the freshly rendered video is on Drive before linking it. The main
    # run pushes the job folder only after publishing, so upload the single file
    # here to make both the integrated run and standalone publish robust.
    if job.video_path.is_file():
        rclone_copy_file(rclone_bin, job.video_path, remote_path)

    link = rclone_public_link(rclone_bin, remote_path)

    file_id = extract_drive_file_id(link)
    if not file_id:
        raise KttError(
            f"Could not extract a Drive file id from rclone link output: {link!r}"
        )
    return drive_direct_url(file_id)


def _post(url, data):
    import requests

    response = requests.post(url, data=data, timeout=120)
    if response.status_code >= 400:
        raise KttError(
            f"Instagram Graph API POST {url} failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )
    return response.json()


def _get(url, params):
    import requests

    response = requests.get(url, params=params, timeout=60)
    if response.status_code >= 400:
        raise KttError(
            f"Instagram Graph API GET {url} failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )
    return response.json()


def create_reel_container(base, ig_user_id, video_url, caption, token):
    payload = _post(
        graph_url(base, ig_user_id, "media"),
        {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        },
    )
    creation_id = payload.get("id")
    if not creation_id:
        raise KttError("Instagram media container response did not include an id")
    return creation_id


def poll_container(base, creation_id, token):
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    last_status = None
    while time.monotonic() < deadline:
        payload = _get(
            graph_url(base, creation_id),
            {"fields": "status_code,status", "access_token": token},
        )
        status_code = payload.get("status_code")
        last_status = payload.get("status") or status_code
        if status_code == "FINISHED":
            return
        if status_code in ("ERROR", "EXPIRED"):
            raise KttError(
                f"Instagram media container failed: status={last_status!r}"
            )
        print(f"  container status: {status_code} (waiting)")
        time.sleep(POLL_INTERVAL_SECONDS)

    raise KttError(
        f"Instagram media container not ready after {POLL_TIMEOUT_SECONDS:.0f}s "
        f"(last status={last_status!r})"
    )


def publish_container(base, ig_user_id, creation_id, token):
    payload = _post(
        graph_url(base, ig_user_id, "media_publish"),
        {"creation_id": creation_id, "access_token": token},
    )
    media_id = payload.get("id")
    if not media_id:
        raise KttError("Instagram media_publish response did not include an id")
    return media_id


def fetch_permalink(base, media_id, token):
    try:
        payload = _get(
            graph_url(base, media_id),
            {"fields": "permalink", "access_token": token},
        )
        return payload.get("permalink")
    except KttError:
        return None


def write_result(job, result):
    result_path = upload_result_path(job)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with result_path.open("w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    return result_path


def publish_reel(job, remote_root=None, rclone_bin=None, force=False):
    result_path = upload_result_path(job)
    if result_path.is_file() and not force:
        existing = read_json(result_path, "Instagram upload result")
        print(f"SKIP Instagram publish already exists: {result_path}")
        if existing.get("permalink"):
            print(f"Instagram: {existing['permalink']}")
        return result_path

    instagram = validate_instagram_config(job)
    mode = instagram.get("publish_mode", PUBLISH_MODE_CONTAINER_ONLY)

    token = secret_value("INSTAGRAM_ACCESS_TOKEN", required=True).strip()
    configured_id = secret_value("INSTAGRAM_USER_ID")
    base = graph_base(token)
    ig_user_id = resolve_ig_user_id(base, token, configured_id)

    caption = build_caption(job)
    video_url = resolve_video_url(job, remote_root=remote_root, rclone_bin=rclone_bin)

    print("Publishing Instagram Reel")
    print(f"Mode: {mode}")
    print(f"Graph host: {base}")
    print(f"IG user id: {ig_user_id}")
    print(f"Video URL: {video_url}")
    print(f"Caption:\n{caption}")

    creation_id = create_reel_container(base, ig_user_id, video_url, caption, token)
    print(f"Container created: {creation_id}")
    poll_container(base, creation_id, token)
    print("Container ready (FINISHED)")

    result = {
        "created_at": utc_now(),
        "publish_mode": mode,
        "container_id": creation_id,
        "caption": caption,
        "video_url": video_url,
    }

    if mode == PUBLISH_MODE_LIVE:
        media_id = publish_container(base, ig_user_id, creation_id, token)
        permalink = fetch_permalink(base, media_id, token)
        result.update(
            {
                "status": "published",
                "media_id": media_id,
                "permalink": permalink,
                "published_at": utc_now(),
            }
        )
        result_path = write_result(job, result)
        print(f"Instagram publish saved: {result_path}")
        print(f"Instagram Reel: {permalink or media_id}")
        return result_path

    result["status"] = "container_ready"
    result["note"] = (
        "Draft/safe mode: media container created but not published. "
        "Instagram containers expire ~24h after creation. Set "
        "instagram.publish_mode to 'live' to publish."
    )
    result_path = write_result(job, result)
    print(f"Instagram container saved (not published): {result_path}")
    print("Draft mode: nothing was published to Instagram.")
    return result_path
