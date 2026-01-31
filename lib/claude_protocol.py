from __future__ import annotations

import os
from pathlib import Path

from ccb_protocol import make_req_id
_SKILL_CACHE: str | None = None


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    val = raw.strip().lower()
    if val in {"0", "false", "no", "off"}:
        return False
    if val in {"1", "true", "yes", "on"}:
        return True
    return default


def _load_claude_skills() -> str:
    global _SKILL_CACHE
    if _SKILL_CACHE is not None:
        return _SKILL_CACHE
    if not _env_bool("CCB_CLAUDE_SKILLS", True):
        _SKILL_CACHE = ""
        return _SKILL_CACHE
    skills_dir = Path(__file__).resolve().parent.parent / "claude_skills"
    if not skills_dir.is_dir():
        _SKILL_CACHE = ""
        return _SKILL_CACHE
    parts: list[str] = []
    # Load short skill files (aligned with droid)
    for name in ("ask.md",):
        path = skills_dir / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if text:
            parts.append(text)
    _SKILL_CACHE = "\n\n".join(parts).strip()
    return _SKILL_CACHE


def apply_claude_skills(message: str) -> str:
    message = (message or "").rstrip()
    skills = _load_claude_skills()
    if skills:
        message = f"{skills}\n\n{message}".strip()
    return message


__all__ = [
    "apply_claude_skills",
    "make_req_id",
]
