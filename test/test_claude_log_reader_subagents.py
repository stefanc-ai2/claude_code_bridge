from __future__ import annotations

import json
import os
import time
from pathlib import Path

from claude_comm import ClaudeLogReader


def _write_message(path: Path, *, role: str, text: str, ts: str) -> None:
    entry = {
        "type": role,
        "timestamp": ts,
        "message": {"role": role, "content": [{"type": "text", "text": text}]},
    }
    path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")


def test_latest_message_reads_subagent_logs(tmp_path, monkeypatch) -> None:
    # Ensure ClaudeLogReader candidate project dirs use our tmp work_dir, not the repo PWD.
    work_dir = tmp_path / "repo"
    work_dir.mkdir()
    monkeypatch.setenv("PWD", str(work_dir))

    projects_root = tmp_path / "claude-projects"
    projects_root.mkdir()

    reader = ClaudeLogReader(root=projects_root, work_dir=work_dir, use_sessions_index=False)
    project_dir = reader._project_dir()
    project_dir.mkdir(parents=True, exist_ok=True)

    session = project_dir / "sess.jsonl"
    # Main session contains an older assistant message.
    _write_message(session, role="assistant", text="old", ts="2026-01-30T00:00:00Z")

    # Subagent log contains a newer assistant message.
    subagent_dir = project_dir / session.stem / "subagents"
    subagent_dir.mkdir(parents=True, exist_ok=True)
    subagent = subagent_dir / "agent-1.jsonl"
    _write_message(subagent, role="assistant", text="new", ts="2026-01-30T00:00:10Z")

    now = time.time()
    os.utime(session, (now - 10, now - 10))
    os.utime(subagent, (now, now))

    assert reader.latest_message() == "new"

