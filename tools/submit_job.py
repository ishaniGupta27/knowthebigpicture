#!/usr/bin/env python3
import argparse
import json
import mimetypes
import os
from pathlib import Path
import sys
from datetime import datetime
from urllib.parse import quote


DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_API = "https://www.googleapis.com/drive/v3"
GOOGLE_DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3"
GITHUB_API = "https://api.github.com"

EXCLUDED_FILENAMES = {".DS_Store"}
EXCLUDED_REL_PREFIXES = {
    Path("outputs") / "frames",
}


class SubmitError(RuntimeError):
    pass


def requests_module():
    import requests

    return requests


class Logger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a", buffering=1)

    def close(self):
        self.file.close()

    def line(self, message=""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = f"[{timestamp}] {message}" if message else ""
        print(text)
        self.file.write(text + "\n")

    def section(self, title):
        self.line()
        self.line("=" * 80)
        self.line(title)
        self.line("=" * 80)


def load_json(path, label):
    try:
        with Path(path).open("r") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise SubmitError(f"Missing {label}: {path}") from e
    except json.JSONDecodeError as e:
        raise SubmitError(f"Invalid {label} JSON: {e}") from e


def require_string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise SubmitError(f"{label} must be a non-empty string")
    return value.strip()


def validate_job_folder(path):
    job_folder = Path(path).expanduser().resolve()
    if not job_folder.is_dir():
        raise SubmitError(f"--job-folder must be a directory: {job_folder}")

    job_id = job_folder.name
    if not job_id.isdigit():
        raise SubmitError(
            f"Job folder name must be numeric because it becomes job_id: {job_folder}"
        )

    inputs_dir = job_folder / "inputs"
    source = inputs_dir / "source.txt"
    if not inputs_dir.is_dir():
        raise SubmitError(f"Missing inputs directory: {inputs_dir}")
    if not source.is_file():
        raise SubmitError(f"Missing required author input: {source}")

    job_json = job_folder / "job.json"
    if job_json.is_file():
        load_json(job_json, "job.json")
    return job_folder, job_id


def should_upload_file(path, root):
    rel = Path(path).relative_to(root)
    if path.name in EXCLUDED_FILENAMES:
        return False
    for prefix in EXCLUDED_REL_PREFIXES:
        try:
            rel.relative_to(prefix)
            return False
        except ValueError:
            pass
    return path.is_file()


def iter_upload_files(root):
    root = Path(root)
    return sorted(path for path in root.rglob("*") if should_upload_file(path, root))


def drive_quote(value):
    return value.replace("\\", "\\\\").replace("'", "\\'")


class GoogleDriveClient:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.access_token = self.refresh_access_token()

    def refresh_access_token(self):
        self.logger.section("GOOGLE DRIVE AUTH")
        payload = {
            "client_id": require_string(
                self.config.get("client_id"), "google_drive.client_id"
            ),
            "client_secret": require_string(
                self.config.get("client_secret"), "google_drive.client_secret"
            ),
            "refresh_token": require_string(
                self.config.get("refresh_token"), "google_drive.refresh_token"
            ),
            "grant_type": "refresh_token",
        }
        requests = requests_module()
        response = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=60)
        if response.status_code != 200:
            raise SubmitError(
                "Google OAuth refresh failed. Check client_id/client_secret/"
                f"refresh_token. HTTP {response.status_code}: {response.text}"
            )
        token = response.json().get("access_token")
        if not token:
            raise SubmitError("Google OAuth response did not include access_token")
        self.logger.line("Google access token refreshed")
        return token

    def headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def request(self, method, url, **kwargs):
        headers = kwargs.pop("headers", {})
        merged_headers = self.headers()
        merged_headers.update(headers)
        requests = requests_module()
        return requests.request(
            method,
            url,
            headers=merged_headers,
            timeout=kwargs.pop("timeout", 120),
            **kwargs,
        )

    def find_child(self, parent_id, name, mime_type=None):
        query_parts = [
            f"'{drive_quote(parent_id)}' in parents",
            f"name = '{drive_quote(name)}'",
            "trashed = false",
        ]
        if mime_type:
            query_parts.append(f"mimeType = '{drive_quote(mime_type)}'")
        response = self.request(
            "GET",
            f"{GOOGLE_DRIVE_API}/files",
            params={
                "q": " and ".join(query_parts),
                "fields": "files(id,name,mimeType)",
                "pageSize": 10,
            },
        )
        if response.status_code != 200:
            raise SubmitError(
                f"Google Drive lookup failed for {name}. "
                f"HTTP {response.status_code}: {response.text}"
            )
        files = response.json().get("files", [])
        return files[0] if files else None

    def create_folder(self, parent_id, name):
        response = self.request(
            "POST",
            f"{GOOGLE_DRIVE_API}/files",
            headers={"Content-Type": "application/json"},
            json={"name": name, "mimeType": DRIVE_FOLDER_MIME, "parents": [parent_id]},
            params={"fields": "id,name"},
        )
        if response.status_code != 200:
            raise SubmitError(
                f"Could not create Drive folder {name}. "
                f"HTTP {response.status_code}: {response.text}"
            )
        folder = response.json()
        self.logger.line(f"Created Drive folder: {name} ({folder['id']})")
        return folder

    def ensure_folder(self, parent_id, name):
        existing = self.find_child(parent_id, name, DRIVE_FOLDER_MIME)
        if existing:
            self.logger.line(f"Found Drive folder: {name} ({existing['id']})")
            return existing
        return self.create_folder(parent_id, name)

    def root_folder_id(self):
        explicit_id = self.config.get("root_folder_id")
        if explicit_id:
            self.logger.line(f"Using Drive root_folder_id: {explicit_id}")
            return explicit_id
        root_path = require_string(self.config.get("root_path"), "google_drive.root_path")
        parent_id = "root"
        self.logger.line(f"Resolving Drive root_path: {root_path}")
        for part in [p for p in root_path.strip("/").split("/") if p]:
            parent_id = self.ensure_folder(parent_id, part)["id"]
        return parent_id

    def ensure_path(self, parent_id, parts):
        current_id = parent_id
        for part in parts:
            current_id = self.ensure_folder(current_id, part)["id"]
        return current_id

    def upload_file(self, local_path, parent_id, remote_name=None):
        local_path = Path(local_path)
        remote_name = remote_name or local_path.name
        mime_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        size = local_path.stat().st_size

        existing = self.find_child(parent_id, remote_name)
        metadata = {"name": remote_name}
        if existing:
            method = "PATCH"
            init_url = f"{GOOGLE_DRIVE_UPLOAD}/files/{existing['id']}"
            action = "Updated"
        else:
            method = "POST"
            init_url = f"{GOOGLE_DRIVE_UPLOAD}/files"
            metadata["parents"] = [parent_id]
            action = "Created"

        response = self.request(
            method,
            init_url,
            headers={
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": mime_type,
                "X-Upload-Content-Length": str(size),
            },
            params={"uploadType": "resumable", "fields": "id,name"},
            json=metadata,
        )
        if response.status_code not in (200, 201):
            raise SubmitError(
                f"Could not start Drive upload for {local_path}. "
                f"HTTP {response.status_code}: {response.text}"
            )
        upload_url = response.headers.get("Location")
        if not upload_url:
            raise SubmitError(f"Drive upload did not return upload URL for {local_path}")

        with local_path.open("rb") as f:
            requests = requests_module()
            upload_response = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": mime_type, "Content-Length": str(size)},
                timeout=300,
            )
        if upload_response.status_code not in (200, 201):
            raise SubmitError(
                f"Drive upload failed for {local_path}. "
                f"HTTP {upload_response.status_code}: {upload_response.text}"
            )
        self.logger.line(f"{action} file: {remote_name} ({size} bytes)")
        return upload_response.json()

    def upload_job_folder(self, job_folder, job_id):
        self.logger.section("GOOGLE DRIVE UPLOAD")
        root_id = self.root_folder_id()
        job_parent_id = self.ensure_path(root_id, ["jobs", job_id])

        files = iter_upload_files(job_folder)
        self.logger.line(f"Local job folder: {job_folder}")
        self.logger.line(f"Remote target path: jobs/{job_id}")
        self.logger.line(f"Files to upload: {len(files)}")

        folder_cache = {Path("."): job_parent_id}
        for local_file in files:
            rel = local_file.relative_to(job_folder)
            parent_rel = rel.parent
            if parent_rel not in folder_cache:
                current_id = job_parent_id
                current_rel = Path(".")
                for part in parent_rel.parts:
                    current_rel = current_rel / part
                    if current_rel not in folder_cache:
                        current_id = self.ensure_folder(current_id, part)["id"]
                        folder_cache[current_rel] = current_id
                    else:
                        current_id = folder_cache[current_rel]
            self.logger.line(f"Uploading: {rel}")
            self.upload_file(local_file, folder_cache[parent_rel], rel.name)

        return job_parent_id


