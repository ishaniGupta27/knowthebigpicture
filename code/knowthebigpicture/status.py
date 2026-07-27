import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_status(job, status, **extra):
    payload = {
        "job_id": job.job_id,
        "status": status,
        "updated_at": utc_now(),
    }
    payload.update(extra)

    path = Path(job.status_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    return path
