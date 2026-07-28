# Know the Big Picture

Know the Big Picture turns an everyday curiosity into a short visual explanation
for ordinary people. A teenager, an older adult, an artist, or someone speaking
English as a second language should understand it immediately. The goal is not
expertise; it is the smallest satisfying answer.

> The internet explains what. We explain why and how.

The first slide preserves the exact input. Six explicit formats then provide the
right storytelling shape: `why`, `how`, `types`, `comparison`, `what_is_it`, and
`myth_vs_fact`. Types produces a title plus 4–12 varieties; other formats produce
5–6 slides.

## Pipeline

```text
question → source packet → explain → verify → images → compose → render → publish
```

0. **Source** — reuse `source.txt`, create a real source packet from
   `question.txt`, or create a local placeholder source during `--dry-run`.
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
| `--dry-run` | Use a local mock source, content, and images, but compose and render a real video. |
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
- `explainer.content_format` and `item_count`
- `parse.min_slides`, `max_slides`, and word limits
- `images.model` and `vibe`
- `compose.show_role_kicker` and `show_explanation`
- `video.min_seconds`, `max_seconds`, audio, motion, and outro
- `youtube` and `instagram` publishing settings

Subject categories remain flexible, while format-specific prompts control the
story structure.

## Remote runs

`tools/submit_job.py` uploads a numeric job folder and dispatches
`.github/workflows/run-knowthebigpicture.yml`:

```bash
python tools/submit_job.py --job-folder /path/to/4 --creds ~/kbp_submit_creds.json
python tools/submit_job.py --job-folder /path/to/4 --lite --creds ~/kbp_submit_creds.json
python tools/submit_job.py --job-folder /path/to/4 --real --publish --creds ~/kbp_submit_creds.json
```

The Actions form accepts the input and content format directly. A Types title may
begin with a count from 4–12, such as `8 Coffee Drinks Explained`; otherwise it
defaults to 5 items. Execution modes are `real` (default), `dry_run`, and `lite`.
YouTube publishing defaults on and Instagram publishing defaults off.

For unattended production, `.github/workflows/produce-next-video.yml` checks a
Google Sheet every two hours and processes one `pending` row. Every result is
uploaded as a YouTube Short; `youtube_public` selects public versus private, and
Instagram remains opt-in. See
[`docs/GOOGLE_SHEETS_QUEUE.md`](docs/GOOGLE_SHEETS_QUEUE.md) for the exact
columns, states, secrets, and setup.

## Publishing

Publishing is disabled by default.

- YouTube uploads a private Short by default; queue jobs may explicitly select
  public visibility.
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
contract. See [`docs/CONTENT_FORMATS.md`](docs/CONTENT_FORMATS.md) for format
definitions and the reusable daily idea-generation prompt.
