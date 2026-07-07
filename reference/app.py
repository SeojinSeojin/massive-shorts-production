import json
import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_here = os.path.dirname(os.path.abspath(__file__))
ITEMS_JSON = os.environ.get("ITEMS_JSON", os.path.join(_here, "../saju-posts/queue.json"))
_POSTS_DIR = os.path.dirname(os.path.abspath(ITEMS_JSON))
AUDIO_DIR = os.environ.get("AUDIO_DIR", os.path.join(_here, "audio"))
SHORT_DURATION_SECS = int(os.environ.get("SHORT_DURATION_SECS", "7"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"


def _load_queue() -> list[dict]:
    with open(ITEMS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_queue(items: list[dict]) -> None:
    with open(ITEMS_JSON, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def main() -> None:
    items = _load_queue()
    item = next((i for i in sorted(items, key=lambda x: x["id"]) if i["status"] == "pending"), None)

    if item is None:
        log.info("All items posted.")
        return

    html_path = os.path.join(_POSTS_DIR, item["filename"])
    tmp_png = None
    tmp_mp4 = None
    tmp_audio = None
    try:
        from media_pipeline import render_html_to_png, build_short
        from audio_fetcher import fetch_random_track

        try:
            tmp_audio = fetch_random_track(genre="ambient")
            log.info("Fetched Pixabay audio: %s", tmp_audio)
        except Exception:
            log.warning("Could not fetch Pixabay audio — falling back to local dir", exc_info=True)

        tmp_png = render_html_to_png(html_path)
        tmp_mp4 = build_short(tmp_png, AUDIO_DIR, SHORT_DURATION_SECS, audio_path=tmp_audio)

        if DRY_RUN:
            log.info("DRY_RUN: built %s for item %s — %s", tmp_mp4, item["id"], item["topic"])
            return

        from youtube_upload import upload_short
        title = (item["topic"] + " #Shorts")[:100]
        description = item["topic"] + "\n\n#Shorts #사주 #운명"
        video_id = upload_short(tmp_mp4, title, description)

        for i in items:
            if i["id"] == item["id"]:
                i["status"] = "posted"
                i["posted_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                break
        _save_queue(items)

        log.info("Posted item %s → video %s", item["id"], video_id)

    finally:
        for tmp in (tmp_png, tmp_mp4, tmp_audio):
            if tmp and os.path.exists(tmp):
                os.remove(tmp)


if __name__ == "__main__":
    if "--auth" in sys.argv:
        from youtube_upload import run_auth_flow
        run_auth_flow()
    else:
        main()
