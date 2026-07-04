"""
Seed demo collected-item data into the TradeRadar database.

This script populates the collection tables with synthetic but realistic data so
the frontend has something meaningful to display.  It uses the existing SQLAlchemy
models so all relationships, tags, and audit fields are correctly wired up.

Usage:
    cd /Users/m4max/VS-CODE-PROJECT/TradeRadar
    PYTHONPATH=backend backend/.venv/bin/python -m app.seed_demo_data
"""
import hashlib
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.normpath(os.path.join(_HERE, "..", ".."))
if _PROJECT not in sys.path:
    sys.path.insert(0, _PROJECT)
os.chdir(_PROJECT)

from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import (
    CollectedItem, CollectionRun, ItemStatus, JobStatus, Tag, SourceConfig, Topic,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def item_id(source_id: str, title: str, url: str = "") -> str:
    raw = f"{source_id}:{title}:{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# ── Demo items generation ───────────────────────────────────────────────

def demo_items(topic_id: str, source_id: str) -> list[dict]:
    now = utc_now()
    items = []

    if topic_id == "global-trade":
        if source_id == "tavily":
            for i in range(12):
                days_ago = i // 2
                published = now - timedelta(days=days_ago, hours=i * 4)
                items.append(dict(
                    title=f"全球贸易政策更新：主要经济体关税调整动向 (第{i+1}期)",
                    content=f"近日，多个主要经济体发布了新的贸易政策动向。美国贸易代表办公室公布了对华关税复审结果，欧盟委员会发布了碳边境调节机制(CBAM)的最新实施指南。分析人士指出，这些措施将对全球供应链产生深远影响。",
                    summary=f"美欧关税与CBAM政策更新 — 第{i+1}期简报",
                    language="zh", category="policy",
                    published_at=published,
                    quality_score=0.85 + (i % 3) * 0.05,
                    relevance_score=0.90 - (i % 5) * 0.02,
                    url=f"https://example.com/trade/update-{i+1}",
                ))
            for i in range(8):
                days_ago = i // 2
                published = now - timedelta(days=days_ago, hours=i * 6)
                items.append(dict(
                    title=f"RCEP实施进展：成员国关税减让与贸易便利化措施通报 (第{i+1}轮)",
                    content=f"RCEP成员国间关税减让持续推进。中国、日本、韩国、澳大利亚、新西兰和东盟成员国就原产地规则、海关程序与贸易便利化措施进行了新一轮磋商。各方同意加快电子商务和数字贸易合作。",
                    summary=f"RCEP关税减让与贸易便利化最新进展",
                    language="zh", category="trade",
                    published_at=published,
                    quality_score=0.82 + (i % 4) * 0.04,
                    relevance_score=0.85 - (i % 3) * 0.03,
                    url=f"https://example.com/trade/rcep-round-{i+1}",
                ))
            for i in range(6):
                days_ago = i // 2
                published = now - timedelta(days=days_ago, hours=i * 8)
                items.append(dict(
                    title=f"Trade Policy Review: US Tariff Adjustment on Chinese Imports Wave {i+1}",
                    content=f"The U.S. Trade Representative has published the latest review of Section 301 tariffs. New exclusions have been granted for certain industrial components, while tariffs on strategic sectors including semiconductors and EV batteries have been maintained.",
                    summary=f"US tariff review cycle {i+1} — exclusions and strategic sector analysis",
                    language="en", category="policy",
                    published_at=published,
                    quality_score=0.88,
                    relevance_score=0.83,
                    url=f"https://example.com/trade/us-tariff-review-{i+1}",
                ))

        elif source_id == "cn-mofcom":
            for i in range(10):
                days_ago = i // 2
                published = now - timedelta(days=days_ago)
                items.append(dict(
                    title=f"商务部公告：关于{'反倾销' if i % 3 == 0 else '出口管制' if i % 3 == 1 else '贸易救济调查'}调查裁定 (2026年第{100+i}号)",
                    content=f"根据《中华人民共和国反倾销条例》的规定，商务部对原产于{'美国' if i % 2 == 0 else '欧盟' if i % 2 == 1 else '日本和韩国'}的进口{'未漂白纸袋纸' if i % 4 == 0 else '取向电工钢' if i % 4 == 1 else '聚苯醚' if i % 4 == 2 else '间甲酚'}产品所适用的反倾销措施进行了{'期终复审' if i % 3 == 0 else '新出口商复审' if i % 3 == 1 else '期中复审'}。",
                    summary=f"商务部关于{'反倾销' if i % 3 == 0 else '出口管制' if i % 3 == 1 else '贸易救济调查'}的公告",
                    language="zh", category="trade",
                    published_at=published,
                    quality_score=0.92,
                    relevance_score=0.88,
                    url=f"https://example.com/mofcom/notice-{100+i}",
                ))

        elif source_id == "cn-customs":
            for i in range(8):
                days_ago = i
                published = now - timedelta(days=days_ago)
                is_optima = i % 2 == 0
                items.append(dict(
                    title=f"海关总署公告：关于{'优化进出口商品检验监管模式' if is_optima else '调整部分商品进出口关税税率'}的通知 (2026年第{200+i}号)",
                    content=f"为进一步优化口岸营商环境，海关总署决定对涉及{'锂电池、新能源汽车' if i % 3 == 0 else '农产品、食品' if i % 3 == 1 else '化工产品、矿产品'}等{'38' if i % 3 == 0 else '42' if i % 3 == 1 else '55'}个HS编码的商品实施{'检验监管模式优化' if is_optima else '关税税率调整'}。本公告自发布之日起30日后施行。",
                    summary=f"海关总署：{'优化进出口商品检验监管模式' if is_optima else '调整部分商品进出口关税税率'}",
                    language="zh", category="regulation",
                    published_at=published,
                    quality_score=0.95,
                    relevance_score=0.90,
                    url=f"https://example.com/customs/notice-{200+i}",
                ))

    elif topic_id == "tech-regulations":
        if source_id == "wto-eping":
            cats = ["tbt_sps", "regulation", "tbt_sps", "biosecurity", "tbt_sps"]
            for i in range(10):
                days_ago = i
                published = now - timedelta(days=days_ago)
                cat = cats[i % len(cats)]
                products = ["lithium-ion batteries", "photovoltaic modules", "pesticide residues in food", "industrial chemicals", "electronic displays"]
                reqs = ["safety and performance requirements", "energy efficiency labeling", "maximum residue limits", "REACH-like requirements", "energy labeling requirements"]
                items.append(dict(
                    title=f"WTO TBT/SPS Notification: {['Battery', 'Solar Panel', 'Food Safety', 'Chemical', 'Electronics'][i%5]} Standards Update G/TBT/N/{chr(65+i)}/{100+i+1}",
                    content=f"WTO Member has submitted a notification concerning proposed technical regulations on {products[i%5]}. The regulation covers {reqs[i%5]}. Comments are invited within 60 days.",
                    summary=f"WTO {cat.upper()} notification: {['battery', 'solar', 'food safety', 'chemical', 'electronics'][i%5]} standards",
                    language="en",
                    category=cat,
                    published_at=published,
                    quality_score=0.90 + (i % 3) * 0.03,
                    relevance_score=0.85,
                    url=f"https://eping.wto.org/notification/G_TBT_N_{chr(65+i)}_{100+i+1}",
                ))

        elif source_id == "eu-eurlex":
            cats = ["regulation", "regulation", "trade", "regulation"]
            for i in range(8):
                days_ago = i
                published = now - timedelta(days=days_ago)
                cat = cats[i % len(cats)]
                is_battery = i % 3 == 0
                is_passport = i % 3 == 1
                items.append(dict(
                    title=f"Commission Delegated Regulation (EU) 2026/{800+i}: {'Battery Carbon Footprint' if is_battery else 'Digital Product Passport' if is_passport else 'Ecodesign for Sustainable Products'}",
                    content=f"The European Commission has adopted a delegated regulation supplementing Regulation (EU) 2023/1542 concerning {'battery carbon footprint declaration methodology' if is_battery else 'digital product passport requirements for batteries' if is_passport else 'ecodesign requirements for sustainable products'}. The regulation enters into force on the twentieth day following its publication in the Official Journal.",
                    summary=f"EU Delegated Regulation on {'battery carbon footprint' if is_battery else 'digital product passport' if is_passport else 'ecodesign'}",
                    language="en", category=cat,
                    published_at=published,
                    quality_score=0.93,
                    relevance_score=0.87,
                    url=f"https://eur-lex.europa.eu/eli/reg_del/2026/{800+i}",
                ))

        elif source_id == "tavily":
            for i in range(10):
                days_ago = i
                published = now - timedelta(days=days_ago)
                topics = ["锂电池", "光伏", "新能源汽车"]
                t = topics[i % 3]
                items.append(dict(
                    title=f"技术性贸易措施动态：{t}出口合规要点第{i+1}期",
                    content=f"欧盟电池法规(EU)2023/1542实施细则持续更新。针对{t}产品，出口企业需要重点关注碳足迹计算、供应链尽职调查文件、合格评定标识等合规要求。",
                    summary=f"{t}出口合规要点分析",
                    language="zh",
                    category="regulation" if i % 2 == 0 else "technology",
                    published_at=published,
                    quality_score=0.80 + (i % 5) * 0.04,
                    relevance_score=0.85,
                    url=f"https://example.com/tech-reg/compliance-{i+1}",
                ))

    return items


# ── Auto-tag inference ──────────────────────────────────────────────────

def inferred_tags(item: dict) -> list[str]:
    text = (item.get("title", "") + " " + (item.get("content", "") or "")).lower()
    tags = []
    rules = [
        ("event:tariff",          ["关税", "tariff", "tariffs"]),
        ("event:anti_dumping",    ["反倾销", "anti-dumping", "antidumping"]),
        ("event:export_control",  ["出口管制", "export control"]),
        ("product:battery",       ["电池", "battery", "batteries", "lithium"]),
        ("product:solar",         ["光伏", "solar"]),
        ("product:semiconductor", ["芯片", "半导体", "semiconductor"]),
        ("event:carbon_footprint",["碳足迹", "carbon", "cbam"]),
        ("sector:new_energy",     ["新能源", "新能源汽车", "ev"]),
        ("agreement:rcep",        ["rcep"]),
    ]
    for tag_id, keywords in rules:
        if any(kw in text for kw in keywords):
            tags.append(tag_id)
    return tags


# ── Ensure tag exists ───────────────────────────────────────────────────

def ensure_tag(db: Session, tag_id: str, namespace: str, value: str, label: str | None = None) -> Tag:
    existing = db.query(Tag).filter(Tag.id == tag_id).first()
    if existing:
        return existing
    t = Tag(id=tag_id, namespace=namespace, value=value, label=label or value)
    db.add(t)
    db.flush()
    return t


# ── Main ────────────────────────────────────────────────────────────────

def seed():
    init_db()
    db: Session = SessionLocal()

    try:
        existing = db.query(CollectedItem).count()
        if existing > 0:
            print(f"Database already has {existing} items. Skipping demo data seed.")
            return

        sources = {s.id: s for s in db.query(SourceConfig).all()}
        topics = {t.id: t for t in db.query(Topic).all()}

        print(f"Found {len(sources)} sources, {len(topics)} topics")

        # Pre-create all known tags
        tag_defs = {
            "event:tariff":          ("event", "tariff", "关税事件"),
            "event:anti_dumping":    ("event", "anti_dumping", "反倾销"),
            "event:export_control":  ("event", "export_control", "出口管制"),
            "event:carbon_footprint":("event", "carbon_footprint", "碳足迹"),
            "product:battery":       ("product", "battery", "锂电池"),
            "product:solar":         ("product", "solar", "光伏产品"),
            "product:semiconductor": ("product", "semiconductor", "半导体"),
            "sector:new_energy":     ("sector", "new_energy", "新能源"),
            "agreement:rcep":        ("agreement", "rcep", "RCEP"),
            "country:cn":            ("country", "CN", "中国"),
            "country:us":            ("country", "US", "美国"),
            "country:eu":            ("country", "EU", "欧盟"),
            "country:asean":         ("country", "ASEAN", "东盟"),
            "language:zh":           ("language", "zh", "中文"),
            "language:en":           ("language", "en", "英文"),
        }
        tags = {}
        for tag_id, (ns, val, label) in tag_defs.items():
            tags[tag_id] = ensure_tag(db, tag_id, ns, val, label)

        # Generate and insert items
        now = utc_now()
        total_items = 0

        for topic_id in topics:
            for source_id in sources:
                items_data = demo_items(topic_id, source_id)
                if not items_data:
                    continue

                run = CollectionRun(
                    id=f"demo-run-{uuid4().hex[:8]}",
                    source_id=source_id,
                    topic_id=topic_id,
                    job_id=f"demo-job-{uuid4().hex[:8]}",
                    status=JobStatus.COMPLETED,
                    keywords_used=topics[topic_id].keywords,
                    items_found=len(items_data),
                    items_new=len(items_data),
                    started_at=now - timedelta(hours=2),
                    completed_at=now - timedelta(hours=1),
                    duration_ms=60000,
                )
                db.add(run)

                for item_data in items_data:
                    raw_id = item_id(source_id, item_data["title"], item_data.get("url", ""))
                    published = item_data["published_at"]
                    collected = now - timedelta(
                        days=(now - published).days if published else 0,
                        hours=2,
                    )

                    ci = CollectedItem(
                        id=raw_id,
                        source_id=source_id,
                        run_id=run.id,
                        topic_id=topic_id,
                        title=item_data["title"],
                        content=item_data.get("content"),
                        content_hash=_hash(item_data.get("content", "") or item_data["title"]),
                        summary=item_data.get("summary"),
                        url=item_data.get("url"),
                        language=item_data.get("language", "zh"),
                        category=item_data.get("category"),
                        quality_score=item_data.get("quality_score", 0.8),
                        relevance_score=item_data.get("relevance_score", 0.8),
                        published_at=published,
                        collected_at=collected,
                        status=ItemStatus.RAW,
                        raw_metadata={"engine": "demo_seed"},
                    )

                    # Auto-tags from content
                    for tag_id in inferred_tags(item_data):
                        t = ensure_tag(db, tag_id, tag_id.split(":")[0], tag_id.split(":")[1] if ":" in tag_id else tag_id)
                        ci.tags.append(t)
                        t.item_count = (t.item_count or 0) + 1
                        t.last_seen_at = now

                    # Category tag
                    cat = item_data.get("category")
                    if cat:
                        ct = ensure_tag(db, f"category:{cat}", "category", cat)
                        ci.tags.append(ct)
                        ct.item_count = (ct.item_count or 0) + 1
                        ct.last_seen_at = now

                    # Language tag
                    lang = item_data.get("language", "zh")
                    lt = ensure_tag(db, f"language:{lang}", "language", lang)
                    ci.tags.append(lt)
                    lt.item_count = (lt.item_count or 0) + 1
                    lt.last_seen_at = now

                    db.add(ci)
                    total_items += 1

        db.commit()
        print(f"Demo data seeded successfully!")
        print(f"  Sources: {len(sources)}")
        print(f"  Topics:  {len(topics)}")
        print(f"  Items:   {total_items}")

    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
