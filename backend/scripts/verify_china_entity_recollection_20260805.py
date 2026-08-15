"""Read-only acceptance checks for the 2026-08-05 China-entity recollection."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[2] / "data" / "gather.db"
REPORT_ID = "report-forum-risk-cn-recollect-20260805"
TOPIC_ID = "foreign-trade-forum-risk-monitoring"
PROMPT_ID = "forum-social-customs-risk-search"
ITEM_IDS = [f"codex-china-entity-recollect-20260805-{index:02d}" for index in range(1, 5)]
PROMPT_MARKER = "[2026-08-05 \u65b0\u4e00\u8f6e\u4e2d\u56fd\u5b9e\u4f53\u91cd\u91c7\u96c6\u89c4\u5219]"


def main() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        report = connection.execute(
            "SELECT * FROM reports WHERE id = ?", (REPORT_ID,)
        ).fetchone()
        topic = connection.execute(
            "SELECT * FROM topics WHERE id = ?", (TOPIC_ID,)
        ).fetchone()
        prompt = connection.execute(
            "SELECT * FROM prompt_templates WHERE id = ?", (PROMPT_ID,)
        ).fetchone()
        placeholders = ",".join("?" for _ in ITEM_IDS)
        items = connection.execute(
            f"SELECT id, raw_metadata FROM collected_items WHERE id IN ({placeholders})",
            ITEM_IDS,
        ).fetchall()
        runs = connection.execute(
            "SELECT id, batch_id, status FROM collection_runs "
            "WHERE id LIKE 'codex-cn-recollect-20260805-%'"
        ).fetchall()

    assert report is not None and report["status"] == "completed"
    assert report["item_count"] == 4
    assert set(json.loads(report["item_ids"])) == set(ITEM_IDS)
    output_files = json.loads(report["output_files"])
    assert Path(output_files["docx"]).is_file()

    assert topic is not None and topic["total_items_collected"] == 24
    assert len(json.loads(topic["source_ids"])) == 36
    assert prompt is not None and PROMPT_MARKER in prompt["content"]

    gates = [json.loads(item["raw_metadata"]).get("china_entity_gate") for item in items]
    assert len(items) == 4 and gates == ["passed"] * 4
    assert len(runs) == 4
    assert all(
        run["status"] == "completed"
        and run["batch_id"] == "codex-china-entity-recollect-20260805"
        for run in runs
    )

    print(
        json.dumps(
            {
                "report_status": report["status"],
                "report_items": report["item_count"],
                "topic_items": topic["total_items_collected"],
                "topic_sources": len(json.loads(topic["source_ids"])),
                "prompt_marker": True,
                "china_entity_gate": "passed",
                "runs": len(runs),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
