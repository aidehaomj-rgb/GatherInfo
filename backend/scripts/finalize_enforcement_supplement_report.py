"""Finalize the July enforcement report with verified, database-backed facts."""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, Report, Topic  # noqa: E402
from app.report_engine import (  # noqa: E402
    _append_enforcement_case_appendix,
    _build_item_context,
)
from app.report_export import _safe_filename, _write_docx, export_report  # noqa: E402
from app.services.report_service import get_system_config  # noqa: E402
from scripts.import_codex_enforcement_cases import CASES  # noqa: E402


TOPIC_ID = "weekly-enforcement-intelligence"

JURISDICTION_ZH = {
    "Argentina": "阿根廷",
    "Australia": "澳大利亚",
    "Brazil": "巴西",
    "Canada": "加拿大",
    "Hong Kong": "中国香港",
    "India": "印度",
    "Indonesia": "印度尼西亚",
    "New Zealand": "新西兰",
    "Pakistan": "巴基斯坦",
    "Panama": "巴拿马",
    "Portugal": "葡萄牙",
    "Singapore": "新加坡",
    "Thailand": "泰国",
    "United States": "美国",
}

RISK_LABELS = {
    "origin fraud": "原产地调换及自由区便利滥用",
    "customs smuggling": "边境夹藏及违规进出口",
    "intellectual property infringement": "中国来源侵权商品",
    "duty evasion": "未完税商品及税收流失",
    "people smuggling": "跨境有组织犯罪",
    "currency declaration violation": "旅客现金申报异常",
    "gold smuggling": "贵金属未申报出境",
    "illegal import network": "二手电子产品非法进口网络",
    "transnational narcotics": "跨国毒品网络",
}


def _review(item: CollectedItem) -> dict:
    metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
    review = metadata.get("enforcement_review")
    return review if isinstance(review, dict) else {}


