# KnowTheTimeline

Turns a news source into a 60-second, objective, chronological video answering
one question: **"How did we get here?"** Heavy media lives in Google Drive, jobs
run on GitHub Actions, and finished videos publish as private YouTube Shorts.

## Pipeline

`source -> parse -> verify -> images -> compose -> render -> publish`

0. **source** – if only `headline.txt` exists, LLM writes `source.txt` (skipped if `source.txt` present)
1. **parse** – LLM -> `timeline.json` + `youtube_metadata.json`
2. **verify** – mechanical checks (verbatim quotes, dates, chronology, word cap)
3. **images** – one 9:16 background per slide (OpenAI, parallel)
4. **compose** – Pillow draws date + headline + detail onto each background
5. **render** – timing plan -> `timeline.mp4` (MoviePy, + outro, + optional audio)
6. **publish** – upload as a private YouTube Short

Everything lives in a numeric job folder; stages cache, so re-runs skip finished work:

```
jobs/<id>/
  job.json            # optional; every setting has a default
  inputs/source.txt   # OR inputs/headline.txt (stage 0 expands it)
  outputs/            # timeline.json, content.json, backgrounds/, frames/, timeline.mp4, ...
  logs/  status.json
```

## Run it

```bash
cd code
python -m pip install -r requirements.txt

python -m knowthetimeline.run <id>            # full run (needs OPENAI_API_KEY)
python -m knowthetimeline.validate_secrets --all
```

### Options

| Flag | What it does |
|------|--------------|
| `--dry-run` | Fully offline: mocks the LLM + images, still renders a real mp4. Needs `source.txt`. |
| `--lite` | Content only: parse + verify -> `content.json`, then stop. No images/video/publish. Cheapest way to test the writing. |
| `--remote [root]` | Pull the job from Drive (rclone) before, push results after. Root defaults to `KTT_REMOTE_ROOT`. |
| `--no-publish` | Render everything but never upload to YouTube. |
| `--force` | Ignore cached `timeline.json` and re-parse. |
| `--jobs-dir PATH` | Local jobs dir (default `<repo>/jobs`, or `KTT_JOBS_DIR`). |

Common combos: `--lite` (real content, no image spend), `--dry-run --lite` (offline structure check), `--remote --no-publish` (full render on a runner, no upload).

## Remote + GitHub Actions

`tools/submit_job.py` uploads a job folder to Drive and dispatches the workflow:

```bash
python tools/submit_job.py --job-folder /path/to/<id> --creds ~/ktt_submit_creds.json           # dry_run
python tools/submit_job.py --job-folder /path/to/<id> --lite --creds ~/ktt_submit_creds.json     # content only
python tools/submit_job.py --job-folder /path/to/<id> --real --publish --creds ~/ktt_submit_creds.json
```

The workflow's `execution_mode` mirrors these: `dry_run` | `lite` | `real`.

## Secrets

Copy `secrets/knowthetimeline.secrets.example.json` to
`secrets/knowthetimeline.secrets.json` (git-ignored), or set env / Actions secrets:

- `OPENAI_API_KEY` (+ optional `OPENAI_MODEL`) — parsing, source, images
- `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN` — publishing
- `RCLONE_CONFIG` — remote Drive sync

## Assets (`assets/`)

`brand/styles.json` (image vibes, shipped) · `fonts/` (headline font) ·
`outro/outro.jpg` (fallback generated if absent) · `audio/` (optional music bed).

See `docs/DESIGN.md` for the full design rationale.
