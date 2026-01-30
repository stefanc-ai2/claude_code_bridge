from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import importlib
from pathlib import Path
from types import SimpleNamespace


def _load_ccb_module(repo_root: Path):
    loader = SourceFileLoader("ccb_launcher", str(repo_root / "ccb"))
    spec = importlib.util.spec_from_loader("ccb_launcher", loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ccb_starts_askd_unmanaged(tmp_path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ccb = _load_ccb_module(repo_root)

    project_root = tmp_path / "proj"
    (project_root / ".ccb_config").mkdir(parents=True)
    monkeypatch.chdir(project_root)

    started: dict = {"ok": False, "env": None}

    def fake_popen(cmd, env=None, **_kwargs):
        started["ok"] = True
        started["env"] = dict(env or {})
        return SimpleNamespace(pid=1234)

    class FakeDaemonModule:
        @staticmethod
        def ping_daemon(*, timeout_s: float = 0.5, state_file=None) -> bool:  # noqa: ARG004
            return bool(started["ok"])

        @staticmethod
        def read_state(*, state_file=None):  # noqa: ARG004
            return {"host": "127.0.0.1", "port": 12345, "managed": False, "parent_pid": None}

    monkeypatch.setattr(ccb.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(importlib, "import_module", lambda _name: FakeDaemonModule)

    launcher = ccb.AILauncher(providers=["codex"])
    launcher._maybe_start_provider_daemon("codex")

    env = started["env"] or {}
    assert env.get("CCB_MANAGED") == "0"
    assert "CCB_PARENT_PID" not in env or not str(env.get("CCB_PARENT_PID") or "").strip()
    assert env.get("CCB_ASKD_IDLE_TIMEOUT_S") == "3600"
    assert env.get("CCB_RUN_DIR")


def test_ccb_reuses_running_askd(tmp_path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ccb = _load_ccb_module(repo_root)

    project_root = tmp_path / "proj"
    (project_root / ".ccb_config").mkdir(parents=True)
    monkeypatch.chdir(project_root)

    popen_calls: list[dict] = []

    def fake_popen(cmd, env=None, **_kwargs):
        popen_calls.append({"cmd": cmd, "env": dict(env or {})})
        return SimpleNamespace(pid=1234)

    class FakeDaemonModule:
        @staticmethod
        def ping_daemon(*, timeout_s: float = 0.5, state_file=None) -> bool:  # noqa: ARG004
            return True

        @staticmethod
        def read_state(*, state_file=None):  # noqa: ARG004
            return {"host": "127.0.0.1", "port": 12345, "managed": False, "parent_pid": None}

    monkeypatch.setattr(ccb.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(importlib, "import_module", lambda _name: FakeDaemonModule)

    launcher = ccb.AILauncher(providers=["codex"])
    launcher._maybe_start_provider_daemon("codex")

    assert popen_calls == []


def test_ccb_cleanup_does_not_shutdown_unowned_askd(tmp_path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ccb = _load_ccb_module(repo_root)

    project_root = tmp_path / "proj"
    (project_root / ".ccb_config").mkdir(parents=True)
    monkeypatch.chdir(project_root)

    launcher = ccb.AILauncher(providers=["codex"])

    shutdown_calls: list[tuple] = []

    monkeypatch.setattr(ccb, "_cleanup_tmpclaude_artifacts", lambda *a, **k: None)
    monkeypatch.setattr(ccb, "_cleanup_stale_runtime_dirs", lambda *a, **k: None)
    monkeypatch.setattr(ccb, "_shrink_ccb_logs", lambda *a, **k: 0)

    askd_state = tmp_path / "askd.json"
    monkeypatch.setattr(ccb, "state_file_path", lambda _name: askd_state)
    monkeypatch.setattr(ccb, "read_state", lambda _path: {"managed": True, "parent_pid": launcher.ccb_pid + 999})
    monkeypatch.setattr(ccb, "shutdown_daemon", lambda *args, **kwargs: shutdown_calls.append((args, kwargs)))

    launcher.cleanup(kill_panes=False, clear_sessions=False, remove_runtime=False, quiet=True)
    assert shutdown_calls == []


def test_ccb_cleanup_shutdowns_owned_askd(tmp_path, monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ccb = _load_ccb_module(repo_root)

    project_root = tmp_path / "proj"
    (project_root / ".ccb_config").mkdir(parents=True)
    monkeypatch.chdir(project_root)

    launcher = ccb.AILauncher(providers=["codex"])

    shutdown_calls: list[tuple] = []

    monkeypatch.setattr(ccb, "_cleanup_tmpclaude_artifacts", lambda *a, **k: None)
    monkeypatch.setattr(ccb, "_cleanup_stale_runtime_dirs", lambda *a, **k: None)
    monkeypatch.setattr(ccb, "_shrink_ccb_logs", lambda *a, **k: 0)

    askd_state = tmp_path / "askd.json"
    monkeypatch.setattr(ccb, "state_file_path", lambda _name: askd_state)
    monkeypatch.setattr(ccb, "read_state", lambda _path: {"managed": True, "parent_pid": launcher.ccb_pid})
    monkeypatch.setattr(ccb, "shutdown_daemon", lambda *args, **kwargs: shutdown_calls.append((args, kwargs)))

    launcher.cleanup(kill_panes=False, clear_sessions=False, remove_runtime=False, quiet=True)
    assert len(shutdown_calls) == 1
