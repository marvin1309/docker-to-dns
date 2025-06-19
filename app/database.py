import sqlite3
import os
import logging

# Logging-Setup
logger = logging.getLogger(__name__)

DB_PATH = os.getenv('DB_PATH', '/app/data/dns_records.db')

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"❌ Fehler beim Öffnen der DB-Verbindung: {e}")
        raise

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dns_records (
                container_id TEXT PRIMARY KEY,
                dns_name TEXT NOT NULL,
                ip TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("📦 SQLite-Datenbank initialisiert.")
    except Exception as e:
        logger.error(f"❌ Fehler bei der DB-Initialisierung: {e}")

def update_record(container_id, dns_name, ip):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('REPLACE INTO dns_records (container_id, dns_name, ip) VALUES (?, ?, ?)',
                       (container_id, dns_name, ip))
        conn.commit()
        conn.close()
        logger.info(f"📝 DB-Eintrag aktualisiert: {container_id} → {dns_name} → {ip}")
    except Exception as e:
        logger.error(f"❌ Fehler beim DB-Update für {container_id}: {e}")

def delete_record(container_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM dns_records WHERE container_id = ?', (container_id,))
        conn.commit()
        conn.close()
        logger.info(f"🗑️ DB-Eintrag gelöscht: {container_id}")
    except Exception as e:
        logger.error(f"❌ Fehler beim Löschen aus DB für {container_id}: {e}")

def get_record(container_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT dns_name FROM dns_records WHERE container_id = ?', (container_id,))
        row = cursor.fetchone()
        conn.close()
        return row['dns_name'] if row else None
    except Exception as e:
        logger.error(f"❌ Fehler beim Lesen aus DB für {container_id}: {e}")
        return None
