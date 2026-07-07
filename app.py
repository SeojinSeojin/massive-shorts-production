import argparse
import json
import logging
import os
from datetime import date
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _load_config(topic: str) -> dict:
    path = Path("topics") / topic / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _runs_dir(topic: str) -> Path:
    d = Path("topics") / topic / "runs" / date.today().isoformat()
    d.mkdir(parents=True, exist_ok=True)
    return d


def phase_plan(topic: str, cfg: dict) -> Path:
    plan_path = _runs_dir(topic) / "plan.json"

    if plan_path.exists():
        log.info("Plan already exists at %s — skipping re-plan", plan_path)
        return plan_path

    from pipeline.planner import build_plan

    plan = build_plan(cfg)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Plan written to %s", plan_path)

    history_path = Path(cfg["history_path"])
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    history.append({
        "date": date.today().isoformat(),
        "video_id": None,
        "title": plan["title"],
        "angle": plan.get("angle", ""),
    })
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    return plan_path


def phase_produce(topic: str, cfg: dict, plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    from pipeline.renderer import render_plan_to_html
    from pipeline.media_pipeline import render_html_to_png, build_short
    from pipeline.audio_fetcher import fetch_audio
    from pipeline.youtube_upload import upload_short

    tmp_html = tmp_png = tmp_mp4 = tmp_audio = None

    try:
        tmp_html = render_plan_to_html(plan, cfg)

        audio_cfg = cfg.get("production", {}).get("audio", {})
        mode = audio_cfg.get("mode", "none")
        if mode == "pixabay":
            tmp_audio = fetch_audio(mode="pixabay", genre=audio_cfg.get("genre", "ambient"))
        elif mode == "local":
            tmp_audio = fetch_audio(mode="local", local_path=audio_cfg.get("local_path", ""))
        # mode == "none": tmp_audio stays None

        tmp_png = render_html_to_png(tmp_html)
        duration = cfg.get("production", {}).get("short_duration_secs", 7)
        tmp_mp4 = build_short(tmp_png, None, duration, audio_path=tmp_audio)

        if os.environ.get("DRY_RUN", "false").lower() == "true":
            log.info("DRY_RUN: built %s — skipping upload", tmp_mp4)
            return

        yt = cfg.get("youtube", {})
        title = (plan["title"] + yt.get("title_suffix", " #Shorts"))[:100]
        description = plan.get("hook", "") + yt.get("description_footer", "")

        video_id = upload_short(
            tmp_mp4,
            title,
            description,
            tags=plan.get("tags", []),
            category_id=yt.get("category_id", "22"),
            privacy=yt.get("privacy", "public"),
            made_for_kids=yt.get("made_for_kids", False),
        )

        # Write video_id back into today's plan.json
        plan["video_id"] = video_id
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        # Backfill video_id into history (most recent matching entry)
        history_path = Path(cfg["history_path"])
        history = json.loads(history_path.read_text(encoding="utf-8"))
        for entry in reversed(history):
            if entry["title"] == plan["title"] and entry["video_id"] is None:
                entry["video_id"] = video_id
                break
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

        log.info("Uploaded '%s' → video_id=%s", plan["title"], video_id)

    finally:
        for tmp in (tmp_html, tmp_png, tmp_mp4, tmp_audio):
            if tmp and os.path.exists(tmp):
                os.remove(tmp)


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Shorts auto-poster")
    parser.add_argument("--topic", required=True, help="Topic slug (matches topics/<topic>/)")
    parser.add_argument(
        "--phase",
        choices=["plan", "produce", "all"],
        default="all",
        help="plan=Claude only, produce=render+upload only, all=both",
    )
    parser.add_argument("--auth", action="store_true", help="Run YouTube OAuth consent flow")
    args = parser.parse_args()

    if args.auth:
        from pipeline.youtube_upload import run_auth_flow
        run_auth_flow()
        return

    cfg = _load_config(args.topic)

    if args.phase in ("plan", "all"):
        plan_path = phase_plan(args.topic, cfg)
    else:
        plan_path = _runs_dir(args.topic) / "plan.json"
        if not plan_path.exists():
            log.error("No plan.json at %s — run --phase plan first", plan_path)
            raise SystemExit(1)

    if args.phase in ("produce", "all"):
        phase_produce(args.topic, cfg, plan_path)


if __name__ == "__main__":
    main()
