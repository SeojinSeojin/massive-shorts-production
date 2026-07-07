import os
import random
import tempfile

import ffmpeg

try:
    ffmpeg.probe.__module__
    import subprocess
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg binary not found. Install it via: brew install ffmpeg")
except FileNotFoundError:
    raise RuntimeError("ffmpeg binary not found. Install it via: brew install ffmpeg")


def render_html_to_png(html_path: str) -> str:
    """Render an HTML file to a 1080x1920 PNG using Playwright headless Chromium.
    Returns path to a temp PNG file. Caller is responsible for deleting it.
    """
    from playwright.sync_api import sync_playwright

    if not os.path.exists(html_path):
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    fd, output_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # device_scale_factor=3 renders the 360x640 card at 1080x1920 natively
        page = browser.new_page(
            viewport={"width": 360, "height": 640},
            device_scale_factor=3,
        )
        page.goto(f"file://{os.path.abspath(html_path)}", wait_until="load", timeout=30000)
        page.screenshot(path=output_path, full_page=False)
        browser.close()

    return output_path


def build_short(image_path: str, audio_dir: str, duration_secs: int = 7, audio_path: str | None = None) -> str:
    """
    Build a 1080x1920 MP4 Short from a still image + audio.
    audio_path takes priority over audio_dir; if neither has audio the video is silent.
    Returns the path to a temp MP4 file. Caller is responsible for deleting it.
    Raises FileNotFoundError if image_path does not exist.
    Raises RuntimeError if ffmpeg is not installed.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    audio_extensions = {".mp3", ".wav", ".m4a"}
    if audio_path and os.path.exists(audio_path):
        audio_files = [audio_path]
    else:
        audio_files = []
        if audio_dir and os.path.isdir(audio_dir):
            audio_files = [
                os.path.join(audio_dir, f)
                for f in os.listdir(audio_dir)
                if os.path.splitext(f)[1].lower() in audio_extensions
            ]

    fd, output_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)

    video = (
        ffmpeg
        .input(image_path, loop=1, t=duration_secs, framerate=30)
        .filter("scale", 1080, 1920, force_original_aspect_ratio="decrease")
        .filter("pad", 1080, 1920, "(ow-iw)/2", "(oh-ih)/2", color="black")
        .filter("setsar", "1")
    )

    if audio_files:
        chosen = random.choice(audio_files)
        audio = ffmpeg.input(chosen, stream_loop=-1, t=duration_secs).audio
        stream = ffmpeg.output(
            video,
            audio,
            output_path,
            vcodec="libx264",
            acodec="aac",
            pix_fmt="yuv420p",
            t=duration_secs,
            shortest=None,
        )
    else:
        stream = ffmpeg.output(
            video,
            output_path,
            vcodec="libx264",
            pix_fmt="yuv420p",
            t=duration_secs,
        )

    try:
        ffmpeg.run(stream, overwrite_output=True, capture_stderr=True)
    except ffmpeg.Error as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        raise RuntimeError(f"ffmpeg failed:\n{stderr}") from e

    return output_path
