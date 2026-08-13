from config.environments import Environment, load_config


def test_profiles_and_storage_contract():
    dev = load_config(Environment.DEV)
    prod = load_config(Environment.PROD)
    assert dev.database_url.startswith("sqlite:///")
    assert "PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST" in dev.database_url
    assert prod.storage_backend == "nas"
    assert "192.168.1.58" not in dev.database_url
