import sqlite3
from datetime import datetime

DB_FILE = "handles.db"

def get_conn():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS handles (
            handle TEXT PRIMARY KEY,
            post_id TEXT,
            content TEXT,
            post_time TEXT,
            last_checked TEXT
        )
    """)
    conn.commit()
    conn.close()

def upsert_handle(handle, post_id, content, post_time):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO handles(handle, post_id, content, post_time, last_checked)
        VALUES(?,?,?,?,?)
        ON CONFLICT(handle) DO UPDATE SET
            post_id=excluded.post_id,
            content=excluded.content,
            post_time=excluded.post_time,
            last_checked=excluded.last_checked
    """, (
        handle,
        post_id,
        content,
        post_time,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()

def get_all():
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM handles").fetchall()
    conn.close()
    return rows

