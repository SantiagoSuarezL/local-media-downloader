"""URL admission policy.

The local API is a security boundary even on loopback
(ENGINEERING_PRINCIPLES #18), so a URL is validated before it can reach a
tool. Only ``http``/``https`` are accepted; ``file:``, ``javascript:``,
``data:`` and arbitrary local-resource schemes are rejected outright
(PRD security requirements).

Phase 10 closed two holes that the minimum gate left open:

- **Embedded credentials** (``https://user:pass@host``) would leak into logs,
  the ``jobs`` table and tool invocations. They are refused outright.
- **Private and loopback sources** (``http://127.0.0.1:8765/api/...``,
  ``http://192.168.0.5/...``) would turn the downloader into an SSRF proxy that
  can read services on the user's own machine or LAN. The hostname is rejected
  before any tool runs, so it can never be dialed.

Hostnames are checked literally (no DNS resolution here): resolution would add
latency to every request and could itself be rebound between the check and the
download. Literal filtering is the admission gate; per-site allowlists stay with
the extractor, which is the only layer that knows a site's real domains.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .errors import ErrorCode, ExtractionError

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnames that always mean "this machine" or "the local network".
_LOCAL_HOSTNAMES = frozenset({"localhost", "localhost.localdomain", "ip6-localhost"})

# Tracking parameters that carry no media identity: two URLs differing only in
# these are the same video, so dedupe must treat them as equal.
_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "utm_name",
        "utm_cid",
        "utm_reader",
        "utm_referrer",
        "utm_social",
        "utm_social-type",
        "gclid",
        "dclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "spm",
        "si",
        "feature",
        "pp",
        "ab_channel",
    }
)

_DEFAULT_PORTS = {"http": 80, "https": 443}


def _is_private_address(hostname: str) -> bool:
    literal = hostname[1:-1] if hostname.startswith("[") and hostname.endswith("]") else hostname
    try:
        address = ipaddress.ip_address(literal)
    except ValueError:
        return False
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def validate_url(url: str) -> str:
    """Return the URL unchanged, or raise :class:`ExtractionError`."""
    candidate = url.strip()
    if not candidate:
        raise ExtractionError(ErrorCode.INVALID_URL, "The URL is empty.")

    parts = urlsplit(candidate)
    if not parts.scheme:
        raise ExtractionError(
            ErrorCode.INVALID_URL, "The URL has no scheme; expected http or https."
        )
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ExtractionError(
            ErrorCode.UNSUPPORTED_PROTOCOL,
            f"Protocol '{scheme}:' is not supported. Use http or https.",
        )
    if not parts.netloc:
        raise ExtractionError(ErrorCode.INVALID_URL, "The URL has no host.")
    if parts.username or parts.password:
        # Never accepted: the credentials would be stored with the job and
        # echoed into logs and tool arguments.
        raise ExtractionError(
            ErrorCode.INVALID_URL,
            "URLs with embedded credentials are not supported.",
        )

    hostname = (parts.hostname or "").lower()
    if not hostname:
        raise ExtractionError(ErrorCode.INVALID_URL, "The URL has no host.")
    if hostname in _LOCAL_HOSTNAMES or hostname.endswith(".local") or _is_private_address(hostname):
        raise ExtractionError(
            ErrorCode.BLOCKED_SOURCE,
            "Addresses on this machine or local network cannot be used as a source.",
        )
    return candidate


def normalize_url(url: str) -> str:
    """Return a canonical form of ``url`` for duplicate detection.

    Two URLs that differ only in scheme/host case, default port, fragment or
    tracking parameters point at the same media, so a batch that pastes the same
    link twice (or once with and once without ``?utm_source=...``) must collapse
    to one job (PRD "Data retention and deduplication").

    The canonical form is deliberately conservative: it never reorders the
    path, never drops a non-tracking query parameter and never touches the
    userinfo (``validate_url`` already rejects embedded credentials before this
    is ever called). It is a comparison key, not a download URL — the job keeps
    the original string for yt-dlp.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port is not None and _DEFAULT_PORTS.get(scheme) == port:
        port = None
    netloc = host
    if parts.username or parts.password:
        # Credentials are refused by validate_url; keep them out of the key so a
        # malformed caller cannot make two different URLs compare equal.
        netloc = f"{parts.username or ''}:{parts.password or ''}@{host}"
    if port is not None:
        netloc = f"{netloc}:{port}"
    if parts.hostname and parts.hostname.startswith("["):
        netloc = f"[{host}]" if port is None else f"[{host}]:{port}"

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"

    query = urlencode(
        sorted(
            q
            for q in parse_qsl(parts.query, keep_blank_values=True)
            if q[0].lower() not in _TRACKING_PARAMS
        )
    )
    return urlunsplit((scheme, netloc, path, query, ""))
