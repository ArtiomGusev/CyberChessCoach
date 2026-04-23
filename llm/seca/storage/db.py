import sqlite3
from pathlib import Path

DB_PATH = Path("data/seca.db")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    schema = Path(__file__).with_name("schema.sql").read_text()
    conn.executescript(schema)
    conn.commit()
    conn.close()
