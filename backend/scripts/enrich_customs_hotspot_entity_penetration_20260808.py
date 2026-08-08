"""Add reviewed entity-penetration findings to the approved customs hotspots."""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
ROOT_DIR = PROJECT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, CollectionRun  # noqa: E402


TOPIC_ID = "weekly-trade-current-affairs"
SOURCE_ID = "ai-smart-web-research"
RUN_ID = "run-customs-entity-penetration-20260808"
BATCH_ID = "customs-entity-penetration-20260808"
DB_PATH = PROJECT_DIR / "data" / "gather.db"
REVIEW_MARKER = "【实体穿透复核（2026-08-08）】"
SUMMARY_MARKER = "实体穿透复核："


REVIEWS = {
    "customs-hotspot-reviewed-20260808-01": {
        "summary": (
            "可穿透到境内保税船燃经营企业、进口资质企业、供油船和电子燃油交付单，"
            "但公开资料尚不能把任何主体与2026年6月增量或违规行为直接关联。"
        ),
        "content": """【实体穿透复核（2026-08-08）】
一、复核结论
本条可以形成具体境内核查对象池，并可由报关单、保税账册、储罐、供油船和电子燃油交付单继续穿透到单票交易；但路透报道只有全国汇总数据，以下企业、人员和船舶均不得据此认定为涉事或违规主体。

二、境内企业对象池
1. 直接经营及配送节点：中石化浙江舟山石油有限公司、浙江自贸区中石油燃料油有限责任公司、浙江自贸区东方同舟海事服务供应有限公司。公开资料显示，前两家直接从事舟山保税船供油，东方同舟由中石化燃料油销售有限公司与舟山交投集团所属企业合资组建并运营专业供油船队。
2. 上海经营节点：中石油上港能源有限公司、上海富远燃料油有限责任公司可作为上海港保税船燃业务的优先核查对象。核查范围应以2026年6月实际报关、入库和加注数据确定，不宜按历史持牌名单全量推定。
3. 进口资质候选节点：商务部公布的2026年非国营贸易燃料油进口允许量企业中，物产中大油气（浙江）有限公司、浙江和创博远供应链有限公司、宁波起航新材料有限公司等可与浙江保税仓储和供船流向做交叉比对。获得进口资质不等于实际参与本期业务。

三、人员与运输工具
公开资料可识别供油船“东方朝阳2”“东方朝阳”“溢沣润66”。“东方朝阳2”由东方同舟投资建造，2026年1月曾为“OCEAN TRINITY”轮加注1600吨低硫燃料油；“东方朝阳”和“溢沣润66”曾参与舟山电子燃油交付单应用。首航报道还公开了“东方朝阳2”轮船长钱峰、东方同舟董事长丁建波等运营背景人员，但这些公开身份与2026年6月汇总增量之间没有直接证据联系。交易层面的有效人员节点应从电子燃油交付单签署人、报关经办人、保税账册管理员、储罐计量员和当航次船长中提取。

四、建议穿透链路
以HS 2710保税进口报关单为起点，依次关联进口经营单位、境内收货人、保税仓库及储罐号、入库计量单、调拨单、供油企业、供油船船名及船舶识别号、受油船IMO号和AIS轨迹、质量流量计记录、电子燃油交付单、出口报关单及舱单。重点筛查同一批次重复核销、库存倒挂、损耗率异常、交付数量与流量计不一致、受油船非国际航次、供油船装载保税油后异常靠泊内贸港区等情形。

五、证据等级
企业对象池：高；具体交易关联：待海关数据确认；人员关联：低；运输工具穿透：中。当前材料只支持确定核查范围，不支持认定违法事实。""",
        "organizations": [
            "中石化浙江舟山石油有限公司",
            "浙江自贸区中石油燃料油有限责任公司",
            "浙江自贸区东方同舟海事服务供应有限公司",
            "中石油上港能源有限公司",
            "上海富远燃料油有限责任公司",
            "物产中大油气（浙江）有限公司",
            "浙江和创博远供应链有限公司",
            "宁波起航新材料有限公司",
        ],
        "people": [
            {"name": "钱峰", "role": "东方朝阳2轮首航公开船长", "relation": "运营背景，非本期交易证据"},
            {"name": "丁建波", "role": "东方同舟公开董事长", "relation": "企业背景，非本期交易证据"},
        ],
        "transport_assets": [
            {"name": "东方朝阳2", "type": "保税燃料供油船", "relation": "公开运营资产，尚未关联2026年6月汇总数据"},
            {"name": "东方朝阳", "type": "保税燃料供油船", "relation": "曾参与电子燃油交付单应用"},
            {"name": "溢沣润66", "type": "保税燃料供油船", "relation": "曾参与电子燃油交付单应用"},
            {"name": "OCEAN TRINITY", "type": "国际航行受油船", "relation": "东方朝阳2首单公开受油船，非本期交易证据"},
        ],
        "routes_or_ports": ["舟山港", "上海港"],
        "evidence_levels": {
            "domestic_entities": "high_target_pool_only",
            "transaction_link": "requires_customs_data",
            "people": "low_background_only",
            "transport_tools": "medium_public_assets_not_period_linked",
        },
        "penetration_keys": [
            "HS 2710保税进口报关单",
            "进口经营单位与境内收货人",
            "保税仓库和储罐号",
            "入库计量单与调拨单",
            "供油船船名和船舶识别号",
            "受油船IMO号与AIS轨迹",
            "质量流量计记录与电子燃油交付单",
            "出口报关单和舱单",
        ],
        "related_urls": [
            "https://www.zsbunker.cn/?lang=zh_CN",
            "https://www.zsbunker.cn/sinopec?lang=zh_CN",
            "https://info.chineseshipping.com.cn/cninfo/News/202507/t20250703_1406063.shtml",
            "https://zjnews.zjol.com.cn/yc/qmt/202601/t20260114_31455129.shtml",
            "https://www.shanghai.gov.cn/cmsres/65/65a56a700d5b4b24b3445711f9a7e87e/6b39e10f35e7730e48a2130eaf8473c1.pdf",
        ],
    },
    "customs-hotspot-reviewed-20260808-02": {
        "summary": (
            "哈方公开改装油箱案例已穿透到吉木乃对应口岸、4名中国籍司机和4辆空载货车，"
            "但企业名称、姓名、车牌及VIN尚未公开，需通过中哈执法数据碰撞继续识别。"
        ),
        "content": """【实体穿透复核（2026-08-08）】
一、改装案例补充
东哈萨克斯坦州国家收入局披露，2026年7月10日，迈卡普恰盖海关检查4辆驶往中国的空载货车，在非原厂、专门加装的附加油箱内发现2640升柴油，合计超过2吨；车辆由中国公民驾驶，4名司机分别被处以32437.5坚戈罚款，材料移交东哈萨克斯坦州经济调查部门。该案是哈方1342起燃油非法外运通报中能够明确确认中国方向、改装油箱和货车数量的实案，不能据此把其余案件全部认定为流向中国。

二、中国境内关联节点
迈卡普恰盖口岸与中国新疆吉木乃口岸相对应，属于中哈公路客货运输口岸。境内第一核查节点应确定为吉木乃口岸的车辆入境、边检和海关查验记录；后续可穿透至车辆中国登记所有人、道路运输经营人、司机所属或结算企业、前序出境货物的经营单位、口岸报关代理以及境内燃油接收或销售节点。公开通报没有披露任何中国企业名称，因此当前不能列出具体涉案企业。

三、人员和运输工具穿透情况
人员层面已知为4名中国籍司机，但姓名、证件号码、雇主和历史通关记录未公开。运输工具层面已知为4辆空载货车、装有非原厂附加油箱并夹带2640升柴油，但车牌、VIN/车架号、品牌型号、核定油箱容积、车辆所有人和承运企业均未公开。公开照片不足以可靠识别这些字段，不应据图推定。

四、可执行数据碰撞
建议向哈方调取现场检查笔录、司机陈述、车辆照片、行政处罚决定、经济调查登记号和加油付款资料；境内以2026年7月10日前后迈卡普恰盖至吉木乃方向的4辆空载回程货车为条件，碰撞吉木乃海关车辆进境记录、边检人员记录、车牌、VIN、轴重和整车自重、道路运输证、舱单或车辆载货清单、查验影像及口岸预约记录。随后反查车辆登记所有人、承运企业、司机劳动或结算关系、上一程出境报关单及哈境内加油站付款账户。重点筛查同一司机或车辆短期高频往返、空载回程自重异常、申报自用燃油与原厂油箱容积不符、改装油箱反复拆装等特征。

五、证据等级
口岸和方向：高；人员国籍及数量：中；车辆类型及数量：中；具体企业、姓名、车牌和VIN：待执法数据确认。该案已具备按日期、方向、车辆状态和数量开展精准碰撞的条件。""",
        "organizations": [],
        "people": [
            {"name": None, "count": 4, "nationality": "中国", "role": "涉案货车司机", "relation": "姓名和雇主未公开"},
        ],
        "transport_assets": [
            {
                "name": None,
                "count": 4,
                "type": "空载货车",
                "modification": "非原厂专门加装附加油箱",
                "fuel": "柴油2640升",
                "identifiers": "车牌、VIN、品牌型号和所有人未公开",
            }
        ],
        "routes_or_ports": ["哈萨克斯坦迈卡普恰盖口岸", "中国新疆吉木乃口岸"],
        "evidence_levels": {
            "domestic_entities": "not_publicly_identified",
            "route_and_port": "high",
            "people": "medium_count_and_nationality_only",
            "transport_tools": "medium_type_count_and_modification_only",
        },
        "penetration_keys": [
            "2026年7月10日前后口岸时间窗",
            "迈卡普恰盖至吉木乃方向",
            "4辆空载回程货车",
            "车牌、VIN和道路运输证",
            "司机证件和边检记录",
            "车辆轴重、自重和原厂油箱容积",
            "上一程出境报关单及载货清单",
            "哈境内加油付款记录",
            "哈方行政处罚决定和经济调查登记号",
        ],
        "related_urls": [
            "https://www.gov.kz/memleket/entities/kgd-vko/press/news/details/1260706?lang=ru",
            "https://bes.media/amp/inostrantsy-pytalis-vyvezti-iz-kazahstana-bolee-dvuh-tonn-topliva/",
            "https://tengrinews.kz/kazakhstan_news/iz-kazahstana-pyitalis-tayno-vyivezti-2-tonnyi-topliva-604222/amp/",
            "https://www.mfa.gov.cn/web/wjb_673085/zzjg_673183/bjhysws_674671/bhgjty/kaglty/202303/P020230320562638731375.pdf",
        ],
    },
    "customs-hotspot-reviewed-20260808-03": {
        "summary": (
            "可由商务部首次配额附件识别7家供港澳小麦粉企业及锯材执行主体，"
            "第二次分配后的实际企业、人员和运输工具仍需以地方分配备案、许可证及报关物流数据确认。"
        ),
        "content": """【实体穿透复核（2026-08-08）】
一、复核结论
本条能够穿透到明确的中国境内配额企业对象池。商务部2026年第一次分配附件已列出7家供港澳小麦粉企业；2026年第二次分配通知要求广东省、深圳市将新增配额通知有关企业并报送执行情况，因此最终核查名单应再叠加地方二次分配备案和实际签发许可证。列入配额名单不代表企业存在违规。

二、供港澳小麦粉企业对象池
1. 佛山市三水丰顺食品有限公司，统一社会信用代码914406006183554792。
2. 广东加福加德食品技术股份有限公司，统一社会信用代码91441200735015502Q。
3. 中山新纪元面粉有限公司，统一社会信用代码91442000618126684K。
4. 广东金禾面粉有限公司，统一社会信用代码91440606783892315H。
5. 深圳市面粉有限公司，统一社会信用代码91440300192199869H，公开资料显示为深粮控股体系企业。
6. 深圳南海粮食工业有限公司，统一社会信用代码91440300618837697M。
7. 蛇口南顺面粉有限公司，统一社会信用代码91440300618836889Y，公开资料显示属南顺香港集团面粉业务网络。
锯材方面，第一次分配通知直接发至中国建材集团有限公司，附件显示相关配额由北新国际木业有限公司执行，可作为锯材业务的中央企业节点。活畜禽、边贸粮食的附件主要按地区分配，具体企业需以地方二次分配备案为准。

三、人员和运输工具
政策文件没有披露具体经办人员、报关员、司机、车牌、集装箱号或船名。人员层面应从配额申请经办人、出口许可证申领人、报关人员、生产及出库责任人、港澳收货人和实际控制人中穿透；运输工具层面应从报关单、载货清单、跨境车辆备案、集装箱设备交接单、提运单和港澳入库记录中提取。对活猪、活牛还应关联动物检疫证书、运输车辆、承运企业和目的地屠宰或接收单位。

四、建议穿透链路
以企业统一社会信用代码为主键，关联地方二次分配备案、配额证明、出口许可证号码及备注、报关单经营单位和发货人、HS 1101/1006/4407等商品、申报口岸、目的国（地区）、数量核销、运输工具、港澳收货人及后续仓储/再出口记录。重点识别非名单企业借用抬头、同一配额跨企业或超量核销、边贸粮食跨省或从非边贸口岸申报、许可证目的地和实际物流不一致、港澳小麦粉短期再出口至第三地等情形。

五、证据等级
境内企业对象池：高；实际使用第二次配额的企业：待地方备案确认；人员关联：低；运输工具关联：待单票物流数据确认。当前已具备以统一社会信用代码批量碰撞许可证和报关数据的条件。""",
        "organizations": [
            "佛山市三水丰顺食品有限公司",
            "广东加福加德食品技术股份有限公司",
            "中山新纪元面粉有限公司",
            "广东金禾面粉有限公司",
            "深圳市面粉有限公司",
            "深圳南海粮食工业有限公司",
            "蛇口南顺面粉有限公司",
            "中国建材集团有限公司",
            "北新国际木业有限公司",
        ],
        "organization_identifiers": {
            "佛山市三水丰顺食品有限公司": "914406006183554792",
            "广东加福加德食品技术股份有限公司": "91441200735015502Q",
            "中山新纪元面粉有限公司": "91442000618126684K",
            "广东金禾面粉有限公司": "91440606783892315H",
            "深圳市面粉有限公司": "91440300192199869H",
            "深圳南海粮食工业有限公司": "91440300618837697M",
            "蛇口南顺面粉有限公司": "91440300618836889Y",
        },
        "people": [],
        "transport_assets": [],
        "routes_or_ports": ["广东省相关出口口岸", "深圳市相关出口口岸", "香港", "澳门", "边贸口岸"],
        "evidence_levels": {
            "domestic_entities": "high_official_first_allocation",
            "second_allocation_users": "requires_local_filing",
            "people": "low_not_in_policy_document",
            "transport_tools": "requires_shipment_data",
        },
        "penetration_keys": [
            "企业统一社会信用代码",
            "地方二次分配备案",
            "配额证明和出口许可证号码",
            "许可证备注及目的地限制",
            "出口报关单经营单位和发货人",
            "报关口岸与离境运输工具",
            "港澳收货人、仓储和后续再出口记录",
            "活畜禽检疫证书和承运车辆",
        ],
        "related_urls": [
            "https://wms.mofcom.gov.cn/ztxx/ncpmyzt/myzc/art/2025/art_964e751d9a844bf383a0bc983f537780.html",
            "https://wms.mofcom.gov.cn/zcfb/wmgl/art/2026/art_304de80295e34e5db1b0525dfb4c5483.html",
            "https://www.ndrc.gov.cn/xwdt/tzgg/202411/P020241119412757974562.pdf",
        ],
    },
}


