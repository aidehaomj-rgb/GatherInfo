"""Configure recurring customs-risk hotspot research for the trade-current-affairs topic."""
from __future__ import annotations

import json
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8109/api/v1"
TOPIC_ID = "weekly-trade-current-affairs"


def main() -> int:
    with urlopen(f"{BASE_URL}/topics/{TOPIC_ID}", timeout=30) as response:
        current = json.load(response)

    payload = {
        "name": "涉进出口时政热点",
        "description": (
            "跟踪近20天全球能源、化肥、化工品、粮食、战略矿产、制裁和供应链异常，"
            "识别价格倒挂、供需缺口、第三国转运、原产地洗白、伪报瞒报、贸易型洗钱及"
            "边境走私等海关进出口监管风险。"
        ),
        "keywords": [
            "能源短缺", "燃油价格", "化肥短缺", "化工原料", "粮食价格", "战略矿产",
            "出口管制", "制裁规避", "第三国转运", "原产地", "贸易救济", "走私风险",
            "伪报瞒报", "贸易型洗钱", "fuel shortage", "fertilizer shortage",
            "critical minerals", "export control", "sanctions evasion", "transshipment",
            "origin fraud", "customs smuggling",
        ],
        "description_prompt": (
            "检索近20天公开信息，按照‘事件变化—供需缺口或区域价差—可能的跨境异常路径—"
            "可由中国海关数据验证的指标’筛选。重点覆盖能源、化肥及化工原料、粮食、战略矿产、"
            "两用物项、制裁规避、贵金属、边境走私、保税转口和检验检疫。原文可以不出现中国，"
            "但必须有地理邻接、既有对华贸易路线、实际货物流、显著价差、供应依赖或中国实施的"
            "管制规则等客观依据，形成完整的对华传导链。风险必须落到中国进境、出境、陆路边境、"
            "中国港口与舱单、保税监管、出口管制、检验检疫或跨境电商等海关监管环节。仅影响外国"
            "海关征税、外国贸易救济、外国市场准入或外国进口商合规的内容不得纳入。每条必须保留"
            "发布日期、原文链接和来源性质。"
            "区分已证实事实与风险研判；风险研判使用‘可能、或’等措辞，不得把推断写成违法事实。"
            "下一步核查必须同时明确数据表或单证、HS品类或企业/路线、异常指标和处置动作，覆盖"
            "报关单、舱单、保税账册、原产地证、许可证、船舶AIS、企业关联和最终用户。优先政府"
            "公告、官方执法通报、国际组织、权威通讯社和"
            "专业行业数据；缺少日期或无法核验来源的内容不进入正式报告。"
        ),
        "source_ids": current.get("source_ids") or [],
        "collect_window_days": 20,
        "schedule_cron": "0 8 1,16 * *",
        "is_scheduled": True,
        "is_active": True,
        "auto_report": True,
        "auto_report_type": "analytical",
        "auto_tag_rules": [
            {"keyword": "走私", "tag": "海关监管风险"},
            {"keyword": "第三国", "tag": "第三国转运"},
            {"keyword": "原产地", "tag": "原产地风险"},
            {"keyword": "出口管制", "tag": "出口管制"},
            {"keyword": "化肥", "tag": "化肥"},
            {"keyword": "燃油", "tag": "能源"},
            {"keyword": "战略矿产", "tag": "战略矿产"},
            {"keyword": "贸易型洗钱", "tag": "贸易型洗钱"},
        ],
    }
    request = Request(
        f"{BASE_URL}/topics/{TOPIC_ID}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="PUT",
    )
    with urlopen(request, timeout=30) as response:
        updated = json.load(response)
    print(json.dumps({
        "id": updated["id"],
        "name": updated["name"],
        "collect_window_days": updated["collect_window_days"],
        "schedule_cron": updated["schedule_cron"],
        "is_scheduled": updated["is_scheduled"],
        "auto_report": updated["auto_report"],
        "source_count": len(updated.get("source_ids") or []),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
