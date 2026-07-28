import json
import mimetypes
from pathlib import Path

from .errors import KtwError
from .metadata import validate_metadata
from .secrets import secret_value
from .status import utc_now


UPLOAD_RESULT_FILE = "youtube_upload.json"
METADATA_FILE = "youtube_metadata.json"
SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
MAX_SHORTS_DURATION = 65.0
YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def upload_result_path(job):
    return job.outputs_dir / UPLOAD_RESULT_FILE


def read_json(path, label):
    try:
        with Path(path).open("r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise KtwError(f"Invalid {label}: {path}: {e}") from e


def load_youtube_metadata(job):
    if job.metadata_path.is_file():
        payload = read_json(job.metadata_path, "YouTube metadata JSON")
        return validate_metadata(payload)

    youtube = job.section("youtube")
    return validate_metadata(
        {
            "title": youtube.get("title"),
            "description": youtube.get("description"),
            "tags": youtube.get("tags"),
        }
    )


def description_text(lines):
    return "\n".join(lines)


def validate_youtube_config(job):
    youtube = job.section("youtube")
    if not youtube.get("enabled", False):
        raise KtwError("youtube.enabled must be true to publish")

    if youtube.get("upload_type", "short") != "short":
        raise KtwError("youtube.upload_type must be 'short'")

    privacy_status = youtube.get("privacy_status", "private")
    if privacy_status not in {"private", "public"}:
        raise KtwError("youtube.privacy_status must be 'private' or 'public'")

    return youtube


def validate_short_video(video_path):
    from moviepy import VideoFileClip

    path = Path(video_path)
    if not path.is_file():
        raise KtwError(f"Video file not found: {path}")
    if path.suffix.lower() != ".mp4":
        raise KtwError(f"YouTube Shorts upload requires an mp4 file: {path}")

    clip = VideoFileClip(str(path))
    try:
        width, height = clip.size
        duration = float(clip.duration or 0)
    finally:
        clip.close()

    if (width, height) != (SHORTS_WIDTH, SHORTS_HEIGHT):
        raise KtwError(
            f"YouTube Shorts upload requires 1080x1920 video. Found {width}x{height}."
        )
    if duration <= 0:
        raise KtwError("YouTube Shorts upload requires a valid video duration")
    if duration > MAX_SHORTS_DURATION:
        raise KtwError(
            f"YouTube Shorts upload requires duration <= {MAX_SHORTS_DURATION:.0f}s. "
            f"Found {duration:.1f}s."
        )

    return {"width": width, "height": height, "duration": duration}


def access_token():
    import requests

    response = requests.post(
        YOUTUBE_TOKEN_URL,
        data={
            "client_id": secret_value("YOUTUBE_CLIENT_ID", required=True),
            "client_secret": secret_value("YOUTUBE_CLIENT_SECRET", required=True),
            "refresh_token": secret_value("YOUTUBE_REFRESH_TOKEN", required=True),
            "grant_type": "refresh_token",
        },
        timeout=60,
    )

    if response.status_code >= 400:
        raise KtwError(
            f"YouTube OAuth token request failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    token = response.json().get("access_token")
    if not token:
        raise KtwError("YouTube OAuth response did not include access_token")
    return token


def initiate_upload(video_path, metadata, youtube, token):
    import requests

    mime_type = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
    file_size = Path(video_path).stat().st_size
    body = {
        "snippet": {
            "title": metadata["title"],
            "description": description_text(metadata["description"]),
            "tags": metadata["tags"],
            "categoryId": str(youtube.get("category_id", "25")),
        },
        "status": {
            "privacyStatus": youtube.get("privacy_status", "private"),
            "selfDeclaredMadeForKids": bool(youtube.get("made_for_kids", False)),
            "containsSyntheticMedia": bool(
                youtube.get("contains_synthetic_media", True)
            ),
        },
    }

    response = requests.post(
        YOUTUBE_UPLOAD_URL,
        params={
            "uploadType": "resumable",
            "part": "snippet,status",
            "notifySubscribers": "false",
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(file_size),
            "X-Upload-Content-Type": mime_type,
        },
        json=body,
        timeout=60,
    )

    if response.status_code >= 400:
        raise KtwError(
            f"YouTube upload session failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    upload_url = response.headers.get("Location")
    if not upload_url:
        raise KtwError("YouTube upload session response did not include Location")

    return upload_url, mime_type


def upload_video_file(upload_url, video_path, token, mime_type):
    import requests

    path = Path(video_path)
    with path.open("rb") as f:
        response = requests.put(
            upload_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": mime_type,
                "Content-Length": str(path.stat().st_size),
            },
            data=f,
            timeout=600,
        )

    if response.status_code not in (200, 201):
        raise KtwError(
            f"YouTube video upload failed: HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return response.json()


def publish_short(job, force=False):
    result_path = upload_result_path(job)
    if result_path.is_file() and not force:
        existing = read_json(result_path, "YouTube upload result")
        video_id = existing.get("video_id")
        print(f"SKIP YouTube upload already exists: {result_path}")
        if video_id:
            print(f"YouTube Short: https://www.youtube.com/shorts/{video_id}")
        return result_path

    youtube = validate_youtube_config(job)
    video_path = job.video_path
    video_info = validate_short_video(video_path)
    metadata = load_youtube_metadata(job)

    print("Uploading YouTube Short")
    print(f"Video: {video_path}")
    print(f"Duration: {video_info['duration']:.1f}s")
    print(f"Title: {metadata['title']}")

    token = access_token()
    upload_url, mime_type = initiate_upload(video_path, metadata, youtube, token)
    response = upload_video_file(upload_url, video_path, token, mime_type)

    video_id = response.get("id")
    if not video_id:
        raise KtwError("YouTube upload response did not include video id")

    result = {
        "uploaded_at": utc_now(),
        "upload_type": "short",
        "privacy_status": youtube.get("privacy_status", "private"),
        "video_id": video_id,
        "shorts_url": f"https://www.youtube.com/shorts/{video_id}",
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        "title": metadata["title"],
        "video": video_info,
        "api_response": response,
    }

    result_path.parent.mkdir(parents=True, exist_ok=True)
    with result_path.open("w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    print(f"YouTube upload saved: {result_path}")
    print(f"YouTube Short: {result['shorts_url']}")
    return result_path
