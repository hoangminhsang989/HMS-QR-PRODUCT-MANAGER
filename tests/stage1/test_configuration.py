import pytest

from config.environments import DatabaseConfigurationError, Environment, load_config


def test_profiles_and_storage_contract(monkeypatch):
    dev = load_config(Environment.DEV)
    assert dev.database_url.startswith("sqlite:///")
    assert "PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST" in dev.database_url
    assert "192.168.1.58" not in dev.database_url
    monkeypatch.delenv("HMS_QR_DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError):
        load_config(Environment.PROD)
