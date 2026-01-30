from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path


def _load_hook_script(repo_root: Path):
    loader = SourceFileLoader("ccb_completion_hook", str(repo_root / "bin" / "ccb-completion-hook"))
    spec = importlib.util.spec_from_loader("ccb_completion_hook", loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_completion_hook_codex_defaults_to_summary(monkeypatch, tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    hook = _load_hook_script(repo_root)

    monkeypatch.delenv("CCB_COMPLETION_HOOK_RESULT_MODE", raising=False)

    msg = hook.format_completion_message(
        provider_display="Claude",
        provider="claude",
        req_id="abc",
        output_file=None,
        reply="SECRET_REPLY",
        caller="codex",
    )
    assert "Result: SECRET_REPLY" not in msg
    assert "Result: (suppressed; run `pend claude`)" in msg


def test_completion_hook_claude_defaults_to_summary(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    hook = _load_hook_script(repo_root)

    monkeypatch.delenv("CCB_COMPLETION_HOOK_RESULT_MODE", raising=False)

    msg = hook.format_completion_message(
        provider_display="Codex",
        provider="codex",
        req_id="abc",
        output_file=None,
        reply="THE_REPLY",
        caller="claude",
    )
    assert "Result: THE_REPLY" not in msg
    assert "Result: (suppressed; run `pend codex`)" in msg


def test_completion_hook_env_override_full(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    hook = _load_hook_script(repo_root)

    monkeypatch.setenv("CCB_COMPLETION_HOOK_RESULT_MODE", "full")

    msg = hook.format_completion_message(
        provider_display="Claude",
        provider="claude",
        req_id="abc",
        output_file=None,
        reply="VISIBLE_REPLY",
        caller="codex",
    )
    assert "Result: VISIBLE_REPLY" in msg


def test_completion_hook_env_override_none(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    hook = _load_hook_script(repo_root)

    monkeypatch.setenv("CCB_COMPLETION_HOOK_RESULT_MODE", "none")

    assert hook._result_mode_for_caller("codex") == "none"


def test_completion_hook_main_exits_early_for_none(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    hook = _load_hook_script(repo_root)

    monkeypatch.setenv("CCB_COMPLETION_HOOK_ENABLED", "1")
    monkeypatch.setenv("CCB_COMPLETION_HOOK_RESULT_MODE", "none")

    class _FakeStdin:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(hook, "sys", hook.sys)
    monkeypatch.setattr(hook.sys, "stdin", _FakeStdin())
    monkeypatch.setattr(
        hook.sys,
        "argv",
        [
            "ccb-completion-hook",
            "--provider",
            "codex",
            "--caller",
            "claude",
            "--req-id",
            "abc",
        ],
    )

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("unexpected side effect")

    monkeypatch.setattr(hook, "send_via_terminal", _unexpected)
    monkeypatch.setattr(hook, "find_ask_command", _unexpected)

    assert hook.main() == 0
