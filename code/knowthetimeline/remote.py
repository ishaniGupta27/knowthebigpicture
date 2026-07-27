import os
import subprocess
from pathlib import Path

from .errors import KttError
from .secrets import secret_value
from .settings import BASE_DIR


def remote_root_from_env():
    return os.environ.get("KTT_REMOTE_ROOT")


def rclone_bin_from_env():
    return os.environ.get("KTT_RCLONE_BIN", "rclone")


def configure_rclone_from_secret():
    config_value = secret_value("RCLONE_CONFIG")
    if not config_value:
        return

    possible_path = Path(config_value).expanduser()
    if possible_path.is_file():
        os.environ["RCLONE_CONFIG"] = str(possible_path)
        return

    if "[" not in config_value or "]" not in config_value:
        return

    config_path = BASE_DIR / ".ktt_runtime" / "rclone.conf"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_value)
    os.environ["RCLONE_CONFIG"] = str(config_path)


def remote_join(root, *parts):
    remote = str(root).rstrip("/")
    suffix = "/".join(str(part).strip("/") for part in parts if str(part).strip("/"))
    return f"{remote}/{suffix}" if suffix else remote


def run_rclone_copy(rclone_bin, source, destination, label, exclude=None):
    configure_rclone_from_secret()

    command = [rclone_bin, "copy", str(source), str(destination), "--progress"]
    for pattern in exclude or []:
        command.extend(["--exclude", pattern])

    print(f"\nREMOTE {label}")
    print("Command: " + " ".join(command))

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as e:
        raise KttError(
            "rclone was not found. Install rclone or set KTT_RCLONE_BIN "
            "to the full rclone path."
        ) from e
    except subprocess.CalledProcessError as e:
        raise KttError(f"rclone failed while {label.lower()}") from e


def rclone_copy_file(rclone_bin, local_file, remote_path):
    """Copy a single local file to an exact remote path (rclone copyto)."""
    configure_rclone_from_secret()

    command = [rclone_bin, "copyto", str(local_file), str(remote_path)]
    print("\nREMOTE COPY FILE")
    print("Command: " + " ".join(command))

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as e:
        raise KttError(
            "rclone was not found. Install rclone or set KTT_RCLONE_BIN "
            "to the full rclone path."
        ) from e
    except subprocess.CalledProcessError as e:
        raise KttError(f"rclone failed to copy {local_file} to {remote_path}") from e


def rclone_public_link(rclone_bin, remote_path):
    configure_rclone_from_secret()

    command = [rclone_bin, "link", str(remote_path)]
    print("\nREMOTE PUBLIC LINK")
    print("Command: " + " ".join(command))

    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True
        )
    except FileNotFoundError as e:
        raise KttError(
            "rclone was not found. Install rclone or set KTT_RCLONE_BIN "
            "to the full rclone path."
        ) from e
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or "").strip()
        raise KttError(
            f"rclone failed to create a public link for {remote_path}: {detail}"
        ) from e

    link = (result.stdout or "").strip()
    if not link:
        raise KttError(f"rclone link returned no URL for {remote_path}")
    return link


def pull_remote_inputs(job_id, remote_root, jobs_root, assets_root, rclone_bin):
    common_excludes = [".DS_Store", "**/.DS_Store"]
    # frames/ are cheap local re-derivations; don't waste bandwidth pulling them.
    job_excludes = common_excludes + ["outputs/frames/**"]

    run_rclone_copy(
        rclone_bin,
        remote_join(remote_root, "assets"),
        assets_root,
        "PULL assets",
        exclude=common_excludes,
    )
    run_rclone_copy(
        rclone_bin,
        remote_join(remote_root, "jobs", job_id),
        Path(jobs_root) / str(job_id),
        "PULL job folder",
        exclude=job_excludes,
    )


def push_remote_job(job_id, remote_root, jobs_root, rclone_bin):
    local_job = Path(jobs_root) / str(job_id)
    if not local_job.exists():
        raise KttError(f"Local job folder does not exist, cannot push: {local_job}")

    run_rclone_copy(
        rclone_bin,
        local_job,
        remote_join(remote_root, "jobs", job_id),
        "PUSH job folder",
        exclude=[
            ".DS_Store",
            "**/.DS_Store",
            "outputs/frames/**",
        ],
    )
