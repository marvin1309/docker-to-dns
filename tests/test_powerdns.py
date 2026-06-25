import pytest
import requests


class FakeResponse:
    def __init__(self, status=200):
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    def __init__(self, status=200):
        self.status = status
        self.calls = []
        self.headers = {}

    def patch(self, url, json=None, timeout=None):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(self.status)

    def mount(self, *a, **k):
        pass


@pytest.fixture
def pdns_env(monkeypatch):
    monkeypatch.setenv("PDNS_API_URL", "http://pdns:8081/api/v1")
    monkeypatch.setenv("PDNS_API_KEY", "secret")
    monkeypatch.setenv("PDNS_ZONE", "int.example.com")


def make_provider(status=200):
    from providers.powerdns import PowerDNSProvider
    p = PowerDNSProvider()
    p.session = FakeSession(status)
    return p


def test_missing_env_raises(monkeypatch):
    for v in ("PDNS_API_URL", "PDNS_API_KEY", "PDNS_ZONE"):
        monkeypatch.delenv(v, raising=False)
    from providers.powerdns import PowerDNSProvider
    with pytest.raises(ValueError):
        PowerDNSProvider()


def test_create_record_success_and_timeout(pdns_env):
    p = make_provider(200)
    p.create_record("web.int.example.com", "10.0.0.5")
    call = p.session.calls[0]
    assert call["timeout"] == p.timeout
    rr = call["json"]["rrsets"][0]
    assert rr["name"] == "web.int.example.com."
    assert rr["changetype"] == "REPLACE"
    assert rr["records"][0]["content"] == "10.0.0.5"


def test_create_record_raises_on_http_error(pdns_env):
    p = make_provider(422)
    with pytest.raises(requests.RequestException):
        p.create_record("web.int.example.com", "10.0.0.5")


def test_delete_record_best_effort_does_not_raise(pdns_env):
    p = make_provider(500)
    # delete must swallow errors so cleanup of other records continues
    p.delete_record("web.int.example.com")
    assert p.session.calls[0]["json"]["rrsets"][0]["changetype"] == "DELETE"


def test_timeout_configurable(pdns_env, monkeypatch):
    monkeypatch.setenv("PDNS_API_TIMEOUT", "3")
    p = make_provider(200)
    assert p.timeout == 3.0
