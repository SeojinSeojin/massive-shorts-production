# yt-auto

Automated pipeline that plans, renders, and posts YouTube Shorts on a schedule. Content is generated per "topic" (currently `saju`, Korean fortune-telling cards) using Claude for planning, an HTML/Jinja2 template rendered via headless Chromium for the visual card, ffmpeg for video assembly, and the YouTube Data API for upload.

## How it works

The pipeline runs in two phases, driven by [app.py](app.py):

1. **Plan** ([pipeline/planner.py](pipeline/planner.py))
   Calls Claude with the topic's knowledge base ([topics/\<topic\>/kb/](topics/saju/kb)), style prompt ([topics/\<topic\>/planning_prompt.txt](topics/saju/planning_prompt.txt)), and recent post history (to avoid repeating titles/angles). Returns a structured JSON plan (title, hook, body points, tags, layout variant) written to `topics/<topic>/runs/<date>/plan.json`, and appends an entry to `topics/<topic>/history.json`.

2. **Produce** ([pipeline/renderer.py](pipeline/renderer.py), [pipeline/media_pipeline.py](pipeline/media_pipeline.py), [pipeline/audio_fetcher.py](pipeline/audio_fetcher.py), [pipeline/youtube_upload.py](pipeline/youtube_upload.py))
   - Renders the plan into HTML using the topic's Jinja2 template ([templates/card_style_a](templates/card_style_a)).
   - Screenshots the HTML to a 1080x1920 PNG via Playwright.
   - Fetches background audio (Pixabay API, a local folder, or none).
   - Composites image + audio into an MP4 with ffmpeg.
   - Uploads the MP4 as a YouTube Short via OAuth, writing the resulting `video_id` back into `plan.json` and `history.json`.

Re-running `plan` for a date that already has a `plan.json` is a no-op, so `produce` can be retried independently after a failure without generating a new plan.

## Directory structure

```
app.py                        CLI entrypoint (plan / produce / all / auth)
pipeline/
  planner.py                  Claude call → structured content plan
  renderer.py                 Plan JSON → HTML (Jinja2)
  media_pipeline.py           HTML → PNG (Playwright) → MP4 (ffmpeg)
  audio_fetcher.py            Background music (Pixabay / local / none)
  youtube_upload.py           OAuth + YouTube Data API upload
templates/
  card_style_a/                Jinja2 card template (4 layout variants)
topics/
  saju/
    config.yaml                Per-topic settings (model, template, YouTube metadata, schedule)
    planning_prompt.txt         System prompt sent to Claude
    kb/                          Knowledge base files fed to Claude as context
    history.json                 Log of past posts (title/angle/video_id) for dedup
    runs/<date>/plan.json        Generated plan per run (created at runtime)
reference/                     Superseded v1 implementation, kept for history
.github/workflows/post-shorts.yml   Scheduled GitHub Actions runner
```

## Adding a new topic/channel

1. Create `topics/<new_topic>/config.yaml`, `planning_prompt.txt`, and `kb/` (copy `topics/saju` as a starting point).
2. Add a matrix entry in [.github/workflows/post-shorts.yml](.github/workflows/post-shorts.yml) with the topic name and its YouTube OAuth secret names (a commented-out example is already there).
3. Add the corresponding `YOUTUBE_CLIENT_ID_<TOPIC>`, `YOUTUBE_CLIENT_SECRET_<TOPIC>`, `YOUTUBE_TOKEN_JSON_<TOPIC>` secrets to the repo.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
brew install ffmpeg   # or apt-get install ffmpeg
```

### Environment variables

| Variable | Required for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | plan phase | Claude API key |
| `PIXABAY_API_KEY` | produce phase | only if a topic's `production.audio.mode` is `pixabay` |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | produce phase, auth | OAuth client credentials (Google Cloud Console) |
| `OAUTH_TOKEN_PATH` | produce phase, auth | where the OAuth token is read/written; defaults to `token.json` |
| `DRY_RUN` | produce phase | `true` builds the MP4 but skips the YouTube upload |

### One-time YouTube auth

```bash
python app.py --auth
```
Runs the OAuth consent flow locally and saves the token to `OAUTH_TOKEN_PATH`. Copy this token's contents into the topic's `YOUTUBE_TOKEN_JSON_*` GitHub secret for CI use.

## Usage

```bash
# Full run for a topic
python app.py --topic saju

# Only generate today's plan
python app.py --topic saju --phase plan

# Only render + upload (requires an existing plan.json for today)
python app.py --topic saju --phase produce

# Build the video without uploading
DRY_RUN=true python app.py --topic saju
```

## Automation

[.github/workflows/post-shorts.yml](.github/workflows/post-shorts.yml) runs daily at 09:00 UTC across every topic in its matrix (`fail-fast: false`, so one topic failing doesn't block the others). It can also be triggered manually (`workflow_dispatch`) with an optional single-topic filter, phase override, and dry-run flag. On success it commits the updated `history.json` and `runs/` directory back to the repo.
