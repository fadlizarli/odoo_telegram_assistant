import sqlite3
from datetime import datetime
import config

def _conn():
    return sqlite3.connect(config.MEMORY_DB_PATH)

def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                chat_id TEXT PRIMARY KEY,
                partner_id INTEGER,
                name TEXT,
                phone TEXT,
                registered_at TEXT
            )
        """)
        conn.commit()

def save_message(chat_id: str, role: str, message: str):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO chat_history (phone, role, message, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, role, message, datetime.now().isoformat())
        )
        conn.commit()

def get_history(chat_id: str, limit: int = 8) -> list:
    with _conn() as conn:
        cursor = conn.execute(
            "SELECT role, message FROM chat_history WHERE phone = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        )
        rows = cursor.fetchall()
    rows.reverse()
    return [{"role": r[0], "content": r[1]} for r in rows]

def register_customer(chat_id: str, partner_id: int, name: str, phone: str):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO customers (chat_id, partner_id, name, phone, registered_at) VALUES (?, ?, ?, ?, ?)",
            (chat_id, partner_id, name, phone, datetime.now().isoformat())
        )
        conn.commit()

def get_customer(chat_id: str):
    with _conn() as conn:
        cursor = conn.execute(
            "SELECT chat_id, partner_id, name, phone FROM customers WHERE chat_id = ?",
            (chat_id,)
        )
        row = cursor.fetchone()
    if row:
        return {"chat_id": row[0], "partner_id": row[1], "name": row[2], "phone": row[3]}
    return None

def clear_history(chat_id: str):
    with _conn() as conn:
        conn.execute("DELETE FROM chat_history WHERE phone = ?", (chat_id,))
        conn.commit()

def save_state(chat_id: str, state: str):
    """Simpan state sementara user"""
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO chat_history (phone, role, message, created_at) VALUES (?, ?, ?, ?)",
            (f"state_{chat_id}", "state", state, datetime.now().isoformat())
        )
        conn.commit()

def get_state(chat_id: str) -> str:
    """Ambil state user"""
    with _conn() as conn:
        cursor = conn.execute(
            "SELECT message FROM chat_history WHERE phone = ? AND role = 'state' ORDER BY id DESC LIMIT 1",
            (f"state_{chat_id}",)
        )
        row = cursor.fetchone()
    return row[0] if row else None

def clear_state(chat_id: str):
    """Hapus state user"""
    with _conn() as conn:
        conn.execute("DELETE FROM chat_history WHERE phone = ? AND role = 'state'", (f"state_{chat_id}",))
        conn.commit()
