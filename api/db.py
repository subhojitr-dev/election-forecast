"""
db.py — read-only SQLite access for the API
Election Forecast Dashboard (Phase 4)
"""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "db", "baseline.db")


def get_conn():
    """A fresh connection per request (SQLite + threads). Row access by name."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")   # wait for locks instead of erroring
    conn.execute("PRAGMA synchronous=NORMAL")    # safe under WAL, fewer fsyncs
    return conn
