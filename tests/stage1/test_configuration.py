import pytest

from config.environments import DatabaseConfigurationError, Environment, load_config
from config.paths import require_test_root


def test_profiles_and_storage_contract(monkeypatch):
    dev = load_config(Environment.DEV)
    assert dev.database_url.startswith("sqlite:///")
    assert require_test_root().as_posix() in dev.database_url
    assert "192.168.1.58" not in dev.database_url
    monkeypatch.delenv("HMS_QR_DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError):
        load_config(Environment.PROD)
