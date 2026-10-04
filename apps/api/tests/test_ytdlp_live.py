"""Opt-in live network tests.

These hit a real public URL and therefore never run in CI. Enable them with::

    LMD_LIVE_NETWORK=1 uv run pytest apps/api/tests/test_ytdlp_live.py -v

CI must stay deterministic and offline; the acceptance for Phase 3 was verified
manually with exactly this code path.
"""

from __future__ import annotations

import os

import pytest

from local_media_downloader.adapters.yt_dlp import YtDlpExtractor
from local_media_downloader.domain.errors import ExtractionError
from local_media_downloader.domain.media import FormatKind

pytestmark = pytest.mark.skipif(
    os.environ.get("LMD_LIVE_NETWORK") != "1",
    reason="set LMD_LIVE_NETWORK=1 to run tests that hit the network",
)

# Small, stable, public and freely licensed test asset.
LIVE_URL = "https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4"


def test_resolves_a_public_url_into_normalized_media() -> None:
    info = YtDlpExtractor().resolve(LIVE_URL, timeout=120.0)
    assert info.id
    assert info.source.extractor
    # A direct media link is not probed, so duration is legitimately absent;
    # the contract is null rather than a fabricated value.
    assert info.duration_seconds is None or info.duration_seconds > 0
    assert info.is_live is False
    assert info.formats
    assert all(f.kind in set(FormatKind) for f in info.formats)
    assert all(f.id for f in info.formats)
    # No yt-dlp schema leaks into the normalized model.
    payload = info.as_dict()
    formats = payload["formats"]
    assert isinstance(formats, list)
    assert {"vcodec", "acodec", "tbr", "format_note", "webpage_url"}.isdisjoint(formats[0])


def test_unsupported_url_is_classified_not_generic() -> None:
    with pytest.raises(ExtractionError) as exc:
        YtDlpExtractor().resolve("https://example.com/not-a-real-video-page", timeout=60.0)
    assert exc.value.code.value != "EXTRACTION_FAILED"
    assert exc.value.detail


def test_invalid_scheme_never_reaches_the_tool() -> None:
    with pytest.raises(ExtractionError):
        YtDlpExtractor().resolve("file:///etc/passwd", timeout=10.0)
