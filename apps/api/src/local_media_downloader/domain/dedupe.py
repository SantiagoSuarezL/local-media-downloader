"""Duplicate detection key.

A job is a duplicate when another non-terminal job has the same normalized URL
AND the same output intent (PRD "Data retention and deduplication"). The key is
a single SHA-256 over both halves so the repository can look a candidate up
with one indexed column instead of comparing JSON blobs.

The intent half is a canonical JSON dump: key order in the request must not
change the identity of the intent, so keys are sorted before hashing.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .urls import normalize_url


def intent_fingerprint(intent: dict[str, Any]) -> str:
    """Stable hash of an intent payload, independent of key order."""
    canonical = json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dedupe_key(source_url: str, intent: dict[str, Any]) -> str:
    """Identity of a job candidate: normalized URL + intent fingerprint."""
    normalized = normalize_url(source_url)
    payload = f"{normalized}\n{intent_fingerprint(intent)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
