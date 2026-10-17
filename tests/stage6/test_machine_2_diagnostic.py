from apps.desktop.lan_diagnostic import run_check


def test_machine_2_diagnostic_uses_discovery_readiness_login_and_stage2_read():
    calls = []

    class ProductClient:
        access_token = "session-token"

        def __init__(self, server_url):
            calls.append(("client", server_url))

        def verify_server_readiness(self):
            calls.append(("product-readiness",))

        def login(self, username, password):
            calls.append(("login", username, password))
            return {"role": "EDITOR"}

    class Stage2Client:
        def __init__(self, server_url, *, access_token):
            calls.append(("stage2-client", server_url, access_token))

        def list_customers(self):
            calls.append(("stage2-read",))

    assert run_check(
        discover=lambda: "http://192.168.2.15:8010",
        ready=lambda url: url == "http://192.168.2.15:8010",
        client_factory=ProductClient,
        stage2_factory=Stage2Client,
        username="editor", password="not-logged",
    ) == ("http://192.168.2.15:8010", "EDITOR")
    assert calls == [
        ("client", "http://192.168.2.15:8010"), ("product-readiness",),
        ("login", "editor", "not-logged"),
        ("stage2-client", "http://192.168.2.15:8010", "session-token"), ("stage2-read",),
    ]


def test_machine_2_diagnostic_refuses_missing_udp_discovery():
    try:
        run_check(discover=lambda: None, username="user", password="secret")
    except RuntimeError as exc:
        assert "UDP 8011" in str(exc)
    else:
        raise AssertionError("missing UDP discovery must fail")
