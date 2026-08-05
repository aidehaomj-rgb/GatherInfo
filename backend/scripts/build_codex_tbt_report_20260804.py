"""Persist the Codex-authored technical barriers to trade report for 2026-08-04."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, Report, SystemConfig, Topic  # noqa: E402
from app.report_export import export_report  # noqa: E402


REPORT_ID = "rpt-codex-tech-regulations-20260804"
TOPIC_ID = "tech-regulations"
ITEM_IDS = ["f19381eb66ce6dec", "8becff95645615ec", "f200e3fa6c2a277a"]
TITLE = "技术性贸易措施 综合分析报告（2026年8月4日）"
SUMMARY = (
    "本次监测聚焦电池供应链尽职调查、光伏组件和家电能效要求、药品注册便利化，"
    "以及SPS检测透明度等动向。分析同时发现部分条目的网页发布日期与系统记录不一致，"
    "建议在形成正式预警前回溯WTO通报号、原始法规文本、生效日期和评议截止日期。"
)


CONTENT = r"""## 一、监测概况

本报告由 Codex 对本次“技术性贸易措施”主题采集结果进行复核整理，共纳入3条采集条目。信息涉及欧盟电池法规、厄瓜多尔家用洗碗机能效要求、菲律宾药品许可注册、泰国光伏组件标准，以及世界贸易组织卫生与植物卫生措施委员会有关采样检测透明度等议题。

本批数据可用于发现风险方向，但尚不能直接等同于正式法规结论。复核发现，部分条目的系统发布日期与原网页路径、正文所载日期不一致；市场监管总局技术性贸易措施页面属于多条通报的汇总入口，尚缺少各措施对应的WTO通报号、评议截止日期和最终实施文本。因此，本报告将“趋势识别”和“事实核验”分开表述。

## 二、重点动态

### （一）欧盟电池合规要求继续向供应链追溯延伸

采集条目显示，欧盟电池法规相关调整涉及钴、天然石墨、锂、镍等原材料尽职调查义务，并同时涉及标签、废旧电池管理和生产者责任等要求。其影响不只落在电池成品，也可能沿供应链传导至正负极材料、关键矿物、零部件生产和出口企业。

需要注意的是，该条目链接路径标示为2025年5月，与系统记录的2026年7月26日不一致。现阶段宜将其作为“持续性合规议题”纳入跟踪，不宜据此认定为2026年新发布措施。后续应以欧盟委员会、EUR-Lex正式文本及修订后的实施时间表为准。

### （二）光伏组件、家电能效和药品注册成为新一轮通报关注点

市场监管总局技术性贸易措施通报评议平台汇总信息显示：厄瓜多尔关注家用洗碗机能效标准修订，泰国拟对光伏组件提出工业标准要求，菲律宾对本地生产药品的许可和注册申请设置监管支持或优先处理安排。

对我国出口企业而言，洗碗机和光伏组件措施可能影响能效标识、检测方法、技术参数、合格评定和随附文件；药品注册政策则可能改变本地生产与进口产品之间的审批节奏和市场准入条件。由于当前采集内容为汇总页面，必须进一步取得每项措施的原始通报，核对产品范围、HS编码、适用对象、过渡期和评议期限。

### （三）SPS治理更加重视检测透明度和新技术应用

WTO官方信息显示，SPS委员会将围绕采样、检测和分析方法透明度以及跨境运输中的有害生物风险开展专题讨论，并关注人工智能和新兴技术在SPS领域的应用。这表明成员方对检测规则可预见性、方法一致性和信息共享的关注上升。

该网页正文日期为2026年3月11日，系统却记录为2026年8月1日，属于明显的发布日期映射偏差。其政策价值主要在于提示未来议题方向，不应作为8月新出台措施统计。

## 三、风险研判

### （一）供应链证明责任上升

境外技术法规正在从成品性能要求向原材料来源、生产过程、第三方验证和全生命周期责任延伸。电池、光伏等优势出口产业可能面临更细的供应链追溯、检测认证和文件留存要求，企业合规成本及因材料不完整造成的通关延误风险上升。

