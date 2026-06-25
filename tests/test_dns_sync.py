import pytest
from conftest import FakeContainer, custom_labels


def multi_labels(*specs):
    """Merge several custom_labels() dicts (one per service)."""
    out = {}
    for service, host, domain in specs:
        out.update(custom_labels(service, host, domain))
    return out


def test_build_dns_name_custom(sync):
    name = sync.build_dns_name(custom_labels("svc", "web", "int.example.com"), "svc")
    assert name == "web.int.example.com"


def test_build_dns_name_missing_raises(sync):
    with pytest.raises(ValueError):
        sync.build_dns_name({"auto-dns.customDNS.svc": "true"}, "svc")


def test_desired_records_skips_invalid(sync):
    c = FakeContainer("c1", "bad", {"auto-dns.customDNS.bad": "true"})
    assert sync.desired_records(c) == []


def test_desired_records_multiple(sync):
    labels = multi_labels(("a", "web", "int.example.com"), ("b", "api", "int.example.com"))
    c = FakeContainer("c1", "multi", labels)
    names = sorted(n for n, _ in sync.desired_records(c))
    assert names == ["api.int.example.com", "web.int.example.com"]


def test_process_container_creates_record_and_db(sync, provider, db):
    c = FakeContainer("c1", "web", custom_labels("svc", "web", "int.example.com"))
    sync.process_container(c)
    assert ("web.int.example.com", "10.0.0.5") in provider.created
    assert db.get_records("c1") == ["web.int.example.com"]


def test_process_container_multiple_dns(sync, provider, db):
    labels = multi_labels(("a", "web", "int.example.com"), ("b", "api", "int.example.com"))
    c = FakeContainer("c1", "multi", labels)
    sync.process_container(c)
    created = {n for n, _ in provider.created}
    assert created == {"web.int.example.com", "api.int.example.com"}
    assert sorted(db.get_records("c1")) == ["api.int.example.com", "web.int.example.com"]


def test_process_drops_record_no_longer_declared(sync, provider, db):
    labels = multi_labels(("a", "web", "int.example.com"), ("b", "api", "int.example.com"))
    c = FakeContainer("c1", "multi", labels)
    sync.process_container(c)
    # container now declares only "web" (api label removed) -> api must be cleaned up
    c.labels = custom_labels("a", "web", "int.example.com")
    sync.process_container(c)
    assert "api.int.example.com" in provider.deleted
    assert db.get_records("c1") == ["web.int.example.com"]


def test_process_container_wildcard(sync, provider):
    c = FakeContainer("c1", "web", custom_labels("svc", "web", "int.example.com", wildcard=True))
    sync.process_container(c)
    assert ("web.int.example.com", "10.0.0.5") in provider.created
    assert ("*.web.int.example.com", "10.0.0.5") in provider.created


def test_db_not_written_when_create_fails(sync, provider, db):
    provider.fail_create = True
    c = FakeContainer("c1", "web", custom_labels("svc", "web", "int.example.com"))
    sync.process_container(c)
    assert db.get_records("c1") == []


def test_process_container_no_host_ip(sync, provider, monkeypatch):
    monkeypatch.delenv("PDNS_HOST_IP", raising=False)
    c = FakeContainer("c1", "web", custom_labels("svc", "web", "int.example.com"))
    sync.process_container(c)
    assert provider.created == []


def test_remove_container_deletes_all_dns_and_db(sync, provider, db):
    labels = multi_labels(("a", "web", "int.example.com"), ("b", "api", "int.example.com"))
    c = FakeContainer("c1", "multi", labels)
    sync.process_container(c)
    sync.remove_container("c1")
    assert "web.int.example.com" in provider.deleted
    assert "api.int.example.com" in provider.deleted
    assert db.get_records("c1") == []


def test_remove_container_keeps_record_claimed_by_other(sync, provider, db):
    db.update_record("old", "web.int.example.com", "10.0.0.5")
    db.update_record("new", "web.int.example.com", "10.0.0.5")
    sync.remove_container("old")  # stale die event
    assert "web.int.example.com" not in provider.deleted
    assert db.get_records("old") == []
    assert db.get_records("new") == ["web.int.example.com"]


def test_reconcile_removes_orphans(sync, provider, db):
    db.update_record("gone", "orphan.int.example.com", "10.0.0.5")
    sync.reconcile([])
    assert "orphan.int.example.com" in provider.deleted
    assert db.get_records("gone") == []


def test_reconcile_creates_missing_multi(sync, provider, db):
    labels = multi_labels(("a", "web", "int.example.com"), ("b", "api", "int.example.com"))
    c = FakeContainer("c1", "multi", labels)
    sync.reconcile([c])
    created = {n for n, _ in provider.created}
    assert created == {"web.int.example.com", "api.int.example.com"}
    assert sorted(db.get_records("c1")) == ["api.int.example.com", "web.int.example.com"]


def test_reconcile_idempotent_no_duplicate_create(sync, provider, db):
    c = FakeContainer("c1", "web", custom_labels("svc", "web", "int.example.com"))
    sync.reconcile([c])
    provider.created.clear()
    sync.reconcile([c])
    assert provider.created == []


def test_reconcile_keeps_shared_name(sync, provider, db):
    # orphan row for old id, but a running container still wants the same name
    db.update_record("old", "web.int.example.com", "10.0.0.5")
    c = FakeContainer("new", "web", custom_labels("svc", "web", "int.example.com"))
    sync.reconcile([c])
    # old row removed from DB, but DNS NOT deleted (new still owns the name)
    assert "web.int.example.com" not in provider.deleted
    assert db.get_records("old") == []
    assert db.get_records("new") == ["web.int.example.com"]
