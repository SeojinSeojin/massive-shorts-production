import json
import os
import random
import tempfile
import urllib.parse
import urllib.request

_PIXABAY_MUSIC_API = "https://pixabay.com/api/music/"
_AUDIO_EXTS = {".mp3", ".wav", ".m4a"}


def fetch_audio(
    mode: str,
    genre: str = "ambient",
    local_path: str = "",
) -> str | None:
    """Return a path to an audio file, or None for silent mode.

    mode: "pixabay" | "local" | "none"
    """
    if mode == "pixabay":
        return _fetch_pixabay(genre)
    if mode == "local":
        return _pick_local(local_path)
    return None


def _fetch_pixabay(genre: str) -> str:
    api_key = os.environ["PIXABAY_API_KEY"]
    params = urllib.parse.urlencode({"key": api_key, "q": genre, "per_page": 20})
    req = urllib.request.Request(
        f"{_PIXABAY_MUSIC_API}?{params}",
        headers={"User-Agent": "yt-auto/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    hits = data.get("hits", [])
    if not hits:
        raise RuntimeError(f"No Pixabay tracks found for genre '{genre}'")

    track = random.choice(hits)
    # Pixabay music API returns audio URLs under different keys depending on version
    audio_url = (
        track.get("audio")
        or track.get("download_url")
        or track.get("mp3_url")
        or track.get("preview_url")
    )
    if not audio_url:
        raise RuntimeError(f"Pixabay track missing download URL: {list(track.keys())}")

    fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    urllib.request.urlretrieve(audio_url, tmp_path)
    return tmp_path


def _pick_local(local_path: str) -> str | None:
    if not local_path or not os.path.isdir(local_path):
        return None
    files = [
        os.path.join(local_path, f)
        for f in os.listdir(local_path)
        if os.path.splitext(f)[1].lower() in _AUDIO_EXTS
    ]
    return random.choice(files) if files else None
