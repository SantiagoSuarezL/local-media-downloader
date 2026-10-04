"""Port the domain depends on.

Adapters are replaceable (ENGINEERING_PRINCIPLES #24): the domain knows only
this protocol, never ``yt-dlp``. A future extractor can be swapped without
touching the domain layer.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .media import MediaInfo


@runtime_checkable
class Extractor(Protocol):
    """Resolves a URL into normalized media information."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str | None: ...

    def resolve(self, url: str, *, timeout: float) -> MediaInfo:
        """Resolve metadata or raise :class:`ExtractionError`."""
        ...
