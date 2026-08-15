"""CLI for importing a source inventory CSV into GatherInfo."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--database-url")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reclassify-all", action="store_true")
    args = parser.parse_args()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    from app.database import SessionLocal, init_db
    from app.models import SourceConfig
    from app.source_inventory_import import import_source_inventory, load_inventory
    from app.source_taxonomy import determine_source_group
    rows = load_inventory(args.csv_path)
    init_db()
    db = SessionLocal()
    try:
        result = import_source_inventory(db, rows)
        if result["conflicts"]:
            raise RuntimeError(
                "Unresolved source inventory conflicts: "
                f"{result['conflicts']}"
            )
        if args.reclassify_all:
            changed = 0
            for source in db.query(SourceConfig).all():
                group = determine_source_group(source)
                if source.source_group != group:
                    source.source_group = group
                    changed += 1
            result["reclassified"] = changed
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        for key, value in result.items():
            print(f"{key}={value}")
        print(f"mode={'dry-run' if args.dry_run else 'committed'}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
