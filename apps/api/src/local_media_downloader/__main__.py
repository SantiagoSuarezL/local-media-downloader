"""Console entrypoint: run the service with Granian (single worker, ASGI)."""

from __future__ import annotations

from granian import Granian
from granian.constants import Interfaces
from granian.log import LogLevels

from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    settings.ensure_data_dir()
    Granian(
        "local_media_downloader.app:app",
        address=settings.host,
        port=settings.port,
        interface=Interfaces.ASGI,
        workers=1,
        log_level=LogLevels(settings.log_level.lower()),
    ).serve()


if __name__ == "__main__":
    main()
