import hashlib
import os
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_HEADER_FONTS = ["Black Han Sans", "Gasoek One", "Gugi"]


def render_plan_to_html(plan: dict, cfg: dict) -> str:
    """Render plan JSON into a temp HTML file using the configured Jinja2 template.
    Returns the temp file path. Caller must delete it."""
    template_name = cfg.get("template", "card_style_a")
    template_dir = Path("templates") / template_name

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
    )
    template = env.get_template("index.html.j2")

    # Deterministic font rotation per title so it's stable across retries
    font_idx = int(hashlib.md5(plan["title"].encode()).hexdigest(), 16) % len(_HEADER_FONTS)

    html = template.render(
        title=plan["title"],
        hook=plan.get("hook", ""),
        body_points=plan.get("body_points", []),
        tags=plan.get("tags", []),
        variant=plan.get("variant", "numbered_list"),
        header_font=_HEADER_FONTS[font_idx],
    )

    fd, tmp_path = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    Path(tmp_path).write_text(html, encoding="utf-8")
    return tmp_path
