"""Shared test helpers.

Tests exercise the same boundary as production: a loopback ``Host`` and a valid
token. Anything less would let a test pass while the real request is refused,
so the helpers below build clients that behave like the dashboard does.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from local_media_downloader.security import TOKEN_HEADER

LOOPBACK_BASE_URL = "http://127.0.0.1:8765"
TOKEN_COOKIE = "lmd_token"


@contextmanager
def serving(app: FastAPI, *, base_url: str = LOOPBACK_BASE_URL) -> Iterator[TestClient]:
    """Run the app and yield a client that authenticates like the web UI."""
    client = TestClient(app, base_url=base_url)
    with client:
        client.headers.update({TOKEN_HEADER: app.state.token})
        yield client