def replace_review(content: str, review: str) -> str:
    base = content.split(REVIEW_MARKER, 1)[0].rstrip()
    return f"{base}\n\n{review.strip()}"


def backup_database(backup_path: Path) -> None:
    with sqlite3.connect(DB_PATH) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)


def main() -> int:
    backup_dir = ROOT_DIR / "work" / "political_hotspots" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"gather-before-entity-penetration-{datetime.now():%Y%m%d-%H%M%S}.db"
    backup_database(backup_path)

    db = SessionLocal()
    now = datetime.now(timezone.utc)
    updated_ids: list[str] = []
    try:
        for item_id, review in REVIEWS.items():
            item = db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
            if item is None:
                raise RuntimeError(f"Missing approved hotspot item: {item_id}")

            item.content = replace_review(item.content or "", review["content"])
            base_summary = (item.summary or "").split(f"\n\n{SUMMARY_MARKER}", 1)[0].rstrip()
            item.summary = f"{base_summary}\n\n{SUMMARY_MARKER}{review['summary']}".strip()
            item.content_hash = hashlib.sha256(
                f"{item.url}\n{item.content}".encode("utf-8")
            ).hexdigest()
            item.status = "enriched"
            item.updated_at = now

            entities = dict(item.entities or {})
            entities["organizations"] = review["organizations"]
            entities["people"] = review["people"]
            entities["transport_assets"] = review["transport_assets"]
            entities["routes_or_ports"] = review["routes_or_ports"]
            if review.get("organization_identifiers"):
                entities["organization_identifiers"] = review["organization_identifiers"]
            item.entities = entities

            metadata = dict(item.raw_metadata or {})
            related_urls = list(metadata.get("related_urls") or [])
            for url in review["related_urls"]:
                if url not in related_urls:
                    related_urls.append(url)
            metadata["related_urls"] = related_urls
            metadata["entity_penetration_review"] = {
                "reviewed_at": now.isoformat(),
                "method": "public_source_entity_and_transport_penetration",
                "conclusion": review["summary"],
                "organizations": review["organizations"],
                "organization_identifiers": review.get("organization_identifiers", {}),
                "people": review["people"],
                "transport_assets": review["transport_assets"],
                "routes_or_ports": review["routes_or_ports"],
                "evidence_levels": review["evidence_levels"],
                "penetration_keys": review["penetration_keys"],
                "disclaimer": (
                    "公开名单、资质、企业关系和运营资产仅用于形成核查对象池；"
                    "未取得单票交易或执法证据前，不得认定相关主体实施违法行为。"
                ),
            }
            tags = list(metadata.get("tags") or [])
            for tag in ["境内实体穿透", "人员与运输工具核查"]:
                if tag not in tags:
                    tags.append(tag)
            metadata["tags"] = tags
            item.raw_metadata = metadata
            updated_ids.append(item.id)

        run = db.query(CollectionRun).filter(CollectionRun.id == RUN_ID).first()
        if run is None:
            run = CollectionRun(id=RUN_ID, source_id=SOURCE_ID, topic_id=TOPIC_ID)
            db.add(run)
        run.source_id = SOURCE_ID
        run.topic_id = TOPIC_ID
        run.status = "completed"
        run.batch_id = BATCH_ID
        run.keywords_used = [
            "中国境内实体",
            "企业关系穿透",
            "人员与运输工具",
            "保税船燃供油船",
            "迈卡普恰盖吉木乃改装油箱",
            "农产品出口配额企业",
        ]
        run.items_found = len(REVIEWS)
        run.items_new = 0
        run.items_updated = len(updated_ids)
        run.items_failed = 0
        run.started_at = now
        run.completed_at = now
        run.duration_ms = 0
        run.error_log = None
        run.metadata_json = {
            "provider": "open_source_entity_review",
            "review_type": "entity_people_transport_penetration",
            "updated_item_ids": updated_ids,
            "public_evidence_only": True,
            "disclaimer": "Named entities are review targets, not alleged violators.",
        }

        db.commit()
        print(f"Backup: {backup_path}")
        print(f"Updated items: {', '.join(updated_ids)}")
        print(f"Run: {RUN_ID}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
