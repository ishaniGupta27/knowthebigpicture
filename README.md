# KnowTheTimeline

An automated short-form video engine that turns a raw source document (a news
article, court filing, or press release) into a 60-second, objective,
chronological timeline answering one question: **"How did we get here?"**

It reuses the battle-tested orchestration model from Fashionbot: heavy media
lives in **Google Drive**, jobs run on **GitHub Actions**, and finished videos
are published as private **YouTube Shorts**.

## Pipeline

```
inputs/source.txt
      │
  1. PARSE     LLM -> timeline.json (Hourglass structure) + youtube_metadata.json
  2. VERIFY    mechanical fact-checks (verbatim quotes, dates, chronology, word cap)
  3. IMAGES    one 9:16 background per node (OpenAI, parallel, vibe sandwich)
  4. COMPOSE   Pillow lays headline + date + brand signature onto each background
  5. RENDER    render_plan.json (natural timing) -> timeline.mp4 (MoviePy + outro + audio)
  6. PUBLISH   private YouTube Short (upload only; metadata already generated in step 1)
      │
   timeline.mp4
```

Each stage reads and writes files inside a numeric **job folder**, so any stage
can be re-run and cached outputs are skipped.

## Job folder contract

```
jobs/<job_id>/
  job.json                 # optional; every setting has a default
  inputs/
    source.txt             # the ONLY required author input
  outputs/
    timeline.json          # stage 1 + stage 2 (verification written in place)
    youtube_metadata.json  # stage 1
    backgrounds/<id>.jpg    # stage 3
    frames/<id>.jpg         # stage 4 (cheap local re-derivation, not synced)
    render_plan.json        # stage 5
    timeline.mp4            # stage 5
    youtube_upload.json     # stage 6
  logs/
  status.json
```

## Local usage

```bash
cd code
python -m pip install -r requirements.txt

# Offline plumbing test (mocks the LLM + image calls, still renders a real mp4):
python -m knowthetimeline.run 1 --dry-run

# Real local run (needs OPENAI_API_KEY in secrets/ or env):
python -m knowthetimeline.run 1

# Validate secrets without rendering:
python -m knowthetimeline.validate_secrets --all
```

Set the local jobs directory with `--jobs-dir` or the `KTT_JOBS_DIR` env var
(defaults to `<repo>/jobs`).

## Remote + GitHub Actions

`tools/submit_job.py` uploads a local job folder to Google Drive and dispatches
the `Run KnowTheTimeline` workflow, which pulls the job with `rclone`, runs the
pipeline, and pushes results back.

```bash
python tools/submit_job.py --job-folder /path/to/1 --creds ~/ktt_submit_creds.json
python tools/submit_job.py --job-folder /path/to/1 --real --publish --creds ~/ktt_submit_creds.json
```

## Secrets

Copy `secrets/knowthetimeline.secrets.example.json` to
`secrets/knowthetimeline.secrets.json` (git-ignored) or set the equivalent env
vars / GitHub Actions secrets:

- `OPENAI_API_KEY` (+ optional `OPENAI_MODEL`) — parsing and image generation
- `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` — publishing
- `RCLONE_CONFIG` — remote Drive sync

## Author-supplied assets

- `assets/brand/styles.json` — image "vibe" library (shipped; edit to taste)
- `assets/fonts/` — a heavy headline font (e.g. `Montserrat-Bold.ttf`)
- `assets/outro/outro.jpg` — global outro card (a fallback is generated if absent)
- `assets/audio/` — an optional music bed

See `docs/DESIGN.md` for the full design rationale behind every stage.
