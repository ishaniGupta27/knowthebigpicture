import json
import re

from .errors import VerificationError
from .job import parse_settings
from .parse import sanitize_source
from . import settings


def normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip().casefold()


def word_count(text):
    return len((text or "").split())


def quote_match(quote, source_norm, source_raw):
    if not quote:
        return "missing"
    if quote in source_raw:
        return "exact"
    if normalize(quote) in source_norm:
        return "normalized"
    return "missing"


def date_key(iso):
    """Sortable tuple from an ISO date that may be partial (YYYY, YYYY-MM, ...)."""
    if not iso:
        return None
    parts = str(iso).split("-")
    try:
        nums = [int(p) for p in parts[:3]]
    except ValueError:
        return None
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def verify_node(node, source_norm, source_raw, max_words):
    role = node.get("role")
    headline = node.get("headline", "")
    result = {
        "passed": True,
        "word_count": word_count(headline),
        "checks": {},
    }

    def fail(name, reason):
        result["passed"] = False
        result["checks"][name] = {"passed": False, "reason": reason}

    def ok(name, **extra):
        result["checks"][name] = {"passed": True, **extra}

    # Word cap.
    if result["word_count"] > max_words:
        fail("word_cap", f"headline has {result['word_count']} words (max {max_words})")
    else:
        ok("word_cap")

    # Verbatim source quote for roles that require it.
    if role in settings.QUOTED_ROLES:
        match = quote_match(node.get("source_quote"), source_norm, source_raw)
        if match == "missing":
            fail("source_quote", "source_quote not found in source.txt")
        else:
            ok("source_quote", match=match)

    # Date grounding (dates-only): displayed date must appear in the source.
    display = node.get("event_date_display")
    if display:
        if normalize(display) in source_norm:
            ok("date_grounded", date=display)
        else:
            fail("date_grounded", f"date '{display}' not found in source.txt")

    node["verification"] = result
    return result["passed"]


def verify_structure(nodes, min_developments):
    problems = []
    counts = {role: 0 for role in settings.VALID_ROLES}
    for node in nodes:
        counts[node.get("role")] = counts.get(node.get("role"), 0) + 1

    for role in (settings.ROLE_PRESENT_HOOK, settings.ROLE_STARTING_POINT, settings.ROLE_RESOLUTION):
        if counts.get(role, 0) != 1:
            problems.append(f"expected exactly 1 '{role}', found {counts.get(role, 0)}")

    if counts.get(settings.ROLE_DEVELOPMENT, 0) < min_developments:
        problems.append(
            f"expected at least {min_developments} developments, "
            f"found {counts.get(settings.ROLE_DEVELOPMENT, 0)}"
        )
    return problems


def verify_chronology(nodes):
    dated = [
        (node["id"], date_key(node.get("event_date")))
        for node in nodes
        if node.get("role") in settings.DATED_ROLES and node.get("event_date")
    ]
    problems = []
    previous_id, previous_key = None, None
    for node_id, key in dated:
        if key is None:
            continue
        if previous_key is not None and key < previous_key:
            problems.append(
                f"node {node_id} event_date is earlier than node {previous_id}"
            )
        previous_id, previous_key = node_id, key
    return problems


def run_verify(job, timeline):
    """Stage 2: mechanically check the timeline; write results in place."""
    cfg = parse_settings(job)
    source_raw = sanitize_source(job.source_path.read_text())
    source_norm = normalize(source_raw)
    nodes = timeline.get("nodes", [])

    passed_count = 0
    failed_segments = []
    for node in nodes:
        if verify_node(node, source_norm, source_raw, cfg["max_words_per_headline"]):
            passed_count += 1
        else:
            failed_segments.append(node.get("id"))

    structure_problems = verify_structure(nodes, cfg["min_developments"])
    chronology_problems = verify_chronology(nodes)

    ok = (
        not failed_segments
        and not structure_problems
        and not chronology_problems
    )

    timeline["verification_summary"] = {
        "status": "passed" if ok else "failed",
        "nodes_total": len(nodes),
        "nodes_passed": passed_count,
        "nodes_failed": len(failed_segments),
        "failed_segments": failed_segments,
        "structure_problems": structure_problems,
        "chronology_problems": chronology_problems,
        "grounding": cfg["grounding"],
    }

    with job.timeline_path.open("w") as f:
        json.dump(timeline, f, indent=2)
        f.write("\n")

    if ok:
        print(f"Verification passed: {passed_count}/{len(nodes)} nodes")
        return timeline

    print("Verification FAILED:")
    for problem in structure_problems + chronology_problems:
        print(f"  - {problem}")
    if failed_segments:
        print(f"  - failing nodes: {failed_segments}")

    if cfg["on_verification_fail"] == "fail_job":
        raise VerificationError(
            "Timeline failed verification; nothing will be published. "
            f"See {job.timeline_path} for per-node detail."
        )
    return timeline
