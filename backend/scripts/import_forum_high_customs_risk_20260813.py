from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import CollectedItem, CollectionRun, Topic


TOPIC_ID = "foreign-trade-forum-risk-monitoring"
RUN_ID = "codex-forum-high-customs-risk-20260813"
SOURCE_ID = "reddit-alibaba"
NOW = datetime.now(timezone.utc)

LEADS = [
    ("01", "深圳至纽约40HQ家具DDP被指可能低报并使用第三方进口商", "2026-08-11", "https://www.reddit.com/r/freightforwarding/comments/1vl4yfb/how_to_find_trustable_and_well_priced_forwarder/", "家具；40HQ；深圳/盐田或蛇口—纽约皇后区", "帖子询价列明深圳至纽约40HQ家具运输；评论称部分DDP会低报，或以货代关联实体作为进口商。该说法属于论坛陈述，尚无报关单证明。", "调取对应订舱、主分提单、舱单和出口报关单，核对发货人、品名、数量、成交价格、境外进口商；筛查同一货代同航次拼柜货值显著偏低、收付款人与贸易主体不一致。"),
    ("02", "山东聊城钢制螺旋桩DDP使用他人买方及玻璃柜提单", "2026-07-27", "https://www.reddit.com/r/Alibaba/comments/1v82wms/my_first_alibaba_order_steel_screw_piles_ddp_to/", "Shandong Liaocheng Chengxin Ganglian Metal Manufacturing Co., Ltd.；钢制螺旋桩；中国—德国—克罗地亚", "发帖人称约3300美元钢制螺旋桩采用双清包税，卖方提供的运输证明将买方写为荷兰烟草公司、货物写为GLASSES CABINET并使用HS 7610.90，而实际货物据称为钢制螺旋桩、HS 7308.90。", "以企业英文名、订单号、提单所列荷兰买方和德国入境节点倒查中国出口报关单、装箱单和舱单；比对实际材质、用途、HS编码、件重体积及欧盟进口MRN，发现货证不符转稽查。"),
    ("03", "广东工厂出口货物因申报HS编码错误在芝加哥被扣", "2026-08-10", "https://www.reddit.com/r/Business_in_China/comments/1vky64f/my_suppliers_onedigit_mistake_just_froze_15000_of/", "广东工厂；约500份订单；中国—芝加哥", "发帖人称长期合作的广东工厂负责出口文件，本批约1.5万美元、500份订单因申报HS编码错误在芝加哥海关被拦截。帖子未披露企业全称和具体货物。", "按时间、目的港芝加哥、票数和货值组合筛查广东出口快件/空运申报；核对更正前后HS、品名、规格和监管条件，识别同一发货人历史归类跳变；缺少企业名，先作为路线模式线索。"),
    ("04", "OneXPlayer设备订单提供299美元建议申报值选项", "2026-07-15", "https://www.reddit.com/r/OneXPlayer/comments/1uwusa5/china_shipping_and_custom_duty/", "OneXPlayer/One Netbook；掌机、外置电池、扩展坞；中国—美国", "发帖人称约3107美元的设备及配件订单可选择全额申报或平台建议的299美元申报值，其选择后者并支付39美元关税；另有评论称该渠道通常低报。内容为用户自述，需以订单和申报数据核实。", "筛查相关品牌出口美国的快件申报，将订单支付金额、商业发票、建议申报值和报关价格交叉比对；联查内置/外置锂电池的UN38.3、危险品运输文件、件数重量及拆单频次。"),
    ("05", "中国出口DDP拼箱被指混报、低报及规避反倾销税", "2026-07-21", "https://www.reddit.com/r/smallbusinessUS/comments/1v2k5v9/the_ddp_compliance_trap_thats_putting/", "中国货代；Amazon/Shopify货物；中国—美国", "帖子称部分中国DDP货代将不同商品混装，使用自身或关联美国实体作为进口商，并可能低报或误归类以规避301及反倾销税。帖子未给出具体货代，属于风险模式线索。", "筛查中国出口同一集装箱多品类、笼统品名、单位价格异常及美国收货人为高频壳公司的记录；联查HBL/MBL、出口报关单、境外Entry Summary和实际电商订单，按货代与进口商关系聚类。"),
    ("06", "中国出口至欧盟DDP拼票无法提供进口申报及MRN", "2026-07-30", "https://www.reddit.com/r/Alibaba/comments/1vapn29/ddp_vs_dap_for_eu_imports_customs_documentation/", "中国供应商/货代；拼箱货物；中国—罗马尼亚", "罗马尼亚企业称多家中国DDP货代以集中申报涉及其他客户隐私为由，无法提供以买方名义出具的进口申报或MRN。缺单不当然证明违法，但提示第三方抬头和拼票申报风险。", "筛查发往罗马尼亚及经德国、荷兰入境的集中DDP货物，核对中国出口分票、主提单、境外申报主体和最终收货人；关注出口多票对应境外单一笼统品名、数量价值无法勾稽。"),
    ("07", "中国采购中间商咨询变更原产地证出口人并重制单证", "2026-07-20", "https://www.reddit.com/r/supplychain/comments/1v18rdt/can_the_exporter_name_on_a_certificate_of_origin/", "中国供应商、出口代理；需许可证商品；中国—未披露目的国", "发帖人称从中国采购需特殊进出口许可证的商品，为隐藏供应商，考虑由出口代理列为原产地证出口人，同时将提单、发票和装箱单改为中间商名称。其寻求合规方案，不代表已经实施违规。", "对需许可证商品核验原产地证申请企业、生产商、出口代理、报关经营单位和许可证持有人关系；比对提单、发票、装箱单与原产地证，发现主体不一致时要求代理协议和货权链证明。"),
    ("08", "中国出口食品DDP被提示存在低报和检疫文件缺失风险", "2026-07-19", "https://www.reddit.com/r/freightforwarding/comments/1v12vln/hi_can_anyone_recommend_uk_based_freight/", "食品20至30千克；中国—英国", "帖子讨论从中国向英国运输20至30千克食品；评论明确提示中国侧DDP若不能分列关税和增值税，可能存在低报，肉乳蛋蜂蜜及部分高风险食品还需预申报和卫生文件。未披露具体企业。", "筛查同路线食品快件的品名、配料、重量、货值和监管证件，核对出口生产企业备案、卫生证书及冷链条件；关注商业批量拆为个人包裹、笼统申报食品样品和同收件人高频入境。"),
    ("09", "中国物流节点被指对肽类产品换标并改道", "2026-07-22", "https://www.reddit.com/r/Alibaba/comments/1v3u804/chinese_logistics_swapping_out_peptides_with_new/", "肽类/API；中国分拨点—第三国—美国", "帖子称中国物流公司在分拨点更换肽类产品标签并重新路由；评论指出若中国API生产商与申报马来西亚原产地不一致，可能形成来源和标签异常。帖子缺少物流企业及运单号，需作为模式线索。", "筛查肽类及第29章相关商品经马来西亚等第三国转运记录，核对生产批号、DMF生产商、原产地证、换标记录、运单轨迹和货物包装；对中国出境后短暂停留即转运且原产国变化的批次布控。"),
    ("10", "中国至美洲货运论坛集中提示HS、低报、木包装和电池风险", "2026-08-07", "https://www.reddit.com/r/freightforwarding/comments/1vhn59i/factors_worth_considering_when_exporting_from/", "中国出口；多供应商拼箱；美洲航线", "帖子总结中国出口美洲的高频异常包括错误HS、低报、木包装无ISPM 15标识、危险品/电池文件缺失和多供应商拼箱单证协调失败。该帖是从业者风险提示，不是具体违法指控。", "建立多供应商拼箱专项规则，核对分票报关与总舱单、木包装IPPC标识、锂电池UN38.3/MSDS、危险品订舱申报和实际件重；按货代统计更改单、查验及退运异常率。"),
]


