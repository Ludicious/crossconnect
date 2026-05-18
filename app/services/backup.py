"""
SQLite backup and restore service.
Postgres is explicitly out of scope — raises RuntimeError if attempted.
"""
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.settings import AppSetting


def _db_path() -> Path:
    url = app_settings.database_url
    if not url.startswith("sqlite"):
        raise RuntimeError(
            "Backup/restore is only supported for SQLite databases. "
            "For PostgreSQL, use pg_dump / pg_restore."
        )
    # sqlite:///./file.db  →  ./file.db
    # sqlite:////abs/path  →  /abs/path
    path_str = url.removeprefix("sqlite:///")
    return Path(path_str)


def create_backup(db: Session) -> bytes:
    """
    Return raw bytes of the current SQLite database.
    Uses shutil.copy to a temp file to avoid reading a partially-written DB.
    Records the timestamp in app_settings key 'last_backup_at'.
    """
    db_path = _db_path()

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        shutil.copy2(str(db_path), str(tmp_path))
        data = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    now_iso = datetime.utcnow().isoformat()
    row = db.get(AppSetting, "last_backup_at")
    if row:
        row.value = now_iso
    else:
        db.add(AppSetting(
            key="last_backup_at",
            value=now_iso,
            description="Timestamp of last manual backup (UTC ISO format)",
        ))
    db.commit()
    return data


def restore_backup(db: Session, file_bytes: bytes) -> None:
    """
    Validate and restore a SQLite backup file.

    Validates:
      - file starts with SQLite magic bytes
      - backup contains alembic_version table
      - alembic version in backup matches current DB

    On success: disposes engine, replaces DB file, next request reconnects.
    Raises ValueError with a user-friendly message on any validation failure.
    """
    SQLITE_MAGIC = b"SQLite format 3\x00"
    if not file_bytes.startswith(SQLITE_MAGIC):
        raise ValueError("Not a valid SQLite database file.")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        conn_check = sqlite3.connect(str(tmp_path))
        try:
            cur = conn_check.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
            )
            if not cur.fetchone():
                raise ValueError(
                    "Backup does not contain an alembic_version table. "
                    "This may not be a CrossConnect database."
                )
            cur.execute("SELECT version_num FROM alembic_version")
            row = cur.fetchone()
            if not row:
                raise ValueError("alembic_version table is empty in the backup file.")
            backup_version = row[0]
        finally:
            conn_check.close()

        from sqlalchemy import text
        from app.db import engine
        with engine.connect() as live_conn:
            result = live_conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            current_version = result[0] if result else None

        if backup_version != current_version:
            raise ValueError(
                f"Schema version mismatch: backup is at '{backup_version}', "
                f"current database is at '{current_version}'. "
                f"The backup cannot be safely restored without running migrations first."
            )

        db_path = _db_path()
        db.close()
        engine.dispose()
        shutil.copy2(str(tmp_path), str(db_path))

    finally:
        tmp_path.unlink(missing_ok=True)


def get_last_backup_time(db: Session) -> Optional[str]:
    """Read 'last_backup_at' from app_settings. Returns None if unset."""
    row = db.get(AppSetting, "last_backup_at")
    return row.value if row else None
