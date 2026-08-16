"""一次性数据迁移：清理 Window Topic、主题归类、删除 cc-switch、标签浓缩。

用法：backend/.venv/bin/python -m migrate_taxonomy
执行后删除本文件。
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.tag_taxonomy import CATEGORY_LABEL, normalize_category  # noqa: E402

DB_PATH = os.path.join(BASE_DIR, "data", "gather.db")
BACKUP_PATH = DB_PATH + f".bak-{time.strftime('%Y%m%d-%H%M%S')}"

TOPIC_CATEGORY = {
    "global-trade": "trade",
    "weekly-trade-current-affairs": "trade",
    "tech-regulations": "regulation",
    "item-56adc0": "security",
    "us-defense-procurement": "security",
    "weekly-enforcement-intelligence": "enforcement",
    "foreign-trade-forum-risk-monitoring": "enforcement",
    "critical-minerals-intelligence": "market",
}

# 这些命名空间整体删除（空标签或低价值/垃圾标签）
DROP_NAMESPACES = ("region", "commodity", "business", "risk", "portfolio")


def main() -> None:
    src = sqlite3.connect(DB_PATH)
    # 在线备份（WAL 安全）
    dst = sqlite3.connect(BACKUP_PATH)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    print(f"[backup] {BACKUP_PATH}")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    cur = con.cursor()

    # ── 0. 防御性检查：window topic 是否被引用 ──────────────────────────
    ref_tables = []
    for (tbl,) in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall():
        cols = {r[1] for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall()}
        if "topic_id" in cols and tbl != "topics":
            n = cur.execute(
                f"SELECT COUNT(*) FROM {tbl} WHERE topic_id LIKE 'window-topic-%'"
            ).fetchone()[0]
            if n:
                ref_tables.append((tbl, n))
    if ref_tables:
        print("[WARN] window topic 仍被引用：", ref_tables)
        print("[WARN] 中止，未做任何删除。")
        con.close()
        return

    # ── 1. 删除 Window Topic ────────────────────────────────────────────
    cur.execute("DELETE FROM topics WHERE id LIKE 'window-topic-%'")
    print(f"[topics] 删除 window topic: {cur.rowcount} 个")

    # ── 2. 主题归类到采集分类 ──────────────────────────────────────────
    for topic_id, cat in TOPIC_CATEGORY.items():
        cur.execute(
            "UPDATE topics SET category_id=? WHERE id=? AND category_id IS NULL",
            (cat, topic_id),
        )
        if cur.rowcount:
            print(f"[topics] {topic_id} -> category {cat}")
    con.commit()

    # ── 3. 删除 cc-switch 模型 ──────────────────────────────────────────
    cur.execute("DELETE FROM model_configs WHERE id='cc-switch-deepseek'")
    print(f"[models] 删除 cc-switch: {cur.rowcount} 个")
    con.commit()

    # ── 4. 归一化 collected_items.category ──────────────────────────────
    items = cur.execute("SELECT id, category FROM collected_items").fetchall()
    for it in items:
        norm = normalize_category(it["category"])
        new_val = norm or None
        if new_val != it["category"]:
            cur.execute(
                "UPDATE collected_items SET category=? WHERE id=?",
                (new_val, it["id"]),
            )
    con.commit()
    print("[items] category 归一化完成")

    # ── 5. 标签合并/删除 ────────────────────────────────────────────────
    tags = cur.execute("SELECT id, namespace, value FROM tags").fetchall()
    merged = 0
    deleted = 0
    for t in tags:
        tid, ns, val = t["id"], t["namespace"], t["value"]
        if ns == "category":
            norm = normalize_category(val)
            target = f"category:{norm}"
            if norm and norm == val and target == tid:
                continue  # 已是受控标签，保留
            if norm:
                # 合并到受控标签
                cur.execute(
                    "UPDATE OR IGNORE item_tags SET tag_id=? WHERE tag_id=?",
                    (target, tid),
                )
                merged += 1
            # 删除旧标签（空或已合并）
            cur.execute("DELETE FROM item_tags WHERE tag_id=?", (tid,))
            cur.execute("DELETE FROM tags WHERE id=?", (tid,))
            deleted += 1
        elif ns == "general":
            norm = normalize_category(val)
            if norm:
                cur.execute(
                    "UPDATE OR IGNORE item_tags SET tag_id=? WHERE tag_id=?",
                    (f"category:{norm}", tid),
                )
                merged += 1
            cur.execute("DELETE FROM item_tags WHERE tag_id=?", (tid,))
            cur.execute("DELETE FROM tags WHERE id=?", (tid,))
            deleted += 1
        elif ns in DROP_NAMESPACES:
            cur.execute("DELETE FROM item_tags WHERE tag_id=?", (tid,))
            cur.execute("DELETE FROM tags WHERE id=?", (tid,))
            deleted += 1
    con.commit()
    print(f"[tags] 合并 {merged} 个，删除 {deleted} 个冗余/垃圾标签")

    # 去重：合并后同一 item 可能对同一 tag 出现多行
    cur.execute(
        "DELETE FROM item_tags WHERE rowid NOT IN "
        "(SELECT MIN(rowid) FROM item_tags GROUP BY item_id, tag_id)"
    )
    print(f"[tags] 去重 item_tags 关联: {cur.rowcount} 行")

    # ── 6. 重建受控 category 标签 + 刷新 item_count ─────────────────────
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    for slug, label in CATEGORY_LABEL.items():
        tid = f"category:{slug}"
        cur.execute(
            "INSERT OR IGNORE INTO tags(id, namespace, value, label, item_count, created_at) "
            "VALUES(?, 'category', ?, ?, 0, ?)",
            (tid, slug, label, now),
        )
        cur.execute(
            "UPDATE tags SET label=?, namespace='category', value=? WHERE id=?",
            (label, slug, tid),
        )
    con.commit()

    # 刷新所有保留标签的 item_count
    counts = cur.execute(
        "SELECT tag_id, COUNT(*) c FROM item_tags GROUP BY tag_id"
    ).fetchall()
    for row in counts:
        cur.execute(
            "UPDATE tags SET item_count=? WHERE id=?", (row["c"], row["tag_id"])
        )
    con.commit()
    print("[tags] 受控标签重建 + item_count 刷新完成")

    # ── 7. 校验 ──────────────────────────────────────────────────────────
    total_tags = cur.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    total_topics = cur.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
    print(f"\n[result] 标签总数 {total_tags}，主题总数 {total_topics}")
    print("=== 最终标签体系 ===")
    for r in cur.execute(
        "SELECT namespace, value, label, item_count FROM tags ORDER BY namespace, item_count DESC"
    ).fetchall():
        print(f"  {r['namespace']:16} | ic={r['item_count']:4} | {r['value']:24} | {r['label']}")

    con.close()
    print("\n迁移完成。可删除 backend/migrate_taxonomy.py")


if __name__ == "__main__":
    main()
