import os
import sqlite3
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
DB_PATH = os.path.join(LOG_DIR, "events.db")
TXT_PATH = os.path.join(LOG_DIR, "events.log")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, system TEXT, kind TEXT, name TEXT,
            vid TEXT, pid TEXT, decision TEXT, reason TEXT)"""
    )
    return conn


def log_event(system, kind, name, vid, pid, decision, reason=""):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{system}] {kind:6} {vid}:{pid} {name!r} -> {decision} ({reason})"
    print(line, flush=True)
    with open(TXT_PATH, "a") as f:
        f.write(line + "\n")
    conn = _connect()
    conn.execute(
        "INSERT INTO events (ts, system, kind, name, vid, pid, decision, reason) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (ts, system, kind, name, vid, pid, decision, reason),
    )
    conn.commit()
    conn.close()
