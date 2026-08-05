"""
Database configuration and session management.

Persistence hardening:
  - Absolute DB path derived from this module location (robust against cwd changes)
  - SQLite WAL journal mode + synchronous=NORMAL for durability under concurrency
  - Pre-migration backup + startup consistency check
  - Connection pool tuning + slow-query logging + performance counters
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

# ── Resolve an absolute data directory (independent of the process cwd) ───────
# database.py lives in backend/app/, so ../../data → <repo>/data.
DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
)
os.makedirs(DATA_DIR, exist_ok=True)

_DEFAULT_DB_PATH = os.path.join(DATA_DIR, "gather.db")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

# ── Performance counters ──────────────────────────────────────────────────────
_QUERY_COUNT: int = 0
_SLOW_QUERY_COUNT: int = 0
_SLOW_QUERY_THRESHOLD_SEC = 1.0
_CONNECTION_COUNT: int = 0


def _db_file_path() -> str | None:
    """Return the on-disk path for a sqlite URL, else None."""
    if not _IS_SQLITE:
        return None
    path = DATABASE_URL.replace("sqlite:///", "", 1)
    return os.path.abspath(path)


# Ensure the directory for the configured DB exists
_db_path = _db_file_path()
if _db_path:
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)

# ── Engine creation with pool tuning ──────────────────────────────────────────
_pool_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
}

if _IS_SQLITE:
    # SQLite does not benefit from large pools; keep it conservative.
    _pool_kwargs["pool_size"] = 5
    _pool_kwargs["max_overflow"] = 10
    _pool_kwargs["pool_timeout"] = 30
    _pool_kwargs["pool_recycle"] = 1800
    _pool_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / MySQL defaults
    _pool_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
    _pool_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    _pool_kwargs["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    _pool_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "1800"))

engine = create_engine(DATABASE_URL, echo=False, **_pool_kwargs)


# ── SQLite PRAGMA + connection tracking ─────────────────────────────────────

if _IS_SQLITE:
    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        """Enable WAL + NORMAL synchronous on every SQLite connection."""
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to set SQLite PRAGMA: %s", exc)


@event.listens_for(Engine, "checkout")
def _on_connection_checkout(dbapi_conn, connection_record, connection_proxy):
    """Track active connections."""
    global _CONNECTION_COUNT
    _CONNECTION_COUNT += 1


@event.listens_for(Engine, "checkin")
def _on_connection_checkin(dbapi_conn, connection_record):
    """Track connection returns."""
    global _CONNECTION_COUNT
    _CONNECTION_COUNT = max(0, _CONNECTION_COUNT - 1)


# ── Slow-query logging ──────────────────────────────────────────────────────

@event.listens_for(Engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.perf_counter()


@event.listens_for(Engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    global _QUERY_COUNT, _SLOW_QUERY_COUNT
    duration = time.perf_counter() - context._query_start_time
    _QUERY_COUNT += 1
    if duration > _SLOW_QUERY_THRESHOLD_SEC:
        _SLOW_QUERY_COUNT += 1
        logger.warning(
            "Slow query (%.2fs): %s",
            duration,
            statement[:200].replace("\n", " "),
        )


# ── Session factory ───────────────────────────────────────────────────────────

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _backup_db():
    """Back up the SQLite DB file before applying schema migrations."""
    path = _db_file_path()
    if not path or not os.path.exists(path):
        return
    try:
        shutil.copy(path, path + ".bak")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("DB backup failed: %s", exc)


def _consistency_check():
    """Warn if the DB file looks suspiciously small (possible data loss)."""
    path = _db_file_path()
    if not path or not os.path.exists(path):
        return
    try:
        size = os.path.getsize(path)
        if size < 1024:
            logger.warning(
                "Database file %s is only %d bytes — it may be empty or corrupted.",
                path, size,
            )
    except OSError:
        pass


def init_db():
    """Create all tables + apply schema migrations (with backup)."""
    _consistency_check()
    _backup_db()
    Base.metadata.create_all(bind=engine)
    # Apply schema additions (new models, column alterations)
    from app.models_additions import migrate_schema
    migrate_schema(engine)
    # Older releases could seed a second built-in default model. Keep all
    # existing records, but restore the user's effective default deterministically.
    from app.model_defaults import reconcile_default_model
    db = SessionLocal()
    try:
        if reconcile_default_model(db):
            db.commit()
        from app.source_profile_registry import reconcile_verified_source_profiles
        reconcile_verified_source_profiles(db)
    finally:
        db.close()
    logger.info("Database ready at %s", _db_file_path() or DATABASE_URL)


# ── Performance metrics helpers ───────────────────────────────────────────────

def get_db_metrics() -> dict[str, Any]:
    """Return current database performance counters."""
    return {
        "query_count": _QUERY_COUNT,
        "slow_query_count": _SLOW_QUERY_COUNT,
        "active_connections": _CONNECTION_COUNT,
        "pool_size": _pool_kwargs.get("pool_size"),
        "max_overflow": _pool_kwargs.get("max_overflow"),
    }


def check_db_connection() -> bool:
    """Quick connectivity check."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("DB connection check failed: %s", exc)
        return False
