from __future__ import annotations

from local_media_downloader.domain.dedupe import dedupe_key, intent_fingerprint
from local_media_downloader.domain.urls import normalize_url


def test_normalize_url_lowercases_scheme_and_host() -> None:
    assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"


def test_normalize_url_strips_default_port() -> None:
    assert normalize_url("https://example.com:443/video") == "https://example.com/video"
    assert normalize_url("http://example.com:80/video") == "http://example.com/video"


def test_normalize_url_keeps_non_default_port() -> None:
    assert normalize_url("https://example.com:8443/video") == "https://example.com:8443/video"


def test_normalize_url_strips_fragment() -> None:
    assert normalize_url("https://example.com/video#t=10") == "https://example.com/video"


def test_normalize_url_strips_tracking_params() -> None:
    assert (
        normalize_url("https://example.com/video?utm_source=x&id=5")
        == "https://example.com/video?id=5"
    )


def test_normalize_url_sorts_query_params() -> None:
    assert normalize_url("https://example.com/video?b=2&a=1") == "https://example.com/video?a=1&b=2"


def test_normalize_url_keeps_non_tracking_params() -> None:
    assert (
        normalize_url("https://example.com/video?t=10&hls=1")
        == "https://example.com/video?hls=1&t=10"
    )


def test_normalize_url_strips_trailing_slash() -> None:
    assert normalize_url("https://example.com/video/") == "https://example.com/video"


def test_intent_fingerprint_is_order_independent() -> None:
    a = intent_fingerprint({"media": "video", "quality": "best"})
    b = intent_fingerprint({"quality": "best", "media": "video"})
    assert a == b


def test_intent_fingerprint_differs_for_different_intents() -> None:
    a = intent_fingerprint({"media": "video"})
    b = intent_fingerprint({"media": "audio"})
    assert a != b


def test_dedupe_key_combines_url_and_intent() -> None:
    key_a = dedupe_key("https://example.com/video", {"media": "video"})
    key_b = dedupe_key("https://example.com/video", {"media": "video"})
    key_c = dedupe_key("https://example.com/video", {"media": "audio"})
    key_d = dedupe_key("https://example.com/other", {"media": "video"})
    assert key_a == key_b
    assert key_a != key_c
    assert key_a != key_d


def test_dedupe_key_ignores_tracking_params_in_url() -> None:
    key_a = dedupe_key("https://example.com/video?utm_source=x", {"media": "video"})
    key_b = dedupe_key("https://example.com/video", {"media": "video"})
    assert key_a == key_b
