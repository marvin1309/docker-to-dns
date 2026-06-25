def test_update_and_get(db):
    db.update_record("c1", "a.example.com", "10.0.0.1")
    assert db.get_records("c1") == ["a.example.com"]


def test_get_missing_returns_empty(db):
    assert db.get_records("nope") == []


def test_multiple_records_per_container(db):
    db.update_record("c1", "a.example.com", "10.0.0.1")
    db.update_record("c1", "b.example.com", "10.0.0.1")
    assert sorted(db.get_records("c1")) == ["a.example.com", "b.example.com"]


def test_replace_same_pair_is_idempotent(db):
    db.update_record("c1", "a.example.com", "10.0.0.1")
    db.update_record("c1", "a.example.com", "10.0.0.2")  # same pair, new ip
    assert db.get_records("c1") == ["a.example.com"]
    assert db.get_all_records() == [("c1", "a.example.com", "10.0.0.2")]


def test_delete_specific_record(db):
    db.update_record("c1", "a.example.com", "10.0.0.1")
    db.update_record("c1", "b.example.com", "10.0.0.1")
    db.delete_record("c1", "a.example.com")
    assert db.get_records("c1") == ["b.example.com"]


def test_delete_all_for_container(db):
    db.update_record("c1", "a.example.com", "10.0.0.1")
    db.update_record("c1", "b.example.com", "10.0.0.1")
    db.delete_record("c1")
    assert db.get_records("c1") == []


def test_get_all_records(db):
    db.update_record("c1", "a.example.com", "10.0.0.1")
    db.update_record("c2", "b.example.com", "10.0.0.2")
    rows = sorted(db.get_all_records())
    assert rows == [("c1", "a.example.com", "10.0.0.1"),
                    ("c2", "b.example.com", "10.0.0.2")]


def test_dns_name_claimed_by_other(db):
    db.update_record("c1", "shared.example.com", "10.0.0.1")
    assert db.dns_name_claimed_by_other("c2", "shared.example.com") is True
    assert db.dns_name_claimed_by_other("c1", "shared.example.com") is False
    assert db.dns_name_claimed_by_other("c2", "free.example.com") is False


def test_migration_from_old_schema(tmp_path, monkeypatch):
    """Old single-record schema (container_id PRIMARY KEY) migrates in place."""
    import sqlite3
    import database
    dbfile = str(tmp_path / "old.db")
    monkeypatch.setattr(database, "DB_PATH", dbfile)
    conn = sqlite3.connect(dbfile)
    conn.execute('CREATE TABLE dns_records (container_id TEXT PRIMARY KEY, '
                 'dns_name TEXT NOT NULL, ip TEXT NOT NULL)')
    conn.execute("INSERT INTO dns_records VALUES ('c1','a.example.com','10.0.0.1')")
    conn.commit(); conn.close()

    database.init_db()  # should migrate, preserving the row
    assert database.get_records("c1") == ["a.example.com"]
    # and now supports multiple records per container
    database.update_record("c1", "b.example.com", "10.0.0.1")
    assert sorted(database.get_records("c1")) == ["a.example.com", "b.example.com"]
