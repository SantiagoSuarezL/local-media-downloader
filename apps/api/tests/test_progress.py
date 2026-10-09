"""Structured progress parsing.

The parser must never misread a human progress line, and must ignore anything
it does not understand rather than abort a download.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from yt_dlp import YoutubeDL, parse_options

from local_media_downloader.adapters.progress import (
    DELIMITER,
    RECORD_PREFIX,
    TEMPLATE,
    parse_progress_line,
)


def _line(*fields: str) -> str:
    return f"lmd{DELIMITER}{DELIMITER.join(fields)}"


def _render(template: str, progress: dict[str, object]) -> str:
    """Render a progress template exactly like yt-dlp's downloader does.

    ``YoutubeDL`` and ``evaluate_outtmpl`` are typed against yt-dlp's private
    TypedDicts (``_Params``/``_InfoDict``), which cannot be spelled from
    outside; the call is real, only the annotations are cast away.
    """
    ydl = cast(Any, YoutubeDL)({"quiet": True, "simulate": True})
    return str(ydl.evaluate_outtmpl(template, {"info": {}, "progress": progress}))


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
    # A human never sees this delimiter, so template output cannot be confused
    # with the human progress line.
    assert DELIMITER == "\x1f"
    # No trailing newline escape: the template is one argv element and yt-dlp
    # already terminates the line itself under --newline.
    assert "\n" not in TEMPLATE
    assert "\\n" not in TEMPLATE


def test_template_carries_no_output_type_prefix() -> None:
    # `download:` is the *type* key of yt-dlp's progress_template dict, not part
    # of the rendered line. Shipping it inside the template made the parser
    # reject every real record (the tool strips it) — see
    # test_rendered_record_from_ytdlp_option_parsing_parses.
    assert not TEMPLATE.startswith("download:")
    assert "download:" not in TEMPLATE


def test_rendered_record_from_ytdlp_option_parsing_parses() -> None:
    """Render the record the way yt-dlp does, through its own option parser.

    This is the contract test for the bug above: the template is handed to
    yt-dlp's CLI parser, which strips the ``download:`` type and keeps the rest
    as the ``download`` template, and it is rendered with yt-dlp's own outtmpl
    evaluator (which resolves ``progress.*`` and turns absent fields into
    ``NA``), exactly like ``FileDownloader._report_progress_status`` does. The
    result must be a line our parser accepts, with every field intact.
    """
    parsed = parse_options(["--progress-template", TEMPLATE, "https://example.invalid/x"])
    template = parsed.options.progress_template["download"]
    assert template == TEMPLATE

    rendered = _render(
        template,
        {
            "_percent_str": " 12.5%",
            "downloaded_bytes": 1234567,
            "total_bytes": 9876543,
            "speed": 654321.0,
            "eta": 7,
            "fragment_index": 2,
        },
    )
    assert rendered.startswith(RECORD_PREFIX)
    progress = parse_progress_line(rendered)
    assert progress is not None
    assert progress.percentage == 12.5
    assert progress.downloaded_bytes == 1234567
    assert progress.total_bytes == 9876543
    assert progress.speed_bytes_per_second == 654321.0
    assert progress.eta_seconds == 7.0
    assert progress.fragment_index == 2


def test_rendered_record_with_absent_fields_parses_as_na() -> None:
    """yt-dlp renders absent progress fields as NA; the parser keeps the rest.

    Speeds/ETA are absent on the first ticks of a download, so a record made only
    of unknown fields must still report the bytes it does know.
    """
    rendered = _render(TEMPLATE, {"_percent_str": "0.0%", "downloaded_bytes": 1024})
    progress = parse_progress_line(rendered)
    assert progress is not None
    assert progress.percentage == 0.0
    assert progress.downloaded_bytes == 1024
    assert progress.total_bytes is None
    assert progress.speed_bytes_per_second is None
    assert progress.eta_seconds is None
    assert progress.fragment_index is None


@pytest.mark.parametrize("value", ["0%", "100%", "12.5%"])
def test_percent_forms(value: str) -> None:
    progress = parse_progress_line(_line(value, "0", "0", "NA", "NA", "NA"))
    assert progress is not None
    assert progress.percentage is not None
