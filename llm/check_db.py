import sqlite3

conn = sqlite3.connect("data/seca.db")
cur = conn.cursor()

tables = ["players", "game_events", "rating_updates", "confidence_updates"]

for table in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(table, cur.fetchone()[0])
    except Exception as e:
        print(table, "ERROR:", e)

conn.close()
