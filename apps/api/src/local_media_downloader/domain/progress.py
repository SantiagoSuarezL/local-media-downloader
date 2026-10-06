"""Normalized progress model observable by the scheduler and the UI.

TECHNICAL_SPEC §3 lists the required fields. The scheduler consumes this
exact model; adapters only contribute the raw numbers, they never publish.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class JobProgress:
    state: str
    stage: str | None = None
    percentage: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: float | None = None
    current_file: str | None = None
    error_code: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {k: v for k, v in asdict(self).items()}
