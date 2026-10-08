"""Frozen entrypoint shim (Phase 16).

PyInstaller runs the Analysis script as a top-level ``__main__`` module, where
the relative imports in ``local_media_downloader/__main__.py`` cannot resolve.
Importing the package entrypoint through its absolute path first gives it the
proper package context, so the same ``main()`` runs frozen and in development
(``python -m local_media_downloader`` / ``lmd-api``).
"""

from local_media_downloader.__main__ import main

if __name__ == "__main__":
    main()
