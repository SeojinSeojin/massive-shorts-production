# yt-auto

Automated pipeline that renders pre-generated HTML cards into YouTube Shorts and posts them on a schedule. Content is organized per "topic" (currently `saju`, Korean fortune-telling cards). You author the visual cards as standalone HTML files (e.g. locally with Claude Code); the pipeline turns each into a 1080x1920 video with headless Chromium + ffmpeg and uploads it via the YouTube Data API.

## How it works

You drop standalone HTML cards into `topics/<topic>/cards/`. Each run, [app.py](app.py) picks the oldest card that hasn't been posted yet and produces + uploads it:

1. **Queue** ([pipeline/card_queue.py](pipeline/card_queue.py))
   The `cards/` folder is the source of truth for *what* to post; `topics/<topic>/queue.json` is the ledger of *what has already been posted*. Any `.html` file in `cards/` not yet recorded in `queue.json` is "pending". Cards are processed oldest-first (by filename).

2. **Produce** ([pipeline/media_pipeline.py](pipeline/media_pipeline.py), [pipeline/audio_fetcher.py](pipeline/audio_fetcher.py), [pipeline/youtube_upload.py](pipeline/youtube_upload.py))
   - Screenshots the card HTML to a 1080x1920 PNG via Playwright.
   - Fetches background audio (Pixabay API, a local folder, or none).
   - Composites image + audio into an MP4 with ffmpeg.
   - Uploads the MP4 as a YouTube Short via OAuth, then records the card + `video_id` in `queue.json`.

### Card format

Each card is a self-contained HTML file (360x640 viewport, rendered at 3x). Its YouTube metadata is read from the `<head>`:

```html
<title>오늘의 금전운</title>                                <!-- video title -->
<meta name="description" content="사주로 보는 오늘의 재물운">   <!-- description -->
<meta name="tags" content="사주, 운세, 금전운, 오늘의운세">      <!-- comma-separated tags -->
```

`topics/<topic>/config.yaml` applies a `title_suffix`, `description_footer`, category, and privacy on top. [templates/card_style_a](templates/card_style_a) is kept as a reference layout you can copy when authoring cards.

## Directory structure

```
app.py                        CLI entrypoint (run / auth)
pipeline/
  card_queue.py               Card discovery + queue.json ledger + <head> metadata parsing
  media_pipeline.py           HTML → PNG (Playwright) → MP4 (ffmpeg)
  audio_fetcher.py            Background music (Pixabay / local / none)
  youtube_upload.py           OAuth + YouTube Data API upload
templates/
  card_style_a/               Reference card layout
topics/
  saju/
    config.yaml               Per-topic settings (paths, audio, YouTube metadata)
    cards/                     Pre-generated HTML cards you author
    queue.json                Ledger of already-posted cards
reference/                     Superseded v1 implementation, kept for history
.github/workflows/post-shorts.yml   Scheduled GitHub Actions runner
```

## Adding a new topic/channel

Topics are discovered automatically — the workflow scans `topics/` and runs one job per folder that contains a `config.yaml`. No workflow edit is needed.

1. Create `topics/<slug>/config.yaml` and a `cards/` folder (copy `topics/saju` as a starting point).
2. Add three repo secrets following the `<SLUG>_YOUTUBE_*` convention (uppercase the folder name):
   `<SLUG>_YOUTUBE_CLIENT_ID`, `<SLUG>_YOUTUBE_CLIENT_SECRET`, `<SLUG>_YOUTUBE_TOKEN_JSON`.

   e.g. for `topics/mbti/` → `MBTI_YOUTUBE_CLIENT_ID`, `MBTI_YOUTUBE_CLIENT_SECRET`, `MBTI_YOUTUBE_TOKEN_JSON`.

If a topic folder exists but its secrets are missing, only that topic's job fails (`fail-fast: false` keeps the others running).

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
brew install ffmpeg   # or apt-get install ffmpeg
```

### Environment variables

| Variable | Required for | Notes |
|---|---|---|
| `PIXABAY_API_KEY` | produce | only if a topic's `production.audio.mode` is `pixabay` |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | produce, auth | OAuth client credentials (Google Cloud Console) |
| `OAUTH_TOKEN_PATH` | produce, auth | where the OAuth token is read/written; defaults to `token.json` |
| `DRY_RUN` | produce | `true` builds the MP4 but skips the YouTube upload (and the queue ledger) |

### One-time YouTube auth

```bash
python app.py --auth
```
Runs the OAuth consent flow locally and saves the token to `OAUTH_TOKEN_PATH`. Copy this token's contents into the topic's `YOUTUBE_TOKEN_JSON_*` GitHub secret for CI use.

## Usage

```bash
# Post the next pending card for a topic
python app.py --topic saju

# Post the next 3 pending cards
python app.py --topic saju --count 3

# Build the video without uploading or recording it
DRY_RUN=true python app.py --topic saju
```

## Automation

[.github/workflows/post-shorts.yml](.github/workflows/post-shorts.yml) runs daily at 09:00 UTC. A `discover` job scans `topics/` and builds the job matrix automatically (one job per folder with a `config.yaml`); the `post` job then fans out across them (`fail-fast: false`, so one topic failing doesn't block the others). It can also be triggered manually (`workflow_dispatch`) with an optional single-topic filter, a per-topic card count, and a dry-run flag. On success each job commits its updated `queue.json` back to the repo.
