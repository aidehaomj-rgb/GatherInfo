"""Import verified cases needed by the 2026-08-13 enforcement portfolio."""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, CollectionRun, SourceConfig, Tag  # noqa: E402


TOPIC_ID = "weekly-enforcement-intelligence"
SOURCE_ID = "ai-smart-web-research"
BATCH_ID = "codex-enforcement-portfolio-20260813"

CASES = [
    {
        "key": "malaysia-johor-chinese-scam-arrests-20260729",
        "url": "https://www.rmp.gov.my/news-detail/2026/07/29/keratan-akhbar-pilihan-dua-sindiket-scam-tumpas",
        "published_at": "2026-07-29T12:00:00+08:00",
        "title": "Malaysian Police Dismantle Two Online Scam Syndicates and Arrest 309 Chinese Nationals",
        "title_zh": "马来西亚警方捣毁柔佛两处诈骗窝点，拘捕309名中国公民",
        "summary_zh": "马来西亚皇家警察通报，柔佛警方在森林城市捣毁两个网络诈骗集团，共拘捕335人，其中309人为中国公民。",
        "content": (
            "Royal Malaysia Police said two online scam call-centre syndicates operating in "
            "Forest City, Iskandar Puteri, were dismantled after an operation on 15 July 2026. "
            "Police arrested 335 suspects, including 309 Chinese nationals, 19 Indonesians, "
            "four Myanmar nationals and three Malaysians."
        ),
        "content_zh": (
            "马来西亚皇家警察2026年7月29日通报，柔佛警方根据侦查结果，于7月15日在依斯干达公主城森林城市开展行动，"
            "捣毁两个以呼叫中心方式实施网络诈骗的集团。警方共拘捕335名嫌疑人，其中包括309名中国公民、19名印度尼西亚公民、"
            "4名缅甸公民和3名马来西亚公民。案件具有明确的境外执法行为、拘捕人数和中国公民关联。"
        ),
        "authority": "Royal Malaysia Police, Johor Police",
        "jurisdiction": "Malaysia",
        "case_type": "online fraud enforcement",
        "subject": "Two Forest City scam syndicates and 309 Chinese nationals",
        "action": "Raided two call centres and arrested 335 suspects",
        "evidence": "The suspects included 309 Chinese nationals among 335 people arrested.",
        "nexus": "Royal Malaysia Police explicitly identified 309 arrested suspects as Chinese nationals.",
    },
    {
        "key": "malaysia-melaka-chinese-scam-arrests-20260716",
        "url": "https://www.rmp.gov.my/news-detail/2026/07/16/keratan-akhbar-pilihan-banglo-scammer-diserbu-21-warga-china-ditahan",
        "published_at": "2026-07-16T12:00:00+08:00",
        "title": "Malaysian Police Raid Melaka Scam Bungalow and Arrest 21 Chinese Nationals",
        "title_zh": "马来西亚警方突击马六甲诈骗窝点，拘捕21名中国公民",
        "summary_zh": "马来西亚皇家警察突击马六甲爱极乐一处网络投资诈骗窝点，拘捕21名涉嫌参与诈骗集团的中国籍男子。",
        "content": (
            "Royal Malaysia Police reported that officers raided a two-storey bungalow in "
            "Ayer Keroh, Melaka, used by a fraudulent investment syndicate. Police arrested "
            "21 male Chinese nationals aged between 23 and 54 who were suspected of involvement."
        ),
        "content_zh": (
            "马来西亚皇家警察2026年7月16日发布通报，马六甲警方突击爱极乐一栋被用作虚假投资诈骗活动窝点的两层别墅。"
            "执法人员拘捕21名年龄在23岁至54岁之间的中国籍男子，警方认为这些人员涉嫌参与有关诈骗集团。"
            "该案具有明确的境外执法行动、拘捕结果及中国公民关联。"
        ),
        "authority": "Royal Malaysia Police, Melaka Police",
        "jurisdiction": "Malaysia",
        "case_type": "online investment fraud enforcement",
        "subject": "Fraudulent investment syndicate and 21 Chinese nationals",
        "action": "Raided a scam premises and arrested 21 suspects",
        "evidence": "Police arrested 21 male Chinese nationals aged between 23 and 54.",
        "nexus": "Royal Malaysia Police explicitly identified all 21 arrested suspects as Chinese nationals.",
    },
]