def main() -> None:
    db = SessionLocal()
    try:
        topic = db.get(Topic, TOPIC_ID)
        if not topic:
            raise RuntimeError("topic missing")
        run = db.get(CollectionRun, RUN_ID) or CollectionRun(id=RUN_ID, source_id=SOURCE_ID)
        run.topic_id, run.status = TOPIC_ID, "completed"
        run.started_at = run.completed_at = NOW
        run.items_found = run.items_new = len(LEADS)
        run.items_failed = 0
        run.metadata_json = {"method": "direct forum collection failed; Codex search and post-level review", "risk_threshold": "high", "claims_unverified": True}
        db.add(run)
        for key, title, date, url, objects, statement, checks in LEADS:
            content = f"论坛陈述：{statement}\n\n海关监管风险：涉及{objects}，可能触及申报真实性、商品归类、价格、许可证、原产地或运输单证一致性；论坛内容本身不构成违法认定。\n\n后续核查：{checks}"
            item_id = f"forum-high-customs-risk-20260813-{key}"
            item = db.get(CollectedItem, item_id) or CollectedItem(id=item_id, source_id=SOURCE_ID)
            item.run_id, item.topic_id = RUN_ID, TOPIC_ID
            item.title, item.content, item.summary, item.url = title, content, statement, url
            item.language, item.category, item.status = "zh", "论坛高风险线索", "enriched"
            item.published_at = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            item.quality_score, item.relevance_score = 0.90, 0.95
            item.content_hash = hashlib.sha256(content.encode()).hexdigest()
            item.entities = {"objects": objects.split("；")}
            item.raw_metadata = {"evidence_type": "forum_post", "claim_status": "unverified", "review": "Codex post-level review", "customs_risk": "high"}
            db.add(item)
        topic.last_collection_run_id = RUN_ID
        topic.last_run_at = NOW
        db.commit()
        print({"run_id": RUN_ID, "items": len(LEADS)})
    finally:
        db.close()


if __name__ == "__main__":
    main()
