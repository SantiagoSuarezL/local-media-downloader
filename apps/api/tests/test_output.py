from __future__ import annotations

from pathlib import Path

from local_media_downloader.domain.output import OutputRule, build_output_path, resolve_output_root


def test_resolve_output_root_expands_user() -> None:
    root = resolve_output_root("~/Downloads/Media")
    assert root.is_absolute()
    assert "~" not in str(root)


def test_resolve_output_root_resolves_relative_to_cwd() -> None:
    root = resolve_output_root("data/output")
    assert root.is_absolute()


def test_build_output_path_flat(tmp_path: Path) -> None:
    path = build_output_path(
        tmp_path,
        rule=OutputRule.FLAT,
        title="My Video",
        extension="mp4",
        fallback="job-id",
    )
    assert path == tmp_path / "My Video.mp4"


def test_build_output_path_sanitizes_title(tmp_path: Path) -> None:
    path = build_output_path(
        tmp_path,
        rule=OutputRule.FLAT,
        title="../../evil",
        extension="mp4",
        fallback="job-id",
    )
    assert ".." not in str(path)
    assert path.parent == tmp_path


def test_build_output_path_by_extractor(tmp_path: Path) -> None:
    path = build_output_path(
        tmp_path,
        rule=OutputRule.BY_EXTRACTOR,
        title="Video",
        extension="mp3",
        extractor="youtube",
        fallback="job-id",
    )
    assert path == tmp_path / "youtube" / "Video.mp3"


def test_build_output_path_by_date(tmp_path: Path) -> None:
    path = build_output_path(
        tmp_path,
        rule=OutputRule.BY_DATE,
        title="Video",
        extension="mp4",
        created_at="2026-03-15T10:00:00+00:00",
        fallback="job-id",
    )
    assert path == tmp_path / "2026" / "03" / "Video.mp4"


def test_build_output_path_uses_fallback_when_title_empty(tmp_path: Path) -> None:
    path = build_output_path(
        tmp_path,
        rule=OutputRule.FLAT,
        title=None,
        extension="mp4",
        fallback="job-123",
    )
    assert path == tmp_path / "job-123.mp4"


def test_build_output_path_proves_containment(tmp_path: Path) -> None:
    path = build_output_path(
        tmp_path,
        rule=OutputRule.FLAT,
        title="normal",
        extension="mp4",
        fallback="f",
    )
    assert tmp_path in path.parents
