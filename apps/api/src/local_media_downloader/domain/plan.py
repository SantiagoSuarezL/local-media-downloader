"""Execution plan produced by the planner.

The plan is fully derived from a validated ``OutputIntent`` plus the source
metadata: the client never supplies tool arguments, it only selects intent.
The plan is serializable so it can be persisted as ``execution_plan_json``
(TECHNICAL_SPEC §6) and reproduced exactly (ENGINEERING_PRINCIPLES §481).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One ordered step of an execution plan."""

    # SELECT_FORMAT, DOWNLOAD, MERGE, REMUX, TRANSCODE, EXTRACT_AUDIO,
    # VIDEO_ONLY, VALIDATE, FINALIZE
    kind: str
    tool: str  # yt_dlp | ffmpeg | ffprobe | internal
    detail: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "tool": self.tool, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    steps: tuple[PlanStep, ...]
    # Which FFmpeg strategy the plan commits to, for diagnostics/UX.
    strategy: str  # "copy" | "transcode" | "extract_audio" | "video_only"

    def as_dict(self) -> dict[str, object]:
        return {"strategy": self.strategy, "steps": [s.as_dict() for s in self.steps]}
