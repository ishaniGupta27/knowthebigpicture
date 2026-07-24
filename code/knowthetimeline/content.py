import json


def build_content(timeline):
    """Flatten a verified timeline into a review-friendly content payload."""
    story = timeline.get("story", {})
    slides = []
    for node in timeline.get("nodes", []):
        slides.append(
            {
                "id": node.get("id"),
                "role": node.get("role"),
                "date": node.get("event_date_display"),
                "headline": node.get("headline"),
                "detail": node.get("detail"),
                "subtitle": node.get("subtitle"),
                "source_quote": node.get("source_quote"),
            }
        )

    return {
        "story": story,
        "central_question": story.get("central_question"),
        "verification": timeline.get("verification_summary", {}).get("status"),
        "slide_count": len(slides),
        "slides": slides,
    }


def write_content(job, timeline):
    """Stage: write content.json (text-only, no images) for lite runs."""
    payload = build_content(timeline)

    job.content_path.parent.mkdir(parents=True, exist_ok=True)
    with job.content_path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    print(f"Content written: {job.content_path}")
    print(f"Slides: {payload['slide_count']}")
    for slide in payload["slides"]:
        date = f"[{slide['date']}] " if slide["date"] else ""
        print(f"  {slide['id']} {slide['role']}: {date}{slide['headline']}")
        if slide["detail"]:
            print(f"       - {slide['detail']}")
    return job.content_path
