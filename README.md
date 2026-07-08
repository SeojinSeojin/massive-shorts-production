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

`topics/<topic>/config.yaml` applies a `title_suffix`, `description_footer`, category, and privacy on top. The [templates/](templates/) directory holds reference layouts you can copy when authoring cards — each is a 360×640 mobile card with three body variants (`numbered_list`, `accent_line`, `grid`):

- [card_style_a](templates/card_style_a) — dark neon-purple glow
- [card_style_b](templates/card_style_b) — warm cream paper, ink serif
- [card_style_c](templates/card_style_c) — bright sunset gradient, frosted glass
- [card_style_d](templates/card_style_d) — near-black mono editorial with an amber accent

The cards fill from the top down, so **fullness comes from content, not spacing** — write ~5 substantive body points of roughly 1–2 lines each. A card with only 2–3 short points will look empty; give each point real detail.

## Directory structure

```
app.py                        CLI entrypoint (run / auth)
pipeline/
  card_queue.py               Card discovery + queue.json ledger + <head> metadata parsing
  media_pipeline.py           HTML → PNG (Playwright) → MP4 (ffmpeg)
  audio_fetcher.py            Background music (Pixabay / local / none)
  youtube_upload.py           OAuth + YouTube Data API upload
templates/
  card_style_a/               Reference card layout — dark neon
  card_style_b/               Reference card layout — warm paper
  card_style_c/               Reference card layout — sunset gradient
  card_style_d/               Reference card layout — mono editorial
topics/
  saju/
    config.yaml               Per-topic settings (paths, audio, YouTube metadata)
    cards/                     Pre-generated HTML cards you author
    queue.json                Ledger of already-posted cards
reference/                     Superseded v1 implementation, kept for history
.github/workflows/post-shorts.yml   Scheduled GitHub Actions runner
```

## Adding a new topic/channel

Topics are discovered automatically — the workflow scans `topics/` and runs one job per folder that contains a `config.yaml`. No workflow edit is needed. Below is a full walkthrough for adding an **`mbti`** channel.

### 1. Scaffold the folder

Copy `saju` as a starting point, then clear the example's cards and ledger:

```bash
cp -r topics/saju topics/mbti
rm -f topics/mbti/cards/*.html
echo '{ "processed": [] }' > topics/mbti/queue.json
```

Edit `topics/mbti/config.yaml` for the new channel — at minimum the identity and paths:

```yaml
topic: "MBTI"
channel_name: "mbti_daily"
cards_dir: "./topics/mbti/cards"
queue_path: "./topics/mbti/queue.json"

youtube:
  title_suffix: " #Shorts"
  description_footer: "\n\n#Shorts #MBTI #성격유형 #심리테스트"
  category_id: "22"
  privacy: "public"
  made_for_kids: false
```

### 2. Generate the cards with Claude Code

Cards are just standalone HTML files. Open Claude Code in this repo and ask it to author them — point it at the reference layout so the style stays consistent. For example:

> Look at `templates/card_style_a/index.html.j2` for the visual style (dark 360×640 vertical card, neon-purple glow, Korean web fonts). Create 5 standalone HTML cards in `topics/mbti/cards/`, one per file named `2026-07-10-<slug>.html`. Each card is a self-contained HTML file (all CSS inlined, no Jinja) about a fun MBTI insight. In each file's `<head>` put:
> - `<title>` — the video title (≤ 25 chars, Korean OK)
> - `<meta name="description">` — a one-line hook
> - `<meta name="tags" content="...">` — 5–8 comma-separated tags, no `#`
>
> Keep the body to a punchy headline plus 3–4 short points so it reads in ~7 seconds.

Claude Code writes the files directly into `topics/mbti/cards/`. Preview one in a browser, or dry-run the render without uploading:

```bash
DRY_RUN=true python app.py --topic mbti
```

Filenames are processed oldest-first, so a date prefix (`2026-07-10-...`) controls posting order.

### 3. Add the channel's secrets

Add three repo secrets following the `<SLUG>_YOUTUBE_*` convention (uppercase the folder name):

- `MBTI_YOUTUBE_CLIENT_ID`
- `MBTI_YOUTUBE_CLIENT_SECRET`
- `MBTI_YOUTUBE_TOKEN_JSON`

Generate the token by running the [one-time auth flow](#one-time-youtube-auth) with the `mbti` OAuth client, then paste `token.json`'s contents into `MBTI_YOUTUBE_TOKEN_JSON`.

### 4. Commit

```bash
git add topics/mbti && git commit -m "feat(mbti): add channel"
```

The next scheduled (or manual) run picks up `mbti` automatically. If a topic folder exists but its secrets are missing, only that topic's job fails (`fail-fast: false` keeps the others running).

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
Runs the OAuth consent flow locally and saves the token to `OAUTH_TOKEN_PATH`. Copy this token's contents into the topic's `<SLUG>_YOUTUBE_TOKEN_JSON` GitHub secret for CI use.

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
