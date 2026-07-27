# Know the Big Picture

Know the Big Picture turns a question into a short visual explanation for ordinary
people with no technical background. A teenager, an older adult, an artist, or
someone speaking English as a second language should understand it immediately.
It teaches the relevant **what, why, how, who, and when** without forcing every
question into the same structure.

> The internet explains what. We explain why and how.

The first slide always poses the question. The remaining slides build the
smallest useful teaching path: definitions, purpose, mechanisms, components,
examples, comparisons, context, misconceptions, or a surprising final insight.
The content is evergreen by default and source-grounded. Time appears only when
it genuinely helps explain the subject.

## Pipeline

```text
question → source packet → explain → verify → images → compose → render → publish
```

0. **Source** — reuse `source.txt`, or create a source packet from `question.txt`.
1. **Explain** — generate `explainer.json` and YouTube metadata in one call.
2. **Verify** — check the question slide, structure, word limits, and quotations.
3. **Images** — generate one teaching-oriented 9:16 visual per slide.
4. **Compose** — add the role, heading, explanation, and brand signature.
5. **Render** — create `explainer.mp4` with derived timing and an optional outro.
6. **Publish** — optionally upload to YouTube Shorts and/or Instagram Reels.

Stages cache their outputs, so interrupted jobs can resume without repeating
expensive work.

## Job contract

```text
jobs/<id>/
  job.json
  inputs/
    question.txt       # required unless explainer.question is configured
    source.txt         # optional; generated from the question when absent
  outputs/
    explainer.json
    content.json
    youtube_metadata.json
    backgrounds/
    frames/
    render_plan.json
    explainer.mp4
  logs/
  status.json
```

Start from [`job_templates/explainer`](job_templates/explainer). A job may omit
`job.json`; the defaults are sufficient.

## Run locally

```bash
cd code
python -m pip install -r requirements.txt

python -m knowthebigpicture.run <id>
python -m knowthebigpicture.validate_secrets --all
```

Options:

| Flag | Effect |
|---|---|
| `--dry-run` | Use local mock content and images, but compose and render a real video. Requires `source.txt`. |
| `--lite` | Stop after verified `content.json`; no images, video, or publishing. |
| `--remote [root]` | Pull and push the job with rclone. Defaults to `KBP_REMOTE_ROOT`. |
| `--no-publish` | Render without uploading. |
| `--youtube` / `--instagram` | Restrict publishing to the named platform(s). |
| `--force` | Regenerate cached content, frames, and video. |
| `--jobs-dir PATH` | Override `jobs/`; also configurable with `KBP_JOBS_DIR`. |

Useful checks:

```bash
python -m knowthebigpicture.run 1 --dry-run --lite
python -m knowthebigpicture.run 1 --dry-run --force
python -m knowthebigpicture.run 1 --remote --no-publish
```

## Job configuration

The important controls are:

- `explainer.question`, `subject`, and `audience`
- `parse.min_slides`, `max_slides`, and word limits
- `images.model` and `vibe`
- `compose.show_role_kicker` and `show_explanation`
- `video.min_seconds`, `max_seconds`, audio, motion, and outro
- `youtube` and `instagram` publishing settings

There are no content categories. The same prompt and schema adapt to any
well-sourced question.

## Remote runs

`tools/submit_job.py` uploads a numeric job folder and dispatches
`.github/workflows/run-knowthebigpicture.yml`:

```bash
python tools/submit_job.py --job-folder /path/to/4 --creds ~/kbp_submit_creds.json
python tools/submit_job.py --job-folder /path/to/4 --lite --creds ~/kbp_submit_creds.json
python tools/submit_job.py --job-folder /path/to/4 --real --publish --creds ~/kbp_submit_creds.json
```

Execution modes are `dry_run`, `lite`, and `real`. Add `--publish-instagram` to
request Instagram publishing.

## Publishing

Publishing is disabled by default.

- YouTube uploads a private Short using the generated question-led metadata.
- Instagram defaults to `container_only`, which validates a Reel container
  without making it public. Set `instagram.publish_mode` to `live` intentionally.
- Instagram requires a public HTTPS video URL, normally created from the remote
  Drive copy during a `--remote` run.

## Secrets and environment

Local secrets live in `secrets/knowthebigpicture.secrets.json` or environment
variables:

- `OPENAI_API_KEY` and optional `OPENAI_MODEL`
- `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`
- `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`
- `RCLONE_CONFIG`

Know the Big Picture-specific environment variables use the `KBP_` prefix:
`KBP_REMOTE_ROOT`, `KBP_RCLONE_BIN`, `KBP_JOBS_DIR`, `KBP_BRAND_STYLES`, and
`KBP_SUBMIT_CREDS`.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the canonical product and technical
contract.
