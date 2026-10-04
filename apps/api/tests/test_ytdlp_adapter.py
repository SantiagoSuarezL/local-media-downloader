"""Extractor diagnostics and tool resolution.

These tests use the real, pinned yt-dlp from the uv environment but never touch
the network: ``--version`` is a local operation.
"""

from __future__ import annotations

from importlib.metadata import version as pinned_version
from pathlib import Path

from local_media_downloader.adapters.tool_paths import (
    ffmpeg_argv,
    find_deno,
    node_bin_candidates,
    yt_dlp_argv,
)
from local_media_downloader.adapters.yt_dlp import YtDlpExtractor
from local_media_downloader.app import _extractor_status


def _parse(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_version_matches_the_pinned_dependency() -> None:
    """The adapter must report the version pinned in uv.lock, not a PATH copy.

    yt-dlp zero-pads its own --version output ("2026.08.19") while the package
    metadata is not ("2026.8.19"), so the comparison is numeric.
    """
    extractor = YtDlpExtractor()
    reported = extractor.version
    assert reported is not None
    assert _parse(reported) == _parse(pinned_version("yt-dlp"))


def test_extractor_status_reports_outdated_signal() -> None:
    status = _extractor_status(YtDlpExtractor)
    assert status["name"] == "yt-dlp"
    assert status["available"] is True
    reported = status["version"]
    assert isinstance(reported, str)
    assert _parse(reported) == _parse(pinned_version("yt-dlp"))
    assert status["may_be_outdated"] is False


def test_argv_uses_the_running_interpreter_not_path() -> None:
    argv = yt_dlp_argv()
    assert argv[0] == __import__("sys").executable
    assert argv[1:] == ["-m", "yt_dlp"]


def test_js_runtime_is_passed_when_deno_is_available() -> None:
    deno = find_deno()
    argv = YtDlpExtractor().base_argv()
    if deno:
        assert "--js-runtimes" in argv
        assert f"deno:{deno}" in argv
    else:
        assert "--js-runtimes" not in argv


def test_deno_is_found_in_the_workspace_node_modules() -> None:
    deno = find_deno()
    if deno is None:
        return  # deno is optional; Phase 1 health reports "not detected"
    assert Path(deno).exists()
    assert "node_modules" in deno or Path(deno).name.startswith("deno")


def test_node_bin_candidates_include_the_workspace() -> None:
    assert any("node_modules" in str(p) for p in node_bin_candidates())


def test_ffmpeg_argv_prefers_an_explicit_override(monkeypatch) -> None:
    monkeypatch.setenv("LMD_FFMPEG", "/custom/ffmpeg")
    assert ffmpeg_argv() == ["/custom/ffmpeg"]


def test_extractor_satisfies_the_port() -> None:
    from local_media_downloader.domain.extractor import Extractor

    assert isinstance(YtDlpExtractor(), Extractor)
