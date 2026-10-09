"""
PyInstaller spec for Local Media Downloader onedir bundle.

Target: Windows first, then Linux/macOS (IMPLEMENTATION_PLAN Phase 16).

All paths are anchored at this file, so the spec builds on any machine and in
CI — never hardcode an absolute checkout path here. Run from ``apps/api``::

    uv run --extra build pyinstaller lmd.spec

Layout of the onedir bundle (PyInstaller 6)::

    dist/LocalMediaDownloader/
        Local Media Downloader.exe   # frozen entrypoint (console: service logs)
        bin/                         # staged post-build: deno, ffmpeg, ffprobe
        THIRD_PARTY_NOTICES.md       # staged post-build from the repo root
        _internal/
            web/                     # built Svelte UI (datas below)

``bin/`` and the notices are staged by copying them next to the executable
after the build (see the ``dist`` step in the Phase 16 notes); the frozen app
resolves them at runtime via ``tool_paths._bundle_bin_candidates`` and
``config.default_web_dist`` (``LMD_WEB_DIST`` still overrides).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

REPO_ROOT = Path(SPECPATH).resolve().parent.parent  # <repo>/apps/api/ -> <repo>
WEB_DIST = REPO_ROOT / "apps" / "web" / "dist"

block_cipher = None

# Built Svelte assets. The web bundle must be built first (``pnpm build``);
# fail fast here instead of shipping a headless bundle.
if not (WEB_DIST / "index.html").is_file():
    raise SystemExit(f"web dist missing: {WEB_DIST} (run `pnpm build` first)")

datas = [
    (str(WEB_DIST), "web"),
]
binaries: list = []

# curl-cffi brings TLS impersonation (TikTok and friends reject vanilla
# urllib); yt-dlp imports it dynamically, invisible to static analysis, and
# it ships native extensions -> collect modules AND shared libraries.
_cc_datas, _cc_binaries, _cc_hidden = collect_all("curl_cffi")
datas += _cc_datas
binaries += _cc_binaries

# yt-dlp-ejs carries the JS challenge solvers as data files; without them the
# frozen app silently loses the formats that need a JS runtime.
_ejs_datas, _ejs_binaries, _ejs_hidden = collect_all("yt_dlp_ejs")
datas += _ejs_datas
binaries += _ejs_binaries

# Hidden imports for dynamic loaders: yt-dlp resolves extractors and
# postprocessors via importlib, invisible to PyInstaller's static analysis.
hiddenimports = [
    "yt_dlp",
    "yt_dlp.extractor",
    "yt_dlp.extractor.common",
    "yt_dlp.postprocessor",
    # JS challenge solvers. The module itself is imported dynamically by
    # diagnostics; its .js payload comes from yt-dlp's own PyInstaller hook
    # (registered through the pyinstaller40 entry point) plus collect_all here.
    "yt_dlp_ejs",
    *_ejs_hidden,
    *_cc_hidden,
    "pydantic",
    "fastapi",
    "granian",
    # App internal modules reached through the Granian target string
    # "local_media_downloader.app:app".
    "local_media_downloader.app",
    "local_media_downloader.config",
    "local_media_downloader.db",
    "local_media_downloader.jobs",
]

a = Analysis(
    ["lmd_entry.py"],
    pathex=[str(REPO_ROOT / "apps" / "api" / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "test", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Local Media Downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LocalMediaDownloader",
)
