"""Card queue: the filesystem is the source of truth for *what* to post,
queue.json is the ledger of *what has already been posted*.

- Cards are standalone HTML files in topics/<topic>/cards/.
- Each card carries its YouTube metadata in <head>:
    <title>...</title>
    <meta name="description" content="...">
    <meta name="tags" content="tag1, tag2, tag3">
- A card is "pending" when its filename is not yet recorded in queue.json.
"""

import json
from html.parser import HTMLParser
from pathlib import Path


def load_queue(path: Path) -> dict:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("processed", [])
        return data
    return {"processed": []}


def save_queue(path: Path, queue: dict) -> None:
    path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


def processed_files(queue: dict) -> set[str]:
    return {entry["file"] for entry in queue.get("processed", [])}


def list_pending(cards_dir: Path, queue: dict) -> list[Path]:
    """Return pending card paths, oldest first (sorted by filename)."""
    done = processed_files(queue)
    if not cards_dir.exists():
        return []
    cards = [p for p in cards_dir.glob("*.html") if p.name not in done]
    return sorted(cards, key=lambda p: p.name)


def mark_processed(queue: dict, file_name: str, video_id: str | None, posted_at: str, title: str) -> None:
    queue.setdefault("processed", []).append({
        "file": file_name,
        "video_id": video_id,
        "posted_at": posted_at,
        "title": title,
    })


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.tags = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            a = dict(attrs)
            name = (a.get("name") or "").lower()
            content = a.get("content") or ""
            if name == "description":
                self.description = content
            elif name in ("tags", "keywords"):
                self.tags = content

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def parse_metadata(html_path: Path) -> dict:
    """Extract title, description, and tags from a card's HTML <head>."""
    parser = _MetaParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    tags = [t.strip() for t in parser.tags.split(",") if t.strip()]
    return {
        "title": parser.title.strip(),
        "description": parser.description.strip(),
        "tags": tags,
    }
