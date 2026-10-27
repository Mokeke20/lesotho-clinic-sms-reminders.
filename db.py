"""Database connection and table definitions (SQLite)."""
import sqlite3
from flask import g
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, code TEXT UNIQUE, phone TEXT, lang TEXT,
  opted_out INTEGER DEFAULT 0, consent_at TEXT);
CREATE TABLE IF NOT EXISTS appts(id INTEGER PRIMARY KEY, client_id INTEGER, day TEXT,
  status TEXT DEFAULT 'scheduled');  -- scheduled|confirmed|reschedule|attended|missed
CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, appt_id INTEGER, kind TEXT, sent_on TEXT, ok INTEGER);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(config.DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.executescript(SCHEMA)
    return g.db


def close_db(_=None):
    d = g.pop("db", None)
    if d:
        d.close()
