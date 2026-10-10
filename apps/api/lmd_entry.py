"""Frozen entrypoint shim (Phase 16).

PyInstaller runs the Analysis script as a top-level ``__main__`` module, where
the relative imports in ``local_media_downloader/__main__.py`` cannot resolve.
Importing the package entrypoint through its absolute path first gives it the
proper package context, so the same ``main()`` runs frozen and in development
(``python -m local_media_downloader`` / ``lmd-api``).
"""

import multiprocessing

if __name__ == "__main__":
    # Granian serves through MPServer on GIL builds (Python 3.12): even with
    # workers=1 it spawns the worker process via multiprocessing "spawn",
    # which re-executes sys.executable — the whole frozen app — as the child.
    # Without freeze_support the child would start another server instead of
    # the worker and the frozen bundle never serves its first response.
    # This must run before anything else in the entry point.
    multiprocessing.freeze_support()

    from local_media_downloader.__main__ import main

    main()
