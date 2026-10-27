import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings

SCHEMA = Path(__file__).with_name("schema.sql")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    s = get_settings()
    s.db_path.parent.mkdir(parents=True, exist_ok=True)
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA.read_text())
        conn.commit()
    finally:
        conn.close()


def get_db():
    conn = connect()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
