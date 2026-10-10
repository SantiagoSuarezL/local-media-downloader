"""Frozen entrypoint shim (Phase 16).

PyInstaller runs the Analysis script as a top-level ``__main__`` module, where
the relative imports in ``local_media_downloader/__main__.py`` cannot resolve.
Importing the package entrypoint through its absolute path first gives it the
proper package context, so the same ``main()`` runs frozen and in development
(``python -m local_media_downloader`` / ``lmd-api``).
"""

import multiprocessing
import runpy
import sys


def _run_bundled_module(argv: list[str]) -> bool:
    """Serve ``exe -m yt_dlp ...`` from inside the frozen bundle.

    The backend spawns yt-dlp as ``sys.executable -m yt_dlp`` everywhere (the
    adapter and the health probes share ``yt_dlp_argv()``), but a PyInstaller
    bootloader ignores ``-m``: without this dispatch the frozen exe would boot
    a NESTED SERVER on the same port instead of yt-dlp — health probes time
    out, downloads hang, and orphaned nested servers fight over the port.
    ``runpy`` executes the bundled ``yt_dlp`` package exactly like
    ``python -m yt_dlp``, so frozen output stays byte-identical to dev.
    Returns True when the invocation was handled (the module raises
    SystemExit itself on every real path; True doubles as the safety net).
    """
    if not getattr(sys, "frozen", False):
        return False
    if len(argv) >= 3 and argv[1] == "-m" and argv[2] == "yt_dlp":
        # Behave exactly like `python -m yt_dlp ...`: the interpreter strips
        # the `-m <module>` prefix before the module runs, but runpy with
        # alter_sys only rewrites argv[0]. Without the trim, yt-dlp receives
        # `-m` itself as an (invalid) option.
        sys.argv = [argv[0], *argv[3:]]
        runpy.run_module("yt_dlp", run_name="__main__", alter_sys=True)
        return True
    return False


if __name__ == "__main__":
    # Granian spawns its worker via multiprocessing even with workers=1; a
    # frozen exe re-runs THIS script as the child, so without freeze_support
    # the child would start another server instead of the worker and the
    # banner never comes up (the Phase 16 frozen smoke failure).
    # This must run before anything else in the entry point.
    multiprocessing.freeze_support()

    if _run_bundled_module(sys.argv):
        raise SystemExit(0)

    from local_media_downloader.__main__ import main

    main()
