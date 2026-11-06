import sqlite3
from pathlib import Path

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = Path(current_app.config["DATABASE"])
        path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: controlamos las transacciones a mano (BEGIN IMMEDIATE)
        conn = sqlite3.connect(path, isolation_level=None, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    db = get_db()
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    db.executescript(schema)
    cols = {r["name"] for r in db.execute("PRAGMA table_info(reservas)")}
    if "asiento" not in cols:      # migración de bases creadas con la versión anterior
        db.execute("ALTER TABLE reservas ADD COLUMN asiento INTEGER")


def init_app(app):
    app.teardown_appcontext(close_db)
