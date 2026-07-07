import json
import os
import re
from pathlib import Path

import anthropic


def _load_kb(kb_path: Path) -> str:
    parts = []
    for p in sorted(kb_path.iterdir()):
        if p.suffix in {".md", ".txt", ".json"} and p.is_file():
            parts.append(f"### {p.name}\n{p.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1).strip())
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"Could not extract JSON from Claude response:\n{text[:400]}")


def build_plan(cfg: dict) -> dict:
    """Call Claude with the topic KB + history and return a structured plan dict."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    kb_text = _load_kb(Path(cfg["kb_path"]))

    history_path = Path(cfg["history_path"])
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    lookback: int = cfg.get("planning", {}).get("history_lookback", 30)
    recent = [{"title": e["title"], "angle": e["angle"]} for e in history[-lookback:]]

    system_prompt = Path(cfg["planning_prompt_path"]).read_text(encoding="utf-8")

    user_msg = f"""## Knowledge Base
{kb_text}

## Recent Post History (avoid repeating these titles or angles)
{json.dumps(recent, ensure_ascii=False, indent=2)}

## Output Format
Return ONLY a JSON object — no prose, no markdown fences:
{{
  "title": "...",            // card headline, ≤25 chars, Korean OK
  "hook": "...",             // 1-sentence hook for YouTube description
  "angle": "...",            // conceptual angle label (used for deduplication)
  "body_points": ["..."],    // 3-5 strings for the card body
  "tags": ["..."],           // 5-8 YouTube tags, no # prefix
  "variant": "numbered_list" // one of: numbered_list | accent_line | grid | full_bleed
}}"""

    planning_cfg = cfg.get("planning", {})
    message = client.messages.create(
        model=planning_cfg.get("model", "claude-opus-4-8"),
        max_tokens=planning_cfg.get("max_tokens", 1024),
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )

    return _extract_json(message.content[0].text)
