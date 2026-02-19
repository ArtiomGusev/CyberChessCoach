import sqlite3
from pathlib import Path

DB_PATH = Path("data/seca.db")


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    schema = Path(__file__).with_name("schema.sql").read_text()
    conn.executescript(schema)
    conn.commit()
    conn.close()