### （二）标准差异可能形成隐性市场准入门槛

能效、尺寸、功率、材料、标签和测试方法等要求具有较强专业性。若目的国标准与我国现行标准、检测方法或认证周期不衔接，企业即使产品性能合格，也可能因证书、标签或测试报告不符合要求而影响出口。

### （三）当前采集结果存在时间和来源层级风险

本批3条信息中，2条存在系统发布日期与原网页信息不一致，1条为多项通报汇总入口。若直接据此生成预警，容易将旧闻误判为新规，或遗漏正式通报中的生效条件。因此，发布日期核验和原始法规回溯应成为技术性贸易措施报告的强制环节。

## 四、工作建议

一是建立“国家（地区）—商品—措施—时间节点”监测表。优先覆盖电池及关键矿物、光伏组件、家用电器、药品等重点商品，逐项记录通报号、法规名称、产品范围、HS编码、评议截止日期、生效日期和主管机构。

二是落实原始来源双重核验。搜索结果和汇总页只用于发现线索，正式研判前应回溯WTO TBT/SPS通报、目的国主管部门或正式法规数据库；网页发布日期、正文日期和系统入库日期不一致时，标记为“待核验”，不得按最新政策统计。

三是加强关区企业影响匹配。将措施涉及商品与重点出口企业、主要目的国和历史贸易量进行关联，识别可能受影响企业，形成分行业、分国别的提示清单，并及时向业务部门和企业推送评议及过渡期信息。

四是完善系统采集规则。发布日期应优先读取原网页结构化时间和正文明确日期，禁止以搜索引擎抓取时间替代政策发布日期；聚合页面应拆分为独立通报条目，并保存原始通报号和链接后再进入正式报告。

## 五、结论

本次采集反映出，技术性贸易措施正进一步向绿色低碳、供应链尽职调查、产品能效、合格评定和检测透明度延伸。电池、光伏、家电和药品等领域值得持续关注。当前最需优先解决的不是扩大条目数量，而是提高日期识别、原始通报回溯和措施要素结构化能力，确保信息从“可发现”转化为“可核验、可研判、可处置”的风险情报。

## 附录：本次纳入条目

1. 市场监管总局技术性贸易措施通报评议中心汇总信息（系统条目ID：f19381eb66ce6dec）。
2. 欧盟电池法规相关提案信息（系统条目ID：8becff95645615ec；发布日期待复核）。
3. WTO SPS委员会检测透明度与新技术议题（系统条目ID：f200e3fa6c2a277a；原网页日期为2026年3月11日）。
"""


def main() -> int:
    db = SessionLocal()
    try:
        topic = db.get(Topic, TOPIC_ID)
        if topic is None:
            raise RuntimeError(f"Topic not found: {TOPIC_ID}")

        existing_ids = {
            row.id for row in db.query(CollectedItem).filter(CollectedItem.id.in_(ITEM_IDS)).all()
        }
        missing = [item_id for item_id in ITEM_IDS if item_id not in existing_ids]
        if missing:
            raise RuntimeError(f"Collected items not found: {missing}")

        report = db.get(Report, REPORT_ID)
        if report is None:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID, title=TITLE)
            db.add(report)

        report.title = TITLE
        report.report_type = "analytical"
        report.content = CONTENT.strip()
        report.summary = SUMMARY
        report.status = "completed"
        report.model_id = "codex-authored"
        report.tokens_used = 0
        report.item_count = len(ITEM_IDS)
        report.item_ids = ITEM_IDS
        report.date_range_start = datetime(2026, 7, 21, 0, 0, 0)
        report.date_range_end = datetime(2026, 8, 4, 23, 59, 59)
        report.generated_at = datetime(2026, 8, 4, 8, 20, 0)
        report.error_log = None
        report.output_files = None
        report.output_dir = None

        system = db.get(SystemConfig, "global")
        export_report(report, system, topic)
        db.commit()
        db.refresh(report)
        print(json.dumps({
            "report_id": report.id,
            "title": report.title,
            "model_id": report.model_id,
            "item_count": report.item_count,
            "output_files": report.output_files,
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