def get_tag(db, tag_id: str) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag:
        return tag
    namespace, value = tag_id.split(":", 1)
    tag = Tag(id=tag_id, namespace=namespace, value=value, label=value)
    db.add(tag)
    db.flush()
    return tag


def main() -> int:
    db = SessionLocal()
    try:
        source = db.get(SourceConfig, SOURCE_ID)
        if not source:
            raise RuntimeError(f"Source not found: {SOURCE_ID}")
        now = datetime.now(timezone.utc)
        run = db.query(CollectionRun).filter(CollectionRun.batch_id == BATCH_ID).first()
        if not run:
            run = CollectionRun(
                id=f"run-{uuid4().hex[:12]}", source_id=SOURCE_ID,
                topic_id=TOPIC_ID, status="running", batch_id=BATCH_ID,
                keywords_used=["Codex Web Search", "Chinese nationals", "overseas enforcement"],
                started_at=now, window_start=datetime(2026, 7, 14, tzinfo=timezone.utc),
                window_end=now,
                metadata_json={"provider": "codex_web_search", "review_mode": "verified_official_source"},
            )
            db.add(run)
            db.flush()

        inserted = 0
        item_ids = []
        tags = ["weekly:执法查获", "weekly:贸易合规", "china_relevance:强涉华关联"]
        for case in CASES:
            item = db.query(CollectedItem).filter(CollectedItem.url == case["url"]).first()
            if not item:
                metadata = {
                    "provider": "codex_web_search", "import_batch": BATCH_ID,
                    "source_name": "Royal Malaysia Police", "original_language": "ms",
                    "date_verified": True, "date_source": case["url"], "tags": tags,
                    "translation_zh": {"title_zh": case["title_zh"], "summary_zh": case["summary_zh"], "content_zh": case["content_zh"], "status": "translated"},
                    "enforcement_review": {
                        "decision": "approve", "confidence": 99,
                        "basis": "已核验官方来源、发布日期、具体执法行动及中国公民关联证据。",
                        "inclusion_basis": "strong_china_nexus", "china_relevance_level": "strong",
                        "china_relevance_label": "强涉华关联", "evidence_quote": case["evidence"],
                        "mainland_nexus_evidence": case["nexus"], "enforcement_action": case["action"],
                        "jurisdiction": case["jurisdiction"], "authority": case["authority"],
                        "case_type": case["case_type"], "subject": case["subject"],
                        "source_name": "Royal Malaysia Police", "source_domain": urlparse(case["url"]).netloc,
                        "reviewer": "codex_web_search",
                    },
                }
                published = datetime.fromisoformat(case["published_at"]).astimezone(timezone.utc)
                item = CollectedItem(
                    id=f'codex-{case["key"]}', source_id=SOURCE_ID, run_id=run.id,
                    topic_id=TOPIC_ID, title=case["title"], content=case["content"],
                    content_hash=hashlib.sha256(f'{case["url"]}\n{case["content"]}'.encode()).hexdigest(),
                    summary=case["summary_zh"], url=case["url"], language="ms",
                    category="跨境网络诈骗执法", entities={"countries": ["Malaysia", "China"], "authorities": [case["authority"]], "subjects": [case["subject"]]},
                    status="enriched", quality_score=0.99, relevance_score=0.96,
                    published_at=published, collected_at=now, updated_at=now,
                    raw_metadata=metadata, authorization_level="public",
                )
                item.tags = [get_tag(db, tag_id) for tag_id in tags]
                db.add(item)
                inserted += 1
            item_ids.append(item.id)

        run.status = "completed"
        run.items_found = len(CASES)
        run.items_new = inserted
        run.items_failed = 0
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = int((run.completed_at - (run.started_at or now)).total_seconds() * 1000)
        run.metadata_json = {**(run.metadata_json or {}), "item_ids": item_ids, "inserted": inserted}
        source.items_collected = int(source.items_collected or 0) + inserted
        source.last_sync_at = run.completed_at
        db.commit()
        print(f"run_id={run.id} inserted={inserted} total={len(CASES)}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
