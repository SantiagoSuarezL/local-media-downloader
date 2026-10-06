"""Console entrypoint: run the service with Granian (single worker, ASGI)."""

from __future__ import annotations

import sys

from granian import Granian
from granian.constants import Interfaces
from granian.log import LogLevels

from .config import Settings
from .logging_config import configure_logging
from .security import SecurityError, assert_loopback_host


def main() -> None:
    settings = Settings.from_env()
    settings.ensure_data_dir()
    configure_logging(settings.log_level)
    try:
        # The bind address is the outermost boundary: if it is not loopback the
        # whole service is exposed to the network, so this fails before binding.
        assert_loopback_host(settings.host)
    except SecurityError as error:
        print(f"error: {error.message}", file=sys.stderr)
        raise SystemExit(1) from error

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
