import argparse
import logging
import os
from datetime import date
from pathlib import Path

import yaml

from pipeline.card_queue import (
    list_pending,
    load_queue,
    mark_processed,
    parse_metadata,
    save_queue,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _load_config(topic: str) -> dict:
    path = Path("topics") / topic / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _cards_dir(topic: str, cfg: dict) -> Path:
    return Path(cfg.get("cards_dir", f"./topics/{topic}/cards"))


def _queue_path(topic: str, cfg: dict) -> Path:
    return Path(cfg.get("queue_path", f"./topics/{topic}/queue.json"))


def process_card(card_path: Path, cfg: dict) -> str | None:
    """Render one pre-generated HTML card into a Short and upload it.
    Returns the uploaded video_id, or None on DRY_RUN."""
    from pipeline.media_pipeline import render_html_to_png, build_short
    from pipeline.audio_fetcher import fetch_audio
    from pipeline.youtube_upload import upload_short

    meta = parse_metadata(card_path)
    if not meta["title"]:
        raise ValueError(f"Card {card_path.name} has no <title> — cannot derive a video title")

    tmp_png = tmp_mp4 = tmp_audio = None
    try:
        audio_cfg = cfg.get("production", {}).get("audio", {})
        mode = audio_cfg.get("mode", "none")
        if mode == "pixabay":
            tmp_audio = fetch_audio(mode="pixabay", genre=audio_cfg.get("genre", "ambient"))
        elif mode == "local":
            tmp_audio = fetch_audio(mode="local", local_path=audio_cfg.get("local_path", ""))

        tmp_png = render_html_to_png(str(card_path))
        duration = cfg.get("production", {}).get("short_duration_secs", 7)
        tmp_mp4 = build_short(tmp_png, None, duration, audio_path=tmp_audio)

        if os.environ.get("DRY_RUN", "false").lower() == "true":
            log.info("DRY_RUN: built %s from %s — skipping upload", tmp_mp4, card_path.name)
            return None

        yt = cfg.get("youtube", {})
        title = (meta["title"] + yt.get("title_suffix", " #Shorts"))[:100]
        description = meta["description"] + yt.get("description_footer", "")

        video_id = upload_short(
            tmp_mp4,
            title,
            description,
            tags=meta["tags"],
            category_id=yt.get("category_id", "22"),
            privacy=yt.get("privacy", "public"),
            made_for_kids=yt.get("made_for_kids", False),
        )
        log.info("Uploaded '%s' → video_id=%s", title, video_id)
        return video_id
    finally:
        for tmp in (tmp_png, tmp_mp4, tmp_audio):
            if tmp and os.path.exists(tmp):
                os.remove(tmp)


def run(topic: str, cfg: dict, count: int) -> None:
    cards_dir = _cards_dir(topic, cfg)
    queue_path = _queue_path(topic, cfg)
    queue = load_queue(queue_path)

    pending = list_pending(cards_dir, queue)
    if not pending:
        log.info("No pending cards in %s — nothing to post", cards_dir)
        return

    dry_run = os.environ.get("DRY_RUN", "false").lower() == "true"

    for card_path in pending[:count]:
        log.info("Processing card: %s", card_path.name)
        video_id = process_card(card_path, cfg)

        if dry_run:
            continue

        meta = parse_metadata(card_path)
        mark_processed(queue, card_path.name, video_id, date.today().isoformat(), meta["title"])
        save_queue(queue_path, queue)
        log.info("Recorded %s in %s", card_path.name, queue_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Shorts auto-poster (HTML card queue)")
    parser.add_argument("--topic", required=True, help="Topic slug (matches topics/<topic>/)")
    parser.add_argument("--count", type=int, default=1, help="How many pending cards to post this run")
    parser.add_argument("--auth", action="store_true", help="Run YouTube OAuth consent flow")
    args = parser.parse_args()

    if args.auth:
        from pipeline.youtube_upload import run_auth_flow
        run_auth_flow()
        return

    cfg = _load_config(args.topic)
    run(args.topic, cfg, args.count)


if __name__ == "__main__":
    main()
