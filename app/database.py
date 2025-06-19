import sqlite3
import os

DB_PATH = os.getenv('DB_PATH', '/app/data/dns_records.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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

def update_record(container_id, dns_name, ip):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('REPLACE INTO dns_records (container_id, dns_name, ip) VALUES (?, ?, ?)',
                   (container_id, dns_name, ip))
    conn.commit()
    conn.close()

def delete_record(container_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM dns_records WHERE container_id = ?', (container_id,))
    conn.commit()
    conn.close()

def get_record(container_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT dns_name FROM dns_records WHERE container_id = ?', (container_id,))
    row = cursor.fetchone()
    conn.close()
    return row['dns_name'] if row else None
