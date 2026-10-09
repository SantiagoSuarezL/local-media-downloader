"""Structured progress parsing.

The UI must never parse raw yt-dlp stdout as its progress protocol
(TECHNICAL_SPEC §3). Instead yt-dlp is invoked with ``--progress-template`` and a
private delimiter, so each progress line is a machine-readable record produced by
the tool itself rather than a human string we try to interpret.

Template used by the adapter::

    <lmd><US>%<percent>%<downloaded>%<total>%<speed>%<eta>%<fragment>

The raw human form ("0.0% of ~10.00MiB at 1.00MiB/s ETA 00:10") is never parsed.

``--progress-template`` takes ``[TYPES:]TEMPLATE``: the leading ``download:`` is
the *output type* (the key of yt-dlp's ``progress_template`` dict) and yt-dlp
consumes it, so it never reaches the rendered line. The rendered line therefore
starts with our marker, and the marker alone identifies a record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

DELIMITER = "\x1f"
PROGRESS_PREFIX = "lmd"
RECORD_PREFIX = f"{PROGRESS_PREFIX}{DELIMITER}"

# No ``download:`` type prefix here on purpose: yt-dlp parses it as the output
# type and strips it, so including it would make every rendered line start with
# the marker alone while the parser (correctly) looks for the marker -- the
# mismatch silently dropped every progress record. The rendered template ends
# without ``\\n`` because ``to_screen``/the multiline printer already terminates
# the line under ``--newline``.
TEMPLATE = (
    f"{RECORD_PREFIX}%(progress._percent_str)s{DELIMITER}"
    "%(progress.downloaded_bytes)s"
    f"{DELIMITER}%(progress.total_bytes)s{DELIMITER}"
    "%(progress.speed)s"
    f"{DELIMITER}%(progress.eta)s{DELIMITER}"
    "%(progress.fragment_index)s"
)


class ProgressStage(StrEnum):
    DOWNLOAD = "download"
    POSTPROCESS = "postprocess"


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    percentage: float | None
    downloaded_bytes: int | None
    total_bytes: int | None
    speed_bytes_per_second: float | None
    eta_seconds: float | None
    fragment_index: int | None

    def as_dict(self) -> dict[str, object]:
        return {
            "stage": ProgressStage.DOWNLOAD.value,
            "percentage": self.percentage,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "speed_bytes_per_second": self.speed_bytes_per_second,
            "eta_seconds": self.eta_seconds,
            "fragment_index": self.fragment_index,
        }


def _to_optional_int(raw: str) -> int | None:
    text = raw.strip()
    if not text or text.upper() == "NA":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _to_optional_float(raw: str) -> float | None:
    text = raw.strip()
    if not text or text.upper() == "NA":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_optional_percent(raw: str) -> float | None:
    text = raw.strip().rstrip("%")
    if not text or text.upper() == "NA":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_progress_line(line: str) -> DownloadProgress | None:
    """Parse one progress line. Returns ``None`` for anything unrecognized.

    Being permissive here is deliberate: yt-dlp interleaves warnings and
    per-fragment lines, and a line we cannot understand must not be allowed to
    abort a download.
    """
    text = line.strip()
    if not text.startswith(RECORD_PREFIX):
        return None
    parts = text.split(DELIMITER)
    # parts[0] is the "lmd" marker.
    if len(parts) < 7:
        return None
    return DownloadProgress(
        percentage=_to_optional_percent(parts[1]),
        downloaded_bytes=_to_optional_int(parts[2]),
        total_bytes=_to_optional_int(parts[3]),
        speed_bytes_per_second=_to_optional_float(parts[4]),
        eta_seconds=_to_optional_float(parts[5]),
        fragment_index=_to_optional_int(parts[6]),
    )
