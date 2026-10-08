"""Phase 16: bundled-binary resolution order and frozen web-dist default.

The packaged app (PyInstaller onedir) must prefer the ``bin/`` directory next
to the executable over development locations, and must find the bundled web UI
without ``LMD_WEB_DIST``. None of these tests touch the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from local_media_downloader.adapters import tool_paths
from local_media_downloader.adapters.tool_paths import (
    _bundle_bin_candidates,
    ffmpeg_argv,
    ffprobe_argv,
    find_deno,
)
from local_media_downloader.config import default_web_dist


def _stage_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Fake an onedir bundle: ``<dir>/app.exe`` + ``<dir>/bin/``."""
    bundle = tmp_path / "bundle"
    (bundle / "bin").mkdir(parents=True)
    fake_exe = bundle / "app.exe"
    fake_exe.touch()
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    return bundle


def test_bundle_deno_wins_over_node_modules_and_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = _stage_bundle(monkeypatch, tmp_path)
    staged = bundle / "bin" / "deno"
    staged.touch()
    assert find_deno() == str(staged)


def test_bundle_ffmpeg_and_ffprobe_win_without_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = _stage_bundle(monkeypatch, tmp_path)
    monkeypatch.delenv("LMD_FFMPEG", raising=False)
    monkeypatch.delenv("LMD_FFPROBE", raising=False)
    staged_ffmpeg = bundle / "bin" / "ffmpeg"
    staged_ffprobe = bundle / "bin" / "ffprobe"
    staged_ffmpeg.touch()
    staged_ffprobe.touch()
    assert ffmpeg_argv() == [str(staged_ffmpeg)]
    assert ffprobe_argv() == [str(staged_ffprobe)]


def test_explicit_override_still_wins_over_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = _stage_bundle(monkeypatch, tmp_path)
    (bundle / "bin" / "ffmpeg").touch()
    monkeypatch.setenv("LMD_FFMPEG", "/custom/ffmpeg")
    assert ffmpeg_argv() == ["/custom/ffmpeg"]


def test_no_bundle_dir_falls_through_to_existing_behavior(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_exe = tmp_path / "lonely" / "python"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.touch()
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert _bundle_bin_candidates() == []
    # Must not point at the nonexistent bundle; dev resolution decides.
    deno = find_deno()
    assert deno is None or not deno.startswith(str(tmp_path))


def test_default_web_dist_frozen_prefers_bundle_web(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = _stage_bundle(monkeypatch, tmp_path)
    (bundle / "web").mkdir()
    (bundle / "web" / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert default_web_dist() == bundle / "web"


def test_default_web_dist_unfrozen_uses_source_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    resolved = default_web_dist()
    assert resolved.parts[-3:] == ("apps", "web", "dist")


def test_tool_paths_documents_bundle_first() -> None:
    assert "bundle" in (tool_paths.__doc__ or "")
