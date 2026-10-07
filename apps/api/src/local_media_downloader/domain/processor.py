"""Ports for local media processing and inspection.

Adapters are replaceable (ENGINEERING_PRINCIPLES #24): the domain knows only
these protocols, never ``ffmpeg``/``ffprobe``. A future implementation can be
swapped without touching the domain layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .probe import MediaProbe


@runtime_checkable
class MetadataInspector(Protocol):
    """Reads metadata from a local media file."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str | None: ...

    def inspect(self, path: Path, *, timeout: float) -> MediaProbe:
        """Inspect a file or raise :class:`ExtractionError`."""
        ...


@runtime_checkable
class MediaProcessor(Protocol):
    """Produces a new media file from an existing one."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str | None: ...

    def remux(self, source: Path, destination: Path, *, timeout: float) -> Path: ...

    def transcode(self, source: Path, destination: Path, *, timeout: float) -> Path: ...

    def extract_audio(self, source: Path, destination: Path, *, timeout: float) -> Path: ...

    def video_only(self, source: Path, destination: Path, *, timeout: float) -> Path: ...

    def convert_preset(
        self, source: Path, destination: Path, *, preset: str, timeout: float
    ) -> Path: ...

    def validate(self, path: Path, *, timeout: float) -> MediaProbe: ...
