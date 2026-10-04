"""Structured progress parsing.

The parser must never misread a human progress line, and must ignore anything
it does not understand rather than abort a download.
"""

from __future__ import annotations

import pytest

from local_media_downloader.adapters.progress import (
    DELIMITER,
    TEMPLATE,
    parse_progress_line,
)


def _line(*fields: str) -> str:
    return f"download:lmd{DELIMITER}{DELIMITER.join(fields)}"


def test_parses_a_complete_record() -> None:
    progress = parse_progress_line(_line("45.3%", "1234567", "2723456", "987654", "1.5", "3"))
    assert progress is not None
    assert progress.percentage == 45.3
    assert progress.downloaded_bytes == 1234567
    assert progress.total_bytes == 2723456
    assert progress.speed_bytes_per_second == 987654.0
    assert progress.eta_seconds == 1.5
    assert progress.fragment_index == 3


def test_na_fields_become_none() -> None:
    progress = parse_progress_line(_line("NA", "NA", "NA", "NA", "NA", "NA"))
    assert progress is not None
    assert progress.percentage is None
    assert progress.downloaded_bytes is None
    assert progress.total_bytes is None
    assert progress.speed_bytes_per_second is None
    assert progress.eta_seconds is None
    assert progress.fragment_index is None


def test_unknown_total_is_none_but_downloaded_is_kept() -> None:
    progress = parse_progress_line(_line("NA", "5000", "NA", "NA", "NA", "NA"))
    assert progress is not None
    assert progress.downloaded_bytes == 5000
    assert progress.total_bytes is None


def test_ignores_human_readable_progress() -> None:
    assert parse_progress_line("[download]  45.3% of ~2.72MiB at 987.65KiB/s ETA 00:01") is None


def test_ignores_warnings_and_noise() -> None:
    assert parse_progress_line("WARNING: something happened") is None
    assert parse_progress_line("") is None
    assert parse_progress_line("   ") is None
    assert parse_progress_line("[youtube] Extracting URL") is None


def test_ignores_truncated_record() -> None:
    assert parse_progress_line(_line("10%", "100")) is None


def test_ignores_postprocess_lines() -> None:
    assert parse_progress_line('[Merger] Merging formats into "file.mp4"') is None


def test_unparseable_numbers_do_not_raise() -> None:
    progress = parse_progress_line(_line("n/a", "abc", "", "xyz", "-", "NaN"))
    assert progress is not None
    assert progress.percentage is None
    assert progress.downloaded_bytes is None


def test_as_dict_exposes_the_sse_contract_fields() -> None:
    progress = parse_progress_line(_line("50%", "100", "200", "10", "5", "1"))
    assert progress is not None
    assert set(progress.as_dict()) == {
        "stage",
        "percentage",
        "downloaded_bytes",
        "total_bytes",
        "speed_bytes_per_second",
        "eta_seconds",
        "fragment_index",
    }


def test_template_uses_named_fields_and_the_private_delimiter() -> None:
    assert "%(progress.downloaded_bytes)s" in TEMPLATE
    assert "%(progress._percent_str)s" in TEMPLATE
    assert DELIMITER in TEMPLATE
    # The template is passed as an argv element, so yt-dlp itself must see the
    # two-character sequence \n and expand it — not a literal newline.
    assert "\\n" in TEMPLATE
    assert "\n" not in TEMPLATE
    # A human never sees this delimiter, so template output cannot be confused
    # with the human progress line.
    assert DELIMITER == "\x1f"


@pytest.mark.parametrize("value", ["0%", "100%", "12.5%"])
def test_percent_forms(value: str) -> None:
    progress = parse_progress_line(_line(value, "0", "0", "NA", "NA", "NA"))
    assert progress is not None
    assert progress.percentage is not None
