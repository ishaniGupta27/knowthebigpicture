import json


def build_content(explainer):
    return {
        "explainer": explainer.get("explainer", {}),
        "verification": explainer.get("verification_summary", {}).get("status"),
        "slide_count": len(explainer.get("slides", [])),
        "slides": [
            {
                "id": slide.get("id"),
                "role": slide.get("role"),
                "heading": slide.get("heading"),
                "explanation": slide.get("explanation"),
                "source_quotes": slide.get("source_quotes"),
            }
            for slide in explainer.get("slides", [])
        ],
    }


def write_content(job, explainer):
    payload = build_content(explainer)
    job.content_path.parent.mkdir(parents=True, exist_ok=True)
    job.content_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Content written: {job.content_path}")
    print(f"Slides: {payload['slide_count']}")
    for slide in payload["slides"]:
        print(f"  {slide['id']} {slide['role']}: {slide['heading']}")
        print(f"       - {slide['explanation']}")
    return job.content_path
