import sys

import pytest

from local_media_downloader.config import Settings, default_data_dir


def test_defaults_are_loopback_and_local() -> None:
    settings = Settings()
    assert settings.host == "127.0.0.1"
    assert settings.port == 8765
    assert str(settings.data_dir) == "data"
    assert settings.log_level == "INFO"


def test_env_overrides(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LMD_HOST", "127.0.0.1")
    monkeypatch.setenv("LMD_PORT", "9001")
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "custom"))
    monkeypatch.setenv("LMD_LOG_LEVEL", "debug")
    settings = Settings.from_env()
    assert settings.host == "127.0.0.1"
    assert settings.port == 9001
    assert settings.log_level == "DEBUG"
    assert settings.database_path.name == "app.db"
    assert settings.database_path.parent.name == "custom"


def test_invalid_port_raises(monkeypatch) -> None:
    monkeypatch.setenv("LMD_PORT", "not-a-port")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_frozen_data_dir_is_per_user(monkeypatch, tmp_path) -> None:
    """A frozen bundle under Program Files cannot write next to the exe."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LMD_DATA_DIR", raising=False)
    data_dir = default_data_dir()
    assert data_dir.name in ("Local Media Downloader", "local-media-downloader")
    assert str(data_dir) != "data"
    settings = Settings.from_env()
    assert settings.data_dir == data_dir
    assert settings.database_path.name == "app.db"


def test_env_data_dir_wins_over_frozen_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LMD_DATA_DIR", str(tmp_path / "custom"))
    assert Settings.from_env().database_path.parent.name == "custom"
