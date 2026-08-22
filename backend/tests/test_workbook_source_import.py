import json
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import SourceChannel, SourceConfig, Topic
from app.workbook_source_import import import_workbook_directory, parse_workbook_directory


def _directory_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "亚洲"
    sheet.append(["亚洲"])
    sheet.append(["分类：政府机构"])
    sheet.append([])
    sheet.append(["序号", "国家/地区", "机构名称", "网站", "中国大陆访问", "反爬虫机制"])
    sheet.append([1, "印度", "印度海关", "https://www.cbic.gov.in/", "可访问", "无"])
    sheet.append([2, "日本", "日本海关", "https://www.customs.go.jp/", "可访问", "有（Crawl-delay:10）"])
    workbook.save(path)


def _article_workbook(path: Path, rows: list[list[object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "中印贸易资讯汇总"
    sheet.append(["本周更新"])
    sheet.append(["时间范围"])
    sheet.append(["序号", "发布日期", "标题", "主要内容摘要", "来源网站名称", "来源链接", "类别"])
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def _manifest(path: Path) -> None:
    path.write_text(json.dumps({
        "topics": [{
            "id": "china-india-trade-intelligence",
            "name": "中印贸易资讯",
            "file_patterns": ["中印贸易资讯_*.xlsx"],
            "sheet_patterns": ["中印贸易资讯*"],
            "keywords": ["中印贸易", "关税", "海关"],
            "focus_countries": ["中国", "印度"],
            "focus_languages": ["zh", "en", "hi"],
            "source_country_filters": ["印度"],
            "collect_window_days": 180,
            "target_urls_mode": "explicit",
        }],
    }, ensure_ascii=False), encoding="utf-8")


def test_parser_deduplicates_article_targets_across_workbooks(tmp_path: Path) -> None:
    _directory_workbook(tmp_path / "政府与国际机构网站目录.xlsx")
    rows = [[
        1, "2026-08-13", "印度调整涉华关税", "只有摘要，不是正式正文",
        "印度海关", "https://www.cbic.gov.in/news/1?utm_source=sheet", "官方政策",
    ]]
    _article_workbook(tmp_path / "中印贸易资讯_1.xlsx", rows)
    _article_workbook(tmp_path / "中印贸易资讯_2.xlsx", rows)
    manifest = tmp_path / "topics.json"
    _manifest(manifest)

    dataset = parse_workbook_directory(tmp_path, manifest)

    assert len(dataset.sites) == 2
    assert len(dataset.targets) == 1
    assert dataset.targets[0].url == "https://www.cbic.gov.in/news/1?utm_source=sheet"
    assert dataset.targets[0].source_files == (
        "中印贸易资讯_1.xlsx", "中印贸易资讯_2.xlsx",
    )


def test_import_is_idempotent_reuses_sources_and_preserves_compliance(tmp_path: Path) -> None:
    _directory_workbook(tmp_path / "政府与国际机构网站目录.xlsx")
    _article_workbook(tmp_path / "中印贸易资讯_1.xlsx", [[
        1, "2026-08-13", "印度调整涉华关税", "只有摘要",
        "印度海关", "https://www.cbic.gov.in/news/1", "官方政策",
    ]])
    manifest = tmp_path / "topics.json"
    _manifest(manifest)
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(SourceConfig(
        id="existing-cbic", name="印度海关", channel=SourceChannel.WEB_SCRAPE,
        base_url="https://www.cbic.gov.in/news", homepage_url="https://cbic.gov.in/",
        is_active=True, is_configured=True, verification_status="verified_by_user",
        robots_status="allowed_by_user", terms_status="government_conditions",
        llm_ingest_allowed=True,
    ))
    db.add(SourceConfig(
        id="existing-japan-api", name="日本海关", channel=SourceChannel.JSON_API,
        api_endpoint="https://www.customs.go.jp/", is_active=True,
        is_configured=True, verification_status="imported_unverified",
    ))
    db.commit()

    first = import_workbook_directory(db, tmp_path, manifest)
    db.commit()
    second = import_workbook_directory(db, tmp_path, manifest)
    db.commit()

    topic = db.get(Topic, "china-india-trade-intelligence")
    existing = db.get(SourceConfig, "existing-cbic")
    imported = db.query(SourceConfig).filter(SourceConfig.name == "日本海关").one()
    assert first.sources_created == 0
    assert second.sources_created == 0
    assert db.query(SourceConfig).count() == 2
    assert existing.verification_status == "verified_by_user"
    assert existing.llm_ingest_allowed is True
    assert imported.id == "existing-japan-api"
    assert imported.verification_status == "imported_unverified"
    assert imported.terms_status == "unverified"
    assert topic.target_urls == ["https://www.cbic.gov.in/news/1"]
    assert topic.target_urls_mode == "explicit"
    assert topic.synonyms == [] or topic.synonyms is None
    assert topic.source_ids == ["existing-cbic"]
    assert second.targets_added == 0
    db.close()
    engine.dispose()
