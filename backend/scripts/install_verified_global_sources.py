"""Install the audited official-source catalog into the configured database."""
from __future__ import annotations

import argparse

from app.database import SessionLocal, init_db
from app.verified_source_catalog import CATALOG_SOURCE_IDS, install_verified_global_sources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="persist the catalog")
    parser.add_argument(
        "--refresh-managed", action="store_true",
        help="refresh the catalog-managed rows before re-verification",
    )
    parser.add_argument("--topic-id", default="global-trade")
    args = parser.parse_args()
    if not args.apply:
        print("DRY RUN: would install/bind " + ", ".join(CATALOG_SOURCE_IDS))
        return 0

    init_db()
    db = SessionLocal()
    try:
        result = install_verified_global_sources(
            db,
            topic_id=args.topic_id,
            refresh_managed=args.refresh_managed,
        )
        print(result)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
