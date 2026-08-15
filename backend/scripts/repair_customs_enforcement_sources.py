"""Repair display names for customs enforcement sources.

Some sources were inserted from a terminal session with a broken code page, so
their Chinese names were persisted as mojibake or question marks.  Keep this as
a repeatable maintenance script instead of a one-off SQL update.
"""

from __future__ import annotations

from app.database import SessionLocal
from app.models import SourceConfig


SOURCE_FIXES: dict[str, dict[str, object]] = {
    "wco": {
        "name": "世界海关组织新闻",
        "description": "WCO 新闻动态、海关合作、执法行动和风险防控信息。",
    },
    "cn-customs": {
        "name": "海关总署公告",
        "description": "海关总署公告、政策文件和监管动态。",
    },
    "singapore-customs-rss": {
        "name": "新加坡海关新闻",
        "description": "Singapore Customs 新闻与媒体发布。",
    },
    "korea-customs-rss": {
        "name": "韩国关税厅新闻",
        "description": "韩国关税厅公告、新闻和执法动态。",
    },
    "weekly-fr-customs": {
        "name": "法国海关新闻",
        "description": "法国海关新闻、查发案例和监管动态。",
    },
    "weekly-bg-customs": {
        "name": "保加利亚海关新闻",
        "description": "保加利亚海关署新闻动态。",
    },
    "weekly-de-customs": {
        "name": "德国海关新闻",
        "description": "德国海关新闻、查发案例和监管动态。",
    },
    "weekly-pa-customs": {
        "name": "巴拿马海关新闻",
        "description": "巴拿马海关新闻动态。",
    },
    "weekly-id-customs": {
        "name": "印度尼西亚海关新闻",
        "description": "印度尼西亚海关与消费税总局新闻动态。",
    },
    "weekly-ca-cbsa": {
        "name": "加拿大边境服务署新闻",
        "description": "CBSA 新闻发布、边境执法和查发案例。",
    },
    "weekly-tw-customs": {
        "name": "台湾关务署新闻",
        "description": "台湾关务署新闻、查发案例和监管动态。",
    },
    "weekly-fi-customs": {
        "name": "芬兰海关新闻",
        "description": "芬兰海关新闻、查发案例和监管动态。",
    },
    "weekly-ee-tax-customs": {
        "name": "爱沙尼亚税务与海关局新闻",
        "description": "爱沙尼亚税务与海关局新闻动态。",
    },
    "weekly-au-abf": {
        "name": "澳大利亚边境执法新闻",
        "description": "澳大利亚边境执法局新闻发布和执法案例。",
    },
    "weekly-nz-customs": {
        "name": "新西兰海关新闻",
        "description": "新西兰海关媒体发布和执法动态。",
    },
    "weekly-jp-customs": {
        "name": "日本海关新闻",
        "description": "日本海关英文新闻和监管动态。",
    },
    "weekly-uk-border-force": {
        "name": "英国边境执法新闻",
        "description": "英国边境执法和内政部相关新闻动态。",
    },
    "weekly-za-sars": {
        "name": "南非税务署海关新闻",
        "description": "南非税务署海关与边境执法新闻动态。",
    },
    "weekly-ke-kra": {
        "name": "肯尼亚税务局新闻",
        "description": "肯尼亚税务局新闻发布、海关和边境执法动态。",
    },
    "weekly-ng-customs": {
        "name": "尼日利亚海关新闻",
        "description": "尼日利亚海关新闻和执法动态。",
    },
    "weekly-bo-customs": {
        "name": "玻利维亚海关新闻",
        "description": "玻利维亚海关新闻和执法动态。",
    },
    "weekly-pe-sunat": {
        "name": "秘鲁 SUNAT 海关新闻",
        "description": "秘鲁 SUNAT 新闻发布、海关和税务执法动态。",
    },
    "weekly-co-dian": {
        "name": "哥伦比亚 DIAN 新闻",
        "description": "哥伦比亚国家税务和海关局新闻发布。",
    },
    "weekly-cl-customs": {
        "name": "智利海关新闻",
        "description": "智利海关新闻和执法动态。",
    },
    "weekly-ar-customs": {
        "name": "阿根廷海关新闻",
        "description": "阿根廷海关新闻和执法动态。",
    },
    "tw-newtalk": {
        "name": "Newtalk 台湾新闻（执法线索）",
        "description": "台湾新闻媒体执法线索，作为候选信息源并由审核规则筛选。",
    },
}


STALE_ERROR_FIXES: dict[str, str | None] = {
    "cn-customs": "海关总署部分页面可能返回 504/412 或需要浏览器校验，建议通过搜索 API 使用 site:customs.gov.cn 补充采集。",
    "korea-customs-rss": "韩国关税厅英文页可能间歇超时，采集失败时保留为可重试来源。",
}


def main() -> None:
    with SessionLocal() as db:
        updated = 0
        for source_id, fields in SOURCE_FIXES.items():
            source = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
            if not source:
                continue
            for field, value in fields.items():
                if getattr(source, field) != value:
                    setattr(source, field, value)
                    updated += 1
            if source_id in STALE_ERROR_FIXES and source.last_error != STALE_ERROR_FIXES[source_id]:
                source.last_error = STALE_ERROR_FIXES[source_id]
                updated += 1
            elif source.last_error and "?" in source.last_error:
                source.last_error = None
                updated += 1
        db.commit()
        print(f"updated_fields={updated}")


if __name__ == "__main__":
    main()
