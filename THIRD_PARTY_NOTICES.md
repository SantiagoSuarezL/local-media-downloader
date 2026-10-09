# THIRD PARTY NOTICES

## Apache License 2.0 – Project
Local Media Downloader is licensed under the Apache License 2.0.

## Bundled Components
The installer bundles the following third-party components with pinned versions.

* **Python 3.12** – Python Software Foundation, Python Software Foundation License.
* **yt-dlp 2026.8.19** – The Unlicense (License-Expression: Unlicense in the installed metadata). Invoked as `sys.executable -m yt_dlp`, never from PATH.
* **yt-dlp-ejs 0.8.0** – Unlicense AND MIT AND ISC (License-Expression in the installed metadata). JS challenge solvers yt-dlp runs through the staged Deno; without them some sites lose formats.
* **FastAPI 0.142.2** – MIT License.
* **Granian 2.8.4** – MIT License.
* **Pydantic 2.13.5** – MIT License.
* **Deno 2.9.6** – MIT License. Staged in the bundle `bin/` directory.
* **curl-cffi 0.16.3** – MIT License. Provides TLS impersonation to yt-dlp (some sites refuse vanilla Python TLS); ships its own bundled libcurl (curl is MIT/X-derived).
* **FFmpeg / FFprobe** – LGPL v2.1 / GPL v2 (prefer an LGPL-compatible build for release). Staged in the bundle `bin/` directory; resolved via `LMD_FFMPEG`/`LMD_FFPROBE` override first, then `bin/`, then PATH as a last resort.
* **Svelte 5**, **Vite**, **Tailwind CSS**, **TypeScript**, **pnpm** – licenses as listed in respective package.json.
* **Archivo (web font)** – SIL Open Font License 1.1. Self-hosted as WOFF2 subsets (`latin`, `latin-ext`) in `apps/web/public/fonts/` rather than loaded from a CDN, so the dashboard needs no internet connection to render correctly. The font files are unmodified subsets.

## Source Links
* https://github.com/yt-dlp/yt-dlp
* https://github.com/yt-dlp/ejs
* https://github.com/tiangolo/fastapi
* https://github.com/emrekaradag/granian
* https://github.com/pydantic/pydantic
* https://deno.land/
* https://github.com/lexiforest/curl_cffi
* https://ffmpeg.org/
* https://fonts.google.com/specimen/Archivo (Omnibus-Type, SIL OFL 1.1)

## License Texts
Full license texts are available under the open-source repositories above. No code is modified except for bundling. FFmpeg is used dynamically via subprocess; it is not statically linked. Patents and trademarks are not transferred by this notice.

Copyright (c) 2025–2026 Local Media Downloader contributors.
