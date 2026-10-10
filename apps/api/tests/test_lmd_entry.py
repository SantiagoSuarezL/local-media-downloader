"""Phase 16/17: the frozen entrypoint must honor ``exe -m yt_dlp ...``.

The backend spawns yt-dlp as ``sys.executable -m yt_dlp`` (adapter and health
probes share ``yt_dlp_argv()``). A PyInstaller bootloader ignores ``-m``, so
without the runpy dispatch the frozen exe boots a NESTED SERVER on the same
port instead of yt-dlp: probes time out, downloads hang, orphans fight over
the port. These tests pin the dispatch without spawning anything: ``runpy``
is stubbed, ``sys.frozen`` is faked.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ENTRY = Path(__file__).resolve().parent.parent / "lmd_entry.py"


def _load_entry(monkeypatch: pytest.MonkeyPatch):
    """Import the shim by file path (it lives outside the src layout)."""
    monkeypatch.delitem(sys.modules, "lmd_entry", raising=False)
    spec = importlib.util.spec_from_file_location("lmd_entry", _ENTRY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["lmd_entry"] = module
    spec.loader.exec_module(module)
    return module


def _freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)


def test_frozen_minus_m_ytdlp_delegates_to_runpy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _freeze(monkeypatch)
    # Pin argv: the dispatch rebinds the real sys.argv (mirroring `python -m`),
    # and monkeypatch restores it afterwards.
    monkeypatch.setattr(sys, "argv", ["app.exe"])
    calls: list[tuple[str, str | None, bool]] = []
    seen_argv: list[list[str]] = []

    def _stub(name: str, run_name: str | None = None, alter_sys: bool = False) -> None:
        calls.append((name, run_name, alter_sys))
        seen_argv.append(list(sys.argv))

    monkeypatch.setattr("runpy.run_module", _stub)
    module = _load_entry(monkeypatch)
    assert module._run_bundled_module(["app.exe", "-m", "yt_dlp", "--version"]) is True
    assert calls == [("yt_dlp", "__main__", True)]
    # The `-m yt_dlp` prefix is stripped first, mirroring `python -m`.
    assert seen_argv == [["app.exe", "--version"]]


def test_frozen_server_argv_falls_through_to_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _freeze(monkeypatch)
    called = False

    def _fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True

    monkeypatch.setattr("runpy.run_module", _fail)
    module = _load_entry(monkeypatch)
    assert module._run_bundled_module(["app.exe"]) is False
    assert called is False


def test_frozen_other_module_falls_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _freeze(monkeypatch)
    called = False

    def _fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True

    monkeypatch.setattr("runpy.run_module", _fail)
    module = _load_entry(monkeypatch)
    assert module._run_bundled_module(["app.exe", "-m", "http.server"]) is False
    assert called is False


def test_unfrozen_never_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    called = False

    def _fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal called
        called = True

    monkeypatch.setattr("runpy.run_module", _fail)
    module = _load_entry(monkeypatch)
    assert module._run_bundled_module(["python", "-m", "yt_dlp", "--version"]) is False
    assert called is False