class GitHubClient:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.owner = require_string(config.get("owner"), "github.owner")
        self.repo = require_string(config.get("repo"), "github.repo")
        self.workflow = require_string(config.get("workflow"), "github.workflow")
        self.branch = require_string(config.get("branch", "main"), "github.branch")
        self.token = require_string(config.get("token"), "github.token")

    def headers(self):
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def dispatch_workflow(self, job_id, remote_root, execution_mode, publish_youtube):
        self.logger.section("GITHUB ACTIONS DISPATCH")
        url = (
            f"{GITHUB_API}/repos/{self.owner}/{self.repo}/actions/workflows/"
            f"{quote(self.workflow, safe='')}/dispatches"
        )
        payload = {
            "ref": self.branch,
            "inputs": {
                "job_id": job_id,
                "remote_root": remote_root,
                "execution_mode": execution_mode,
                "publish_youtube": "true" if publish_youtube else "false",
            },
        }
        self.logger.line(f"Repository: {self.owner}/{self.repo}")
        self.logger.line(f"Workflow: {self.workflow}")
        self.logger.line(f"Branch: {self.branch}")
        self.logger.line(
            f"Inputs: job_id={job_id}, remote_root={remote_root}, "
            f"execution_mode={execution_mode}, publish_youtube={publish_youtube}"
        )

        requests = requests_module()
        response = requests.post(url, headers=self.headers(), json=payload, timeout=60)
        if response.status_code not in (200, 201, 202, 204):
            raise SubmitError(
                f"GitHub workflow dispatch failed. "
                f"HTTP {response.status_code}: {response.text}"
            )

        workflow_url = (
            f"https://github.com/{self.owner}/{self.repo}/actions/workflows/"
            f"{self.workflow}"
        )
        actions_url = f"https://github.com/{self.owner}/{self.repo}/actions"
        self.logger.line("Workflow dispatch accepted by GitHub")
        self.logger.line(f"Workflow link: {workflow_url}")
        self.logger.line(f"Actions link: {actions_url}")
        return workflow_url


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Upload a local KnowTheTimeline job folder and trigger GitHub Actions."
    )
    parser.add_argument(
        "--job-folder",
        required=True,
        help="Local numeric job folder, for example /path/to/2",
    )
    parser.add_argument(
        "--creds",
        default=os.environ.get("KTT_SUBMIT_CREDS"),
        help="Path to submit creds JSON. Can also use KTT_SUBMIT_CREDS.",
    )
    parser.add_argument(
        "--execution-mode",
        choices=("dry_run", "lite", "real"),
        default="dry_run",
        help="GitHub Actions execution mode.",
    )
    parser.add_argument("--real", action="store_true", help="Shortcut for --execution-mode real.")
    parser.add_argument("--lite", action="store_true", help="Shortcut for --execution-mode lite.")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Set publish_youtube=true on the workflow dispatch.",
    )
    parser.add_argument("--remote-root", default=None, help="Override remote_root input.")
    parser.add_argument("--branch", default=None, help="Override GitHub workflow branch/ref.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.real:
        execution_mode = "real"
    elif args.lite:
        execution_mode = "lite"
    else:
        execution_mode = args.execution_mode

    if not args.creds:
        print("ERROR: --creds is required or set KTT_SUBMIT_CREDS", file=sys.stderr)
        return 1

    try:
        job_folder, job_id = validate_job_folder(args.job_folder)
        log_path = job_folder / "logs" / (
            f"local_submit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        logger = Logger(log_path)
    except SubmitError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    try:
        logger.section("SUBMIT JOB")
        logger.line(f"Job folder: {job_folder}")
        logger.line(f"Job id: {job_id}")
        logger.line(f"Execution mode: {execution_mode}")
        logger.line(f"Publish YouTube: {args.publish}")

        creds = load_json(Path(args.creds).expanduser(), "creds")
        google_config = creds.get("google_drive")
        github_config = creds.get("github")
        if not isinstance(google_config, dict):
            raise SubmitError("creds.google_drive must be an object")
        if not isinstance(github_config, dict):
            raise SubmitError("creds.github must be an object")
        if args.branch:
            github_config = dict(github_config)
            github_config["branch"] = args.branch

        remote_root = args.remote_root or creds.get("remote_root") or "gdrive:knowthetimeline"
        remote_root = require_string(remote_root, "remote_root")

        drive = GoogleDriveClient(google_config, logger)
        github = GitHubClient(github_config, logger)

        drive.upload_job_folder(job_folder, job_id)
        workflow_url = github.dispatch_workflow(
            job_id, remote_root, execution_mode, args.publish
        )

        logger.section("UPLOAD SUBMIT LOG")
        root_id = drive.root_folder_id()
        logs_folder_id = drive.ensure_path(root_id, ["jobs", job_id, "logs"])
        drive.upload_file(log_path, logs_folder_id, log_path.name)

        logger.section("DONE")
        logger.line(f"GitHub Actions workflow link: {workflow_url}")
        print()
        print(f"GitHub Actions workflow link: {workflow_url}")
        return 0
    except SubmitError as e:
        logger.line(f"ERROR: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        logger.close()


if __name__ == "__main__":
    raise SystemExit(main())
