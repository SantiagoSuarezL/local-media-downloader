import pytest

from local_media_downloader.config import Settings


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
