"""Import operator-provided XLSX source directories and article targets."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from dataclasses import asdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _backup_sqlite(database_url: str, backup_dir: Path) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    source = Path(database_url.removeprefix("sqlite:///"))
    if not source.is_file():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{source.stem}-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(source) as source_db, sqlite3.connect(target) as target_db:
        source_db.backup(target_db)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--database-url")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    if not args.directory.is_dir() or not args.manifest.is_file():
        raise SystemExit("工作簿目录或主题清单不存在")

    from app.database import DATABASE_URL, SessionLocal, init_db
    from app.workbook_source_import import import_workbook_directory

    backup = None if args.dry_run else _backup_sqlite(
        DATABASE_URL,
        args.backup_dir or Path(__file__).resolve().parents[2] / "data" / "backups",
    )
    if not args.dry_run:
        init_db()
    db = SessionLocal()
    try:
        summary = import_workbook_directory(db, args.directory, args.manifest)
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        output = {**asdict(summary), "mode": "dry-run" if args.dry_run else "committed"}
        if backup:
            output["backup"] = str(backup)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
