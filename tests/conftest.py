import pytest


class FakeProvider:
    """Records create/delete calls; can be told to fail create_record."""

    def __init__(self):
        self.created = []   # list of (name, content)
        self.deleted = []   # list of name
        self.fail_create = False

    def create_record(self, name, content, record_type="A", ttl=300):
        if self.fail_create:
            raise RuntimeError("PowerDNS 422")
        self.created.append((name, content))

    def delete_record(self, name, record_type="A"):
        self.deleted.append(name)


class FakeContainer:
    def __init__(self, cid, name, labels):
        self.id = cid
        self.short_id = cid[:12]
        self.name = name
        self.labels = labels


def custom_labels(service, host, domain, wildcard=False):
    return {
        f"auto-dns.customDNS.{service}": "true",
        f"auto-dns.customDOMAIN.{service}": domain,
        f"auto-dns.customHost.{service}": host,
        f"auto-dns.createWildcard.{service}": "true" if wildcard else "false",
    }


@pytest.fixture
def db(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    return database


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def sync(db, provider, monkeypatch):
    """dns_sync wired to the temp DB + fake provider + a host IP."""
    import dns_sync
    monkeypatch.setenv("PDNS_HOST_IP", "10.0.0.5")
    monkeypatch.setattr(dns_sync, "_provider", provider)
    return dns_sync
