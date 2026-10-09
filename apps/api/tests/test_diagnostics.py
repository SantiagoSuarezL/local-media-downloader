"""Tool detection for /api/v1/health.

Diagnostics must describe the binaries the adapters will really spawn. Probing
``PATH`` reported ``deno: no`` while the extractor was running the workspace Deno
from ``node_modules/.bin``, so the resolution used by ``tool_paths`` is pinned
here: the probe argv is the adapter's argv.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from local_media_downloader import diagnostics
from local_media_downloader.adapters import tool_paths
from local_media_downloader.diagnostics import detect_tools

# Tools resolved through tool_paths and probed as a subprocess. yt-dlp-ejs is an
# import, not a process, so it is covered by its own tests below.
PROBED = ("yt_dlp", "deno", "ffmpeg", "ffprobe")


class _Completed:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _record_argv(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    seen: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> _Completed:
        seen.append(list(argv))
        return _Completed(stdout="9.9.9\n")

    monkeypatch.setattr(diagnostics.subprocess, "run", fake_run)
    return seen


def test_probe_argv_matches_the_adapter_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    deno = tmp_path / "deno"
    deno.write_text("", encoding="utf-8")
    monkeypatch.setattr(diagnostics, "find_deno", lambda: str(deno))

    seen = _record_argv(monkeypatch)
    detect_tools()

    # yt-dlp: the pinned module of this environment, never a PATH shim.
    assert seen[0] == [sys.executable, "-m", "yt_dlp", "--version"]
    assert seen[0][:3] == tool_paths.yt_dlp_argv()
    # Deno: whatever the adapter resolves, including outside PATH.
    assert seen[1] == [str(deno), "--version"]
    # FFmpeg/FFprobe: environment/bundle before PATH, exactly like the processor.
    assert seen[2][:1] == tool_paths.ffmpeg_argv()
    assert seen[2][-1] == "-version"
    assert seen[3][:1] == tool_paths.ffprobe_argv()
    assert seen[3][-1] == "-version"


def test_missing_deno_is_not_probed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "find_deno", lambda: None)

    seen = _record_argv(monkeypatch)
    tools = detect_tools()

    assert tools["deno"].detected is False
    assert not any("deno" in " ".join(argv) for argv in seen[1:])


def test_a_missing_tool_is_reported_as_not_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(argv: list[str], **kwargs: object) -> _Completed:
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(diagnostics.subprocess, "run", missing)
    tools = detect_tools()

    assert set(tools) == {"yt_dlp", "yt_dlp_ejs", "deno", "ffmpeg", "ffprobe"}
    assert all(tools[name].detected is False for name in PROBED)


def test_a_tool_that_times_out_is_reported_as_not_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(argv: list[str], **kwargs: object) -> _Completed:
        raise subprocess.TimeoutExpired(argv, 2.0)

    monkeypatch.setattr(diagnostics.subprocess, "run", timeout)
    tools = detect_tools()
    assert all(tools[name].detected is False for name in PROBED)


def test_only_the_version_line_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool that prints more than one line contributes only its first line.

    ``ffmpeg -version`` prints a whole banner (build flags, configuration,
    libraries); the payload carries one string per tool, and health is reachable
    without a token, so nothing past the version line is kept.
    """

    def noisy(argv: list[str], **kwargs: object) -> _Completed:
        return _Completed(stdout="1.2.3\nbuilt with /very/long/options\n")

    monkeypatch.setattr(diagnostics.subprocess, "run", noisy)
    for name in PROBED:
        assert detect_tools()[name].version == "1.2.3", name


def test_detects_the_pinned_ytdlp_of_this_environment() -> None:
    """No monkeypatching: the environment always has yt-dlp installed."""
    tool = detect_tools()["yt_dlp"]
    assert tool.detected is True
    assert tool.version is not None
    assert tool.version.split(".")[0].isdigit()


def test_detects_the_ejs_solvers_in_this_environment() -> None:
    """yt-dlp-ejs is a declared dependency; a rename cannot hide it again."""
    tool = detect_tools()["yt_dlp_ejs"]
    assert tool.detected is True
    assert tool.version is not None
    assert tool.version[0].isdigit()


@pytest.mark.parametrize("attribute", ["version", "__version__"])
def test_ejs_version_accepts_either_spelling(
    monkeypatch: pytest.MonkeyPatch, attribute: str
) -> None:
    module = ModuleType("yt_dlp_ejs")
    setattr(module, attribute, "9.9.9")
    monkeypatch.setitem(sys.modules, "yt_dlp_ejs", module)
    assert diagnostics._ejs_version() == "9.9.9"


def test_ejs_installed_without_a_version_attribute_is_still_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "yt_dlp_ejs", ModuleType("yt_dlp_ejs"))
    assert diagnostics._ejs_version() == "unknown"


def test_ejs_absent_is_not_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "yt_dlp_ejs", None)
    assert diagnostics._ejs_version() is None
