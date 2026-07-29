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
question → source → explain → verify → content → narrate → images → compose → render → publish
```

0. **Source** — reuse `source.txt`, create a real source packet from
   `question.txt`, or create a local placeholder source during `--dry-run`.
1. **Explain** — generate `explainer.json` and YouTube metadata in one call.
2. **Verify** — check the question slide, structure, word limits, and quotations.
2b. **Content** — write the verified platform-neutral content artifact.
2c. **Narrate** — synthesize and cache per-slide and outro speech.
3. **Images** — generate one teaching-oriented 9:16 visual per slide.
4. **Compose** — add the role, heading, explanation, and brand signature.
5. **Render** — time slides from speech, mix narration with ducked music, and
   create `explainer.mp4` with an optional outro.
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
    narration/
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
- `parse.provider`, Gemini/OpenAI models, and verification behavior
- `images.provider`, models, quality, aspect ratio, and vibe
- `compose.show_role_kicker` and `show_explanation`
- `video.min_seconds`, `max_seconds`, audio, motion, and outro
- `video.voiceover` enablement, Edge voice, rate, music volume, and failure mode
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

The scheduled queue workflow is the current unattended production path and
exports both Gemini and OpenAI credentials. The older manual workflow currently
exports only `OPENAI_API_KEY`; because the package text-provider default is now
Gemini, its real/lite path needs `GEMINI_API_KEY` added to that workflow before
it can use the current defaults.

The package default for source and explainer generation is Gemini
`gemini-3.6-flash`; OpenAI `gpt-5-mini` is an explicit alternative. The package
default image path is OpenAI `gpt-image-1-mini` at low quality, while the example
job template deliberately overrides images to Gemini/high quality. Providers do
not automatically fall back to one another.

For unattended production, `.github/workflows/produce-next-video.yml` checks a
Google Sheet at 02:27 and 14:27 UTC and processes one `pending` row. Every result is
uploaded as a YouTube Short; `youtube_public` selects public versus private, and
Instagram remains opt-in. Voice-over defaults on and may be disabled with the
optional `voiceover` Sheet column. See
[`docs/GOOGLE_SHEETS_QUEUE.md`](docs/GOOGLE_SHEETS_QUEUE.md) for the exact
columns, states, secrets, and setup.

## Publishing

Publishing is disabled in the general job template. Queue-created jobs always
enable YouTube.

- YouTube uploads a private Short by default; queue jobs may explicitly select
  public visibility.
- Instagram defaults to `container_only`, which validates a Reel container
  without making it public. Set `instagram.publish_mode` to `live` intentionally.
- Instagram requires a public HTTPS video URL, normally created from the remote
  Drive copy during a `--remote` run.

## Secrets and environment

Local secrets live in `secrets/knowthebigpicture.secrets.json` or environment
variables:

- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and optional `GEMINI_MODEL`
- `OPENAI_API_KEY` and optional `OPENAI_MODEL`
- optional `GEMINI_IMAGE_MODEL`
- `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`
- `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`
- `RCLONE_CONFIG`

Know the Big Picture-specific environment variables use the `KBP_` prefix:
`KBP_REMOTE_ROOT`, `KBP_RCLONE_BIN`, `KBP_JOBS_DIR`, `KBP_BRAND_STYLES`, and
`KBP_SUBMIT_CREDS`.

Narration uses Edge TTS and does not require an additional API secret. Package
defaults are `en-US-EmmaNeural` at `+10%`; the example template uses
`en-US-AndrewNeural` at `+0%`.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the canonical product and technical
contract. See [`docs/CONTENT_FORMATS.md`](docs/CONTENT_FORMATS.md) for format
definitions and the reusable daily idea-generation prompt.
