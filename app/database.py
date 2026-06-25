import sqlite3
import os
import logging
from contextlib import contextmanager

# Logging-Setup
logger = logging.getLogger(__name__)

DB_PATH = os.getenv('DB_PATH', '/app/data/dns_records.db')


@contextmanager
def get_db_connection():
    """Context manager that always closes the connection (no FD leaks).

    WAL + busy_timeout make the DB resilient to the periodic reconcile reading
    while the event listener writes.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')
        yield conn
    finally:
        conn.close()


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _dns_name_in_pk(conn):
    """True if dns_name is part of the primary key (new multi-record schema)."""
    for col in conn.execute("PRAGMA table_info(dns_records)").fetchall():
        if col['name'] == 'dns_name' and col['pk'] > 0:
            return True
    return False


def init_db():
    """Create the schema (composite PK so one container can own many records),
    migrating the old single-record schema in place. Raises on failure."""
    try:
        with get_db_connection() as conn:
            migrated = False
            if _table_exists(conn, 'dns_records') and not _dns_name_in_pk(conn):
                # migrate old (container_id PRIMARY KEY) -> composite key
                conn.execute('ALTER TABLE dns_records RENAME TO dns_records_old')
                migrated = True
            conn.execute('''
                CREATE TABLE IF NOT EXISTS dns_records (
                    container_id TEXT NOT NULL,
                    dns_name TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    PRIMARY KEY (container_id, dns_name)
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_dns_name ON dns_records(dns_name)')
            if migrated:
                conn.execute('''INSERT OR IGNORE INTO dns_records (container_id, dns_name, ip)
                                SELECT container_id, dns_name, ip FROM dns_records_old''')
                conn.execute('DROP TABLE dns_records_old')
                logger.info("🔀 DB-Schema auf Multi-Record migriert.")
            conn.commit()
        logger.info("📦 SQLite-Datenbank initialisiert.")
    except Exception as e:
        logger.error(f"❌ Fehler bei der DB-Initialisierung: {e}")
        raise


def update_record(container_id, dns_name, ip):
    """Insert/update one (container_id, dns_name) record."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                'REPLACE INTO dns_records (container_id, dns_name, ip) VALUES (?, ?, ?)',
                (container_id, dns_name, ip))
            conn.commit()
        logger.info(f"📝 DB-Eintrag aktualisiert: {container_id} → {dns_name} → {ip}")
    except Exception as e:
        logger.error(f"❌ Fehler beim DB-Update für {container_id}/{dns_name}: {e}")
        raise


def delete_record(container_id, dns_name=None):
    """Delete one record (container_id, dns_name) or, if dns_name is None,
    every record for the container."""
    try:
        with get_db_connection() as conn:
            if dns_name is None:
                conn.execute('DELETE FROM dns_records WHERE container_id = ?', (container_id,))
            else:
                conn.execute('DELETE FROM dns_records WHERE container_id = ? AND dns_name = ?',
                             (container_id, dns_name))
            conn.commit()
        logger.info(f"🗑️ DB-Eintrag gelöscht: {container_id}{'' if dns_name is None else '/' + dns_name}")
    except Exception as e:
        logger.error(f"❌ Fehler beim Löschen aus DB für {container_id}: {e}")
        raise


def get_records(container_id):
    """Return the list of dns_names a container owns (possibly several)."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                'SELECT dns_name FROM dns_records WHERE container_id = ?',
                (container_id,)).fetchall()
        return [r['dns_name'] for r in rows]
    except Exception as e:
        logger.error(f"❌ Fehler beim Lesen aus DB für {container_id}: {e}")
        return []


def get_all_records():
    """Return every record as a list of (container_id, dns_name, ip). Used by reconcile."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                'SELECT container_id, dns_name, ip FROM dns_records').fetchall()
        return [(r['container_id'], r['dns_name'], r['ip']) for r in rows]
    except Exception as e:
        logger.error(f"❌ Fehler beim Lesen aller DB-Einträge: {e}")
        return []


def dns_name_claimed_by_other(container_id, dns_name):
    """True if a DIFFERENT container_id already owns this dns_name.

    Guards against a stale `die` event (old container) deleting a DNS record that
    a freshly-(re)created container with the same name now legitimately owns.
    """
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                'SELECT 1 FROM dns_records WHERE dns_name = ? AND container_id != ? LIMIT 1',
                (dns_name, container_id)).fetchone()
        return row is not None
    except Exception as e:
        logger.error(f"❌ Fehler bei der Claim-Prüfung für {dns_name}: {e}")
        # fail safe: assume claimed so we do NOT delete a possibly-live record
        return True
