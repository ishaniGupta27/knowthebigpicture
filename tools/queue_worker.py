#!/usr/bin/env python3
"""Claim and update Know the Big Picture jobs in a Google Sheet."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote
from uuid import uuid4


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
DEFAULT_TAB = "VideoQueue"
VALID_FORMATS = {
    "why",
    "how",
    "types",
    "comparison",
    "what_is_it",
    "myth_vs_fact",
}
REQUIRED_HEADERS = (
    "id",
    "status",
    "format",
    "topic",
    "number_of_items",
    "created_at",
    "started_at",
    "completed_at",
    "output_url",
    "error",
    "retry_count",
    "youtube_public",
    "publish_instagram",
)


class QueueError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def normalize_bool(value, default=False):
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"true", "yes", "y", "1", "on"}:
        return True
    if text in {"false", "no", "n", "0", "off"}:
        return False
    raise QueueError(f"Expected a boolean value, got {value!r}")


def numeric_id(value):
    text = str(value or "").strip()
    if not text.isdigit():
        raise QueueError(f"Queue id must be numeric, got {value!r}")
    return int(text)


def github_output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        print(f"{name}={value}")
        return
    text = str(value)
    delimiter = f"KBP_{uuid4().hex}"
    with Path(path).open("a") as output:
        output.write(f"{name}<<{delimiter}\n{text}\n{delimiter}\n")


class SheetQueue:
    def __init__(self, spreadsheet_id, tab_name, credentials_path):
        try:
            from google.auth.transport.requests import AuthorizedSession
            from google.oauth2 import service_account
        except ImportError as exc:
            raise QueueError(
                "Google authentication dependency missing. Install google-auth."
            ) from exc

        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=[SHEETS_SCOPE],
        )
        self.session = AuthorizedSession(credentials)
        self.spreadsheet_id = spreadsheet_id
        self.tab_name = tab_name

    def _values_url(self, a1_range):
        encoded = quote(f"'{self.tab_name}'!{a1_range}", safe="")
        return f"{SHEETS_API}/{self.spreadsheet_id}/values/{encoded}"

    def read_rows(self):
        response = self.session.get(
            self._values_url("A:Z"),
            params={"majorDimension": "ROWS"},
            timeout=60,
        )
        if response.status_code >= 400:
            raise QueueError(
                f"Google Sheets read failed: HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        values = response.json().get("values", [])
        if not values:
            raise QueueError(f"Sheet tab {self.tab_name!r} is empty")

        headers = [str(value).strip() for value in values[0]]
        missing = [name for name in REQUIRED_HEADERS if name not in headers]
        if missing:
            raise QueueError(
                "VideoQueue is missing required columns: " + ", ".join(missing)
            )

        rows = []
        for row_number, values_row in enumerate(values[1:], start=2):
            padded = list(values_row) + [""] * (len(headers) - len(values_row))
            row = dict(zip(headers, padded[: len(headers)]))
            row["_row_number"] = row_number
            rows.append(row)
        return headers, rows

    def update_row(self, headers, row):
        row_number = row["_row_number"]
        values = [[row.get(header, "") for header in headers]]
        end_column = column_name(len(headers))
        a1_range = f"A{row_number}:{end_column}{row_number}"
        response = self.session.put(
            self._values_url(a1_range),
            params={"valueInputOption": "RAW"},
            json={"majorDimension": "ROWS", "values": values},
            timeout=60,
        )
        if response.status_code >= 400:
            raise QueueError(
                f"Google Sheets update failed: HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )


def column_name(number):
    if number < 1:
        raise ValueError("Column number must be positive")
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def validate_job(row):
    job_id = str(numeric_id(row.get("id")))
    content_format = str(row.get("format") or "").strip().lower()
    if content_format not in VALID_FORMATS:
        raise QueueError(
            f"Job {job_id} format must be one of: {', '.join(sorted(VALID_FORMATS))}"
        )
    topic = str(row.get("topic") or "").strip()
    if not topic:
        raise QueueError(f"Job {job_id} topic is empty")

    number_of_items = str(row.get("number_of_items") or "").strip()
    if number_of_items:
        try:
            count = int(number_of_items)
        except ValueError as exc:
            raise QueueError(
                f"Job {job_id} number_of_items must be an integer"
            ) from exc
        if content_format == "types" and not 4 <= count <= 12:
            raise QueueError(
                f"Job {job_id} number_of_items must be between 4 and 12"
            )
        if content_format != "types":
            raise QueueError(
                f"Job {job_id} number_of_items is only valid for format types"
            )

    return {
        "id": job_id,
        "content_format": content_format,
        "topic": topic,
        "number_of_items": number_of_items,
        "youtube_public": normalize_bool(row.get("youtube_public"), default=False),
        "publish_instagram": normalize_bool(
            row.get("publish_instagram"), default=False
        ),
        # Optional column; defaults on so existing sheets keep getting voice-over.
        "voiceover": normalize_bool(row.get("voiceover"), default=True),
    }


def find_job(rows, job_id):
    matches = [
        row for row in rows if str(row.get("id") or "").strip() == str(job_id)
    ]
    if not matches:
        raise QueueError(f"Queue job id not found: {job_id}")
    if len(matches) > 1:
        raise QueueError(f"Queue contains duplicate job id: {job_id}")
    return matches[0]


def fail_row(queue, headers, row, error):
    try:
        retry_count = int(str(row.get("retry_count") or "0").strip())
    except ValueError:
        retry_count = 0
    row["status"] = "failed"
    row["completed_at"] = utc_now()
    row["error"] = str(error)[:2000]
    row["retry_count"] = str(retry_count + 1)
    queue.update_row(headers, row)


def command_claim(queue):
    headers, rows = queue.read_rows()
    id_counts = {}
    for existing_row in rows:
        existing_id = str(existing_row.get("id") or "").strip()
        if existing_id:
            id_counts[existing_id] = id_counts.get(existing_id, 0) + 1
    pending = [
        row
        for row in rows
        if str(row.get("status") or "").strip().lower() == "pending"
    ]
    if not pending:
        github_output("has_job", "false")
        print("No pending video ideas found.")
        return

    candidates = []
    for row in pending:
        try:
            candidates.append((numeric_id(row.get("id")), row))
        except QueueError as exc:
            fail_row(queue, headers, row, exc)
            print(f"Rejected row {row['_row_number']}: {exc}")

    row = None
    job = None
    for _, candidate in sorted(candidates, key=lambda item: item[0]):
        try:
            candidate_id = str(candidate.get("id") or "").strip()
            if id_counts.get(candidate_id, 0) > 1:
                raise QueueError(f"Queue contains duplicate job id: {candidate_id}")
            job = validate_job(candidate)
            row = candidate
            break
        except QueueError as exc:
            fail_row(queue, headers, candidate, exc)
            print(f"Rejected job {candidate.get('id')}: {exc}")

    if row is None or job is None:
        github_output("has_job", "false")
        print("No valid pending video ideas found.")
        return

    row["status"] = "processing"
    row["started_at"] = utc_now()
    row["completed_at"] = ""
    row["output_url"] = ""
    row["error"] = ""
    queue.update_row(headers, row)

    github_output("has_job", "true")
    github_output("job_id", job["id"])
    github_output("content_format", job["content_format"])
    github_output("topic", job["topic"])
    github_output("number_of_items", job["number_of_items"])
    github_output("youtube_public", str(job["youtube_public"]).lower())
    github_output("publish_instagram", str(job["publish_instagram"]).lower())
    github_output("voiceover", str(job["voiceover"]).lower())
    print(f"Claimed queue job {job['id']}: {job['topic']}")


def command_complete(queue, job_id, output):
    headers, rows = queue.read_rows()
    row = find_job(rows, job_id)
    row["status"] = "done"
    row["completed_at"] = utc_now()
    row["output_url"] = output
    row["error"] = ""
    queue.update_row(headers, row)
    print(f"Completed queue job {job_id}")


def command_fail(queue, job_id, error):
    headers, rows = queue.read_rows()
    row = find_job(rows, job_id)
    fail_row(queue, headers, row, error)
    print(f"Failed queue job {job_id}")


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("claim", "complete", "fail"),
    )
    parser.add_argument("--job-id")
    parser.add_argument("--output")
    parser.add_argument("--error")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID")
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    tab_name = os.environ.get("GOOGLE_SHEET_TAB", DEFAULT_TAB)
    if not spreadsheet_id:
        print("ERROR: GOOGLE_SHEET_ID is required")
        return 1
    if not credentials_path:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS is required")
        return 1

    try:
        queue = SheetQueue(spreadsheet_id, tab_name, credentials_path)
        if args.command == "claim":
            command_claim(queue)
        elif args.command == "complete":
            if not args.job_id or not args.output:
                raise QueueError("complete requires --job-id and --output")
            command_complete(queue, args.job_id, args.output)
        else:
            if not args.job_id or not args.error:
                raise QueueError("fail requires --job-id and --error")
            command_fail(queue, args.job_id, args.error)
    except (QueueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