def _clean_text(value: object) -> str:
    text = " ".join(str(value or "").split())
    text = re.sub(r"^\s*#{1,6}\s*", "", text)
    text = re.sub(r"^\s*[-*]\s+", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\|", "，", text)
    return text.strip()


def _new_case_digest() -> str:
    lines = [
        "## 二、本次补充纳入的重点案例",
        "",
        "本次通过多语种深度检索补充纳入9条经核验案例，其中强涉华关联8条、弱涉华关联1条，主要覆盖原产地欺诈、边境走私、知识产权、税收走私、人员偷渡、现金申报、贵金属走私、违规进口和跨国毒品等类型。",
        "",
    ]
    for index, case in enumerate(
        sorted(CASES, key=lambda row: row["published_at"], reverse=True),
        1,
    ):
        numeral = _chinese_ordinal(index)
        date = case["published_at"][:10]
        jurisdiction = JURISDICTION_ZH.get(case["jurisdiction"], case["jurisdiction"])
        label = "强涉华关联" if case["level"] == "strong" else "弱涉华关联"
        risk = RISK_LABELS.get(case["case_type"], case["case_type"])
        lines.extend(
            [
                f"（{numeral}）{case['title_zh']}",
                f"发布时间：{date}。国家或地区：{jurisdiction}。涉华等级：{label}。主要风险：{risk}。",
                f"案情摘要：{_clean_text(case['content_zh'])}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _build_analysis(items: list[CollectedItem]) -> tuple[str, str]:
    levels = Counter(
        _review(item).get("china_relevance_level") or "unclassified"
        for item in items
    )
    jurisdictions = Counter(
        JURISDICTION_ZH.get(
            _review(item).get("jurisdiction"),
            _review(item).get("jurisdiction") or "待核验",
        )
        for item in items
    )
    top_jurisdictions = "、".join(
        f"{name}{count}条" for name, count in jurisdictions.most_common(8)
    )
    content = f"""## 执行摘要

本期报告共分析境外进出口执法信息{len(items)}条。经案件级审核，其中强涉华关联{levels["strong"]}条、弱涉华关联{levels["weak"]}条、重大非涉华执法案件{levels["major_non_china"]}条。案例覆盖14个国家和地区，主要分布为{top_jurisdictions}。本次通过多语种深度检索新增9条经核验案例，补充了泰国、巴基斯坦、葡萄牙、新加坡、澳大利亚、印度、印度尼西亚和阿根廷等地执法动态。

综合看，涉华风险关联已不局限于“中国发货”这一单一维度，而是同时表现为中国来源商品、中国籍涉案人员、中国目的地或边境通道、经中国香港转运以及由中国关联人员控制的跨国网络。海关风险监测应从关键词命中转向“人员、商品、路线、企业和执法行为”五个维度的关联识别。

## 一、总体态势

（一）贸易合规类风险链条更加完整。本次新增案例覆盖伪造原产地、知识产权侵权、二手电子产品违规进口、未完税商品、现金未申报和贵金属走私等类型。相关案件显示，中国来源商品可能利用自由区和包装换标实施原产地调换；中国来源箱包、工具、电子产品仍是境外边境执法重点；部分案件呈现“境外采购、违规进口、境内分销、关联企业配合”的网络化特征。

（二）旅客及跨境通道风险值得持续关注。印度机场未申报现金、印尼机场黄金走私、新加坡未完税酒案件分别涉及航空旅客、仓储配送和税收规避。巴基斯坦索斯特陆港案件还反映车辆特制夹层、边境陆路通道和中国方向物流可能被用于藏匿运输。相关风险具有单票价值较高、现场识别难度较大、资金及货物流向交织等特点。

（三）跨国有组织犯罪呈现多环节协同。澳大利亚组织偷渡案和阿根廷跨国毒品网络案表明，中国籍人员可能作为实施者、组织者或网络关联方出现在境外边境执法案件中。此类案件不能仅依赖“中国货物”关键词发现，应同步关注人员国籍、通讯平台、跨国路线、资金流和同案关系。

（四）多语种地方来源是补充官方监测的重要入口。本次新增案例分别来自英语、葡萄牙语、印度尼西亚语和西班牙语来源。多起案件标题并不直接出现“中国”，涉华证据隐藏在正文中的人员国籍、货物来源、目的地和案件组织关系中。建立“当地语种发现线索、权威来源回查事实、大模型辅助语义审核、人工复核重点结论”的流程，是提高覆盖率的关键。

{_new_case_digest()}

## 三、主要风险提示

（一）原产地欺诈风险。重点关注由中国出口、在自由区或第三国换标包装后再出口的香烟、工具、机电产品及其他易受贸易措施影响商品。

（二）电子产品非法贸易风险。加强对二手手机、拆机件、液晶屏、电池和维修配件的来源、申报品名、数量逻辑及境内分销主体关联分析。

（三）旅客携带高价值物品风险。对黄金、现金等高流动性资产强化申报审核、行程关联和异常频次分析。

（四）税收及知识产权风险。持续关注未完税烟酒、侵权箱包、假冒工具等商品通过仓储配送、邮递和集装箱渠道进入市场。

（五）跨国犯罪网络风险。对涉及中国籍人员的偷渡、毒品及其他有组织犯罪案件，应区分人员偶发参与与网络组织控制，避免简单以国籍替代风险定性。

## 四、工作建议

一是建立“国家地区、执法机关、案件类型、涉华关系、当地语种”检索矩阵，将海关官网、警察检察机关、政府通讯社和可信地方媒体纳入分层监测。

二是完善强涉华、弱涉华、重大非涉华三级审核规则，明确中国来源、目的地、中国籍人员、中国企业和转运路线等证据标准。

三是强化原文发布日期及关键事实回溯，报告中的数量、国家和执法机关必须与原始来源逐项对应。

四是将高价值案件进一步关联关区企业、商品编码、运输路线和历史申报数据，形成可转化的风险提示和查验建议。"""
    summary = (
        f"本期共分析{len(items)}条境外执法信息，其中强涉华{levels['strong']}条、"
        f"弱涉华{levels['weak']}条、重大非涉华{levels['major_non_china']}条。"
        "新增9条经核验案例，重点反映原产地欺诈、违规进出口、现金和黄金申报、"
        "未完税商品及跨国有组织犯罪风险。"
    )
    return content.strip(), summary


def _chinese_ordinal(value: int) -> str:
    digits = "零一二三四五六七八九"
    if value <= 10:
        return "十" if value == 10 else digits[value]
    if value < 20:
        return "十" + digits[value % 10]
    tens, ones = divmod(value, 10)
    return digits[tens] + "十" + (digits[ones] if ones else "")


def main(report_id: str) -> int:
    db = SessionLocal()
    try:
        report = db.get(Report, report_id)
        if not report:
            raise RuntimeError(f"Report not found: {report_id}")
        topic = db.get(Topic, TOPIC_ID)
        items = (
            db.query(CollectedItem)
            .filter(CollectedItem.topic_id == TOPIC_ID)
            .order_by(CollectedItem.published_at.desc())
            .all()
        )
        analysis, summary = _build_analysis(items)
        context = _build_item_context(items, content_limit=None, max_items=None)
        report.title = "执法信息采集 综合分析报告（2026年7月补充版）"
        report.content = _append_enforcement_case_appendix(analysis, context)
        report.summary = summary
        report.item_count = len(items)
        report.item_ids = [item.id for item in items]
        report.error_log = None
        report.status = "completed"
        db.commit()
        db.refresh(report)

        system = get_system_config(db)
        export_system = SimpleNamespace(
            report_formats=system.report_formats,
            report_output_dir=system.report_output_dir,
            report_dir_pattern=system.report_dir_pattern,
            report_title_format="{title}",
        )
        report.output_files = export_report(report, export_system, topic)
        revised_docx = (
            Path(report.output_dir)
            / f"{_safe_filename(report.title)}（格式修订版）.docx"
        )
        _write_docx(str(revised_docx), report.title, report.content or "")
        report.output_files = {**(report.output_files or {}), "docx": str(revised_docx)}
        db.commit()
        print(
            f"report_id={report.id} items={report.item_count} "
            f"content_length={len(report.content or '')}"
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: finalize_enforcement_supplement_report.py REPORT_ID")
    raise SystemExit(main(sys.argv[1]))
