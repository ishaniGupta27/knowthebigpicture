from .errors import KttError

MAX_TITLE_LENGTH = 100
MAX_TAGS_JOINED_LENGTH = 500


def validate_metadata(payload):
    if not isinstance(payload, dict):
        raise KttError("YouTube metadata must be an object")

    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise KttError("YouTube metadata.title must be a non-empty string")
    if len(title) > MAX_TITLE_LENGTH:
        raise KttError(
            f"YouTube metadata.title must be <= {MAX_TITLE_LENGTH} characters"
        )

    description = payload.get("description")
    if isinstance(description, str):
        description = [description]
    if not isinstance(description, list) or not all(
        isinstance(line, str) for line in description
    ):
        raise KttError("YouTube metadata.description must be a string or list of strings")

    tags = payload.get("tags") or []
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise KttError("YouTube metadata.tags must be a list of strings")
    if sum(len(tag) for tag in tags) > MAX_TAGS_JOINED_LENGTH:
        raise KttError(
            f"YouTube metadata.tags joined length must be <= {MAX_TAGS_JOINED_LENGTH}"
        )

    return {"title": title.strip(), "description": description, "tags": tags}
