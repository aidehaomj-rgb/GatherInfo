"""
SQLite FTS5 full-text search for collected items.

Provides init_fts() to create the FTS virtual table and triggers,
and search_items() for querying with title:/content: syntax support.
"""
import logging
import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import CollectedItem

logger = logging.getLogger(__name__)

FTS_TABLE = "collected_items_fts"


def init_fts(engine: Engine):
    """Create FTS5 virtual table and sync triggers if not exists."""
    with engine.connect() as conn:
        # Create FTS5 table
        try:
            conn.execute(text(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
                    item_id UNINDEXED,
                    title,
                    content,
                    summary,
                    tokenize='unicode61'
                )
            """))
            conn.commit()
        except Exception as exc:
            logger.warning("FTS table creation skipped: %s", exc)
            return

        # Create triggers for auto-sync (INSERT / UPDATE / DELETE)
        for op, timing in [("INSERT", "AFTER"), ("UPDATE", "AFTER"), ("DELETE", "AFTER")]:
            trigger_name = f"trg_fts_{op.lower()}"
            try:
                if op == "DELETE":
                    conn.execute(text(f"""
                        CREATE TRIGGER IF NOT EXISTS {trigger_name}
                        AFTER DELETE ON collected_items
                        BEGIN
                            DELETE FROM {FTS_TABLE} WHERE item_id = OLD.id;
                        END
                    """))
                else:
                    conn.execute(text(f"""
                        CREATE TRIGGER IF NOT EXISTS {trigger_name}
                        AFTER {op} ON collected_items
                        BEGIN
                            DELETE FROM {FTS_TABLE} WHERE item_id = NEW.id;
                            INSERT INTO {FTS_TABLE}(item_id, title, content, summary)
                            VALUES (NEW.id, NEW.title, NEW.content, NEW.summary);
                        END
                    """))
                conn.commit()
            except Exception as exc:
                logger.warning("FTS trigger %s skipped: %s", trigger_name, exc)

    # Seed existing data
    try:
        with Session(engine) as db:
            count = db.query(CollectedItem).count()
            if count > 0:
                with engine.connect() as conn:
                    conn.execute(text(f"""
                        INSERT OR IGNORE INTO {FTS_TABLE}(item_id, title, content, summary)
                        SELECT id, title, content, summary FROM collected_items
                    """))
                    conn.commit()
                    logger.info("FTS seeded with %d items", count)
    except Exception as exc:
        logger.warning("FTS seeding skipped: %s", exc)

    logger.info("FTS5 full-text search initialized")


def search_items(
    db: Session,
    query: str,
    topic_id: Optional[str] = None,
    source_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[str], int]:
    """
    Search collected items using FTS5 with optional syntax:
      title:xxx   — search only in title
      content:xxx — search only in content

    Returns (matching_item_ids, total_count).
    """
    # Parse query for field-specific filters
    title_query = ""
    content_query = ""
    general_query = ""

    remaining = query
    # Extract title: queries
    title_matches = re.findall(r'title:([^\s]+(?:\s[^\s:]+)*)', remaining)
    if title_matches:
        # Rebuild without title: prefix
        title_query = " ".join(t.strip() for t in title_matches)
        remaining = re.sub(r'title:[^\s]+(?:\s[^\s:]+)*', '', remaining).strip()

    # Extract content: queries
    content_matches = re.findall(r'content:([^\s]+(?:\s[^\s:]+)*)', remaining)
    if content_matches:
        content_query = " ".join(c.strip() for c in content_matches)
        remaining = re.sub(r'content:[^\s]+(?:\s[^\s:]+)*', '', remaining).strip()

    general_query = remaining.strip()

    # Build FTS query
    fts_parts = []
    if title_query:
        # FTS5 column filter: {column}: query
        fts_parts.append(f'title: "{title_query}"')
    if content_query:
        fts_parts.append(f'content: "{content_query}"')
    if general_query:
        fts_parts.append(f'"{general_query}"')

    if not fts_parts:
        # Fallback to LIKE search
        q = db.query(CollectedItem).filter(
            (CollectedItem.title.ilike(f"%{query}%")) |
            (CollectedItem.content.ilike(f"%{query}%"))
        )
        if topic_id:
            from app.services.topic_item_query import filter_items_by_topic
            q = filter_items_by_topic(q, topic_id)
        if source_id:
            q = q.filter(CollectedItem.source_id == source_id)

        total = q.count()
        items = q.order_by(CollectedItem.collected_at.desc()).offset(offset).limit(limit).all()
        return [it.id for it in items], total

    fts_expression = " AND ".join(fts_parts)

    try:
        # Use raw SQL for FTS5 query
        with db.bind.connect() as conn:
            # Get matching IDs
            result = conn.execute(
                text(f"""
                    SELECT item_id FROM {FTS_TABLE}
                    WHERE {FTS_TABLE} MATCH :query
                    ORDER BY rank
                    LIMIT :limit OFFSET :offset
                """),
                {"query": fts_expression, "limit": limit, "offset": offset},
            )
            item_ids = [row[0] for row in result.fetchall()]

            # Get total count
            count_result = conn.execute(
                text(f"""
                    SELECT COUNT(*) FROM {FTS_TABLE}
                    WHERE {FTS_TABLE} MATCH :query
                """),
                {"query": fts_expression},
            )
            total = count_result.scalar() or 0
    except Exception as exc:
        logger.warning("FTS query failed (falling back to LIKE): %s", exc)
        # Fallback to LIKE
        q = db.query(CollectedItem).filter(
            (CollectedItem.title.ilike(f"%{query}%")) |
            (CollectedItem.content.ilike(f"%{query}%"))
        )
        if topic_id:
            from app.services.topic_item_query import filter_items_by_topic
            q = filter_items_by_topic(q, topic_id)
        if source_id:
            q = q.filter(CollectedItem.source_id == source_id)
        total = q.count()
        items = q.order_by(CollectedItem.collected_at.desc()).offset(offset).limit(limit).all()
        return [it.id for it in items], total

    if topic_id and item_ids:
        from app.services.topic_item_query import filter_items_by_topic
        allowed = {
            row[0] for row in filter_items_by_topic(
                db.query(CollectedItem.id), topic_id,
            ).filter(CollectedItem.id.in_(item_ids)).all()
        }
        item_ids = [item_id for item_id in item_ids if item_id in allowed]
        total = len(item_ids)
    return item_ids, total
