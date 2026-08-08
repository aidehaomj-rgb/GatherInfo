"""Data for the 2026-08-08 full-source forum-risk refresh."""

from __future__ import annotations

from china_entity_recollection_data_20260805 import LEADS as PRIOR_LEADS


TOPIC_ID = "foreign-trade-forum-risk-monitoring"
PROMPT_ID = "forum-social-customs-risk-search"
REPORT_ID = "report-forum-risk-full-source-refresh-20260808"
BATCH_ID = "codex-forum-risk-full-source-refresh-20260808"
REPORT_TITLE = "外贸论坛违规清关与走私风险线索全源复核与互联网补充报告（2026-08-08）"
DATE_RANGE_START = "2026-07-09"
DATE_RANGE_END = "2026-08-08"
OUTPUT_DIR = r"D:\codex\GatherInfo\GatherInfo\data\reports\2026-08-08"
OUTPUT_DOCX = OUTPUT_DIR + r"\外贸论坛违规清关与走私风险线索_全源复核与互联网补充报告_含时令生鲜专项_2026-08-08.docx"


NEW_SOURCES = [
    {
        "id": "web-linktrans-official",
        "name": "Linktrans 官方网站（主体核验源）",
        "description": "用于核对同名货代品牌的中国总部、公开业务范围和联系方式；不作为违规事实来源。",
        "base_url": "https://en.link-trans.com/",
        "homepage_url": "https://en.link-trans.com/",
        "keywords": ["Linktrans", "China headquarters", "Dongguan", "DDP", "customs declaration"],
        "languages": ["en", "zh-CN"],
    },
    {
        "id": "web-welisen-logistics",
        "name": "威立森国际物流公开业务文章",
        "description": "物流业务文章中出现低申报、改品名、集中申报等高风险模式词，纳入持续监测；本轮命中文章超出30天窗口，未作为当期条目。",
        "base_url": "https://www.welisen.com/",
        "homepage_url": "https://www.welisen.com/zh-CN/articles/special-cargo-transfer-guide-2026",
        "keywords": ["价值低申", "改品名", "集中申报", "仿牌专线", "特殊清关"],
        "languages": ["zh-CN"],
    },
    {
        "id": "web-zerrand-crossborder-runner",
        "name": "差遣跑腿 Zerrand 深港跨境服务",
        "description": "公开提供深圳至香港的专人跑腿、口岸交接和生鲜直送服务，适合监测时令水产、商业代带、多人拆分及重复往返等风险组合；单纯个人自用携带不作风险升级。",
        "base_url": "https://www.zerrand.com/",
        "homepage_url": "https://www.zerrand.com/pricing/shenzhen-hongkong-fresh-food-delivery/",
        "keywords": ["大闸蟹香港直送", "深港跑腿", "人肉手提", "每日往返罗湖口岸", "口岸交接", "中秋十一继续营业"],
        "languages": ["zh-CN", "zh-HK"],
    },
]


NEW_LEADS = [
    {
        "id": "codex-forum-risk-full-refresh-20260808-01",
        "source_id": "reddit-alibaba",
        "run_id": "codex-forum-risk-audit-20260808-reddit-alibaba",
        "title": "Reddit帖子称“Linktrans”货代询问是否降低申报货值以减少税费",
        "url": "https://www.reddit.com/r/Alibaba/comments/1v5g0z4/should_i_let_my_freight_forwarder_misrepresent/",
        "published_at": "2026-07-24T00:00:00+00:00",
        "risk_level": "一级（先锁定同名境内主体）",
        "quality_score": 0.93,
        "relevance_score": 0.98,
        "content_summary": (
            "发帖人自述：其货代“Linktrans”询问，是否可在所谓合理区间内降低申报货值，"
            "以减少约22.5%的税费。该内容是发帖人的单方陈述，评论区关于DDP、低报和进口责任的分析也只是意见，"
            "不能据此认定任何企业实施违法行为。独立核对的品牌官网披露其中国总部位于东莞，并提供中国至美国、加拿大、英国等线路；"
            "但公开页面不足以证明帖子中的同名货代就是该官网所指主体。"
        ),
        "china_entities": [
            "Linktrans品牌（官网披露中国总部位于东莞；与帖子所称同名货代是否同一主体待核）",
            "官网披露地址：广东省东莞市南城街道白马黄金一路3号（英文页面表述）",
            "可回溯平台标识：Alibaba货代账号、聊天记录、报价单、订单号、收款主体",
            "潜在线路标识：中国始发—美国/加拿大/英国等目的地；本帖具体口岸、提单和箱号未公开",
        ],
        "risk_signals": ["主动询问降低申报货值", "明确税费比例", "具体货代品牌", "可通过平台订单反查"],
        "risk_points": [
            "“降低申报货值+减少明确税费+具体货代品牌”构成较强估价风险组合，强于单独出现DDP或包税。",
            "帖子没有公开报价单、聊天截图、报关单或提单，且Linktrans存在同名或近似名称主体，当前只能形成身份核查线索。",
            "官网地址和线路仅用于主体消歧，不能反向证明官网主体与帖子所述行为有关。",
        ],
        "next_steps": [
            "向发帖平台或业务当事方调取原始聊天、报价、Alibaba账号、订单号、付款账户和服务合同，先确定实际签约与收款的中国法律主体。",
            "核对商业发票、付款金额、保险与运费、进口申报价值、税费计算、进口商和报关行，检查是否存在发票金额与申报金额不一致。",
            "取得运单、主分提单、柜号或快递单号后，串联中国出运仓、订舱代理、出口申报和境外进口申报；在主体未锁定前不作企业风险定性。",
        ],
        "missing_fields": "中国法律实体全称、统一社会信用代码、Alibaba账号、订单号、货物品名、起运口岸、运单/提单号、柜号、进口报关单和实际申报价值。",
        "source_note": "Reddit为用户生成内容，属于未经独立证实的单方陈述；Linktrans官网仅作同名品牌的公开主体核验来源。发布日期采用搜索索引显示日期。",
        "china_entity_gate": "conditional",
        "duplicate_group": "linktrans-undervaluation-allegation-20260724",
    },
    {
        "id": "codex-forum-risk-full-refresh-20260808-02",
        "source_id": "reddit-alibaba",
        "run_id": "codex-forum-risk-audit-20260808-reddit-alibaba",
        "title": "阿里巴巴订单自述出现钢制螺旋桩与“眼镜柜”提单货名不一致",
        "url": "https://www.reddit.com/r/Alibaba/comments/1v82wms/my_first_alibaba_order_steel_screw_piles_ddp_to/",
        "published_at": "2026-07-27T00:00:00+00:00",
        "risk_level": "一级（订单号可直接锁定中国卖家）",
        "quality_score": 0.97,
        "relevance_score": 0.99,
        "content_summary": (
            "发帖人复盘一笔中国始发、DDP运往欧盟的钢制螺旋桩订单，并公开Alibaba订单号290841751001029390。"
            "其称商业发票和装箱单记载钢制螺旋桩，但收到的提单涉及他人的“眼镜柜”，且文件中的商品编码描述存在差异；"
            "发帖人还称未取得MRN或进口申报资料。帖子评论对钢铁保障措施和CBAM的解释属于评论者推断，报告不将其作为事实。"
        ),
        "china_entities": [
            "Alibaba中国卖家（待通过订单号290841751001029390锁定店铺与营业执照主体）",
            "货物：中国始发钢制螺旋桩；目的地：欧盟；贸易条件：DDP",
            "单证差异：商业发票/装箱单为钢制螺旋桩，帖子称提单出现“眼镜柜”",
            "编码线索：帖子提及7308.90与7610.90的描述差异，须以原始报关与进口申报文件为准",
        ],
        "risk_signals": ["具体Alibaba订单号", "提单货名与实货不一致", "HS描述差异", "DDP且无MRN/进口申报资料"],
        "risk_points": [
            "该条同时具备平台订单号、具体货物、贸易方式和单证不一致描述，是本轮最接近可直接核查闭环的线索。",
            "提单可能是发帖人收到错误文件、拼箱资料混淆或其他操作失误，也可能涉及申报问题；未取得原始单证前不能判断原因。",
            "评论区关于规避保障措施或CBAM的说法不是发帖人提供的直接证据，不应写入企业事实认定。",
        ],
        "next_steps": [
            "以订单号向Alibaba调取卖家店铺、营业执照、收款账户、合同、聊天、物流服务商和Trade Assurance争议材料，锁定中国卖家及实际出口代理。",
            "逐票比对合同、付款、发票、装箱单、出口报关单、主分提单、舱单、柜号/封志号、实物照片以及欧盟MRN/SAD/EORI资料。",
            "核对申报品名、材质、用途、HS编码、数量、重量、货值和原产地；查明提单“眼镜柜”对应的真实货主、拼箱批次和订舱代理。",
        ],
        "missing_fields": "中国卖家名称、统一社会信用代码、出口报关单号、主分提单号、船名航次、柜号/封志号、欧盟入境口岸、MRN、进口商及报关行。",
        "source_note": "Reddit用户自述，订单号具备平台内核查价值；公开帖子未附可独立验证的全套单证，所有不一致描述均需调取原件复核。",
        "china_entity_gate": "passed_by_platform_order",
        "duplicate_group": "alibaba-order-290841751001029390",
    },
    {
        "id": "codex-forum-risk-full-refresh-20260808-03",
        "source_id": "reddit-alibaba",
        "run_id": "codex-forum-risk-audit-20260808-reddit-alibaba",
        "title": "宁波至多伦多货运询价帖出现“LCL更少被查验”营销话术",
        "url": "https://www.reddit.com/r/Alibaba/comments/1v0llpz/alibaba_forwarders_deception/",
        "published_at": "2026-07-19T00:00:00+00:00",
        "risk_level": "二级（先调取当前报价与承运主体）",
        "quality_score": 0.89,
        "relevance_score": 0.94,
        "content_summary": (
            "发帖人就45立方米、380箱、约7.5吨普通非危险干货，从中国宁波FOB运往加拿大多伦多询价，考虑40GP整柜。"
            "其称多家Alibaba货代推荐LCL，并使用“更便宜、更快、更不容易被加拿大边境服务署查验”等话术；"
            "当前推荐该话术的货代未被公开点名。帖子另提及过往合作方“SHENZHEN JW Logistics INTERNATIONAL”，"
            "但相关指称主要是上一次货物体积计费争议，不能与本次查验话术或海关违规直接绑定。"
        ),
        "china_entities": [
            "SHENZHEN JW Logistics INTERNATIONAL（帖子给出的英文名称；需核验准确中国工商主体，仅涉及过往计费争议）",
            "始发节点：宁波；目的地：加拿大多伦多；供应商条款：FOB Ningbo",
            "货物规模：45 CBM、380 cartons、约7,500 kg、普通非危险干货；拟用40GP FCL",
            "当前货代：多家Alibaba货代，帖子未公开名称；报价约14,000美元DDP且查验费用另计",
        ],
        "risk_signals": ["更少被查验的话术", "DDP与LCL组合", "具体中国始发口岸", "体积/箱数/重量/柜型/报价"],
        "risk_points": [
            "“更少被查验”与DDP、LCL、具体路线和货量同时出现，值得核对申报与拼箱责任链，但单凭营销话术不能证明存在伪瞒报。",
            "被点名的JW Logistics是上一票体积计费争议对象；本次推荐LCL并使用查验话术的服务商未公开，必须严格区分。",
            "同一内容同时发布于r/Alibaba和r/freightforwarding，已按同一帖子组去重，只保留一条系统记录。",
        ],
        "next_steps": [
            "调取本次所有Alibaba货代报价、账号、聊天和收款主体，识别是谁提出“更少查验”，并锁定实际订舱、报关和加拿大进口商。",
            "按45 CBM、380箱、7.5吨、宁波—多伦多、40GP等条件核对订舱资料、装箱仓、主分提单、舱单和柜号；区分LCL与FCL方案。",
            "比对商业发票、装箱单、出口申报、加拿大CARM/进口申报、关税税费和查验账单；如资料一致则保留为正常物流样本。",
            "对“SHENZHEN JW Logistics INTERNATIONAL”仅做主体和历史业务核验，不把体积争议推定为海关申报风险。",
        ],
        "missing_fields": "本次货代名称和账号、供应商名称、具体品名、订舱号、主分提单号、柜号、船名航次、加拿大进口商、报关行和申报价值。",
        "source_note": "Reddit用户自述；跨版帖子已去重。搜索索引显示发布日期为2026-07-19，页面相对时间显示存在差异，精确UTC时间仍需平台后台核准，但均落在本轮30天窗口内。",
        "china_entity_gate": "conditional",
        "duplicate_group": "ningbo-toronto-45cbm-380cartons-7500kg",
        "crosspost_url": "https://www.reddit.com/r/freightforwarding/comments/1v0ll8n/alibaba_shipping_service/",
    },
]


PRIOR_BY_ID = {lead["id"]: lead for lead in PRIOR_LEADS}
REPORT_LEADS = [
    NEW_LEADS[1],
    NEW_LEADS[0],
    PRIOR_BY_ID["codex-china-entity-recollect-20260805-01"],
    PRIOR_BY_ID["codex-china-entity-recollect-20260805-02"],
    PRIOR_BY_ID["codex-china-entity-recollect-20260805-04"],
    NEW_LEADS[2],
    PRIOR_BY_ID["codex-china-entity-recollect-20260805-03"],
]


SOURCE_CATALOG = [
    ("forum-fobshanghai", "福步外贸论坛", "https://www.fobshanghai.com/"),
    ("forum-jying-customs", "外贸精英论坛—报关员工作交流", "https://bbs.jying.cn/"),
    ("forum-citclub", "CIT Club 海关及贸易事务俱乐部", "https://www.citclub.org/"),
    ("forum-tradeach", "外贸跨境生态社群", "https://www.tradeach.com/club/"),
    ("forum-baidu-clearance", "百度贴吧—清关相关板块", "https://tieba.baidu.com/f?kw=%E6%B8%85%E5%85%B3"),
    ("forum-fob5", "环球外贸论坛 FOB5", "https://bbs.fob5.com/"),
    ("forum-9c9t", "九九外贸论坛", "https://bbs.9c9t.com/"),
    ("forum-alibaba-waimaoquan", "阿里外贸圈", "https://waimaoquan.alibaba.com/"),
    ("community-mikecrm-ask", "米课圈 / 米课外贸问答", "https://ask.mikecrm.com/"),
    ("community-wearesellers", "知无不言 WeAreSellers", "https://www.wearesellers.com/explore/"),
    ("forum-wholesaleforum", "Wholesale Forum", "https://www.wholesaleforum.com/"),
    ("forum-thewholesaleforums", "The Wholesale Forums（英国）", "https://www.thewholesaleforums.co.uk/"),
    ("social-linkedin-trade-groups", "LinkedIn 外贸行业群组", "https://www.linkedin.com/groups/"),
    ("forum-ichuanglan", "创蓝论坛", "https://bbs.ichuanglan.com/"),
    ("community-cifnews", "雨果论坛 / 雨果跨境社区", "https://www.cifnews.com/"),
    ("community-maijiazhijia", "卖家之家", "https://www.maijiazhijia.com/"),
    ("reddit-customsbroker", "Reddit - CustomsBroker", "https://www.reddit.com/r/CustomsBroker/"),
    ("reddit-freightforwarding", "Reddit - freightforwarding", "https://www.reddit.com/r/freightforwarding/"),
    ("reddit-alibaba", "Reddit - Alibaba", "https://www.reddit.com/r/Alibaba/"),
    ("reddit-internationaltrade", "Reddit - Internationaltrade", "https://www.reddit.com/r/Internationaltrade/"),
    ("reddit-business-in-china", "Reddit - Business_in_China", "https://www.reddit.com/r/Business_in_China/"),
    ("reddit-china", "Reddit - China", "https://www.reddit.com/r/China/"),
    ("reddit-logistics", "Reddit - logistics", "https://www.reddit.com/r/logistics/"),
    ("reddit-india-business", "Reddit - IndiaBusiness", "https://www.reddit.com/r/IndiaBusiness/"),
    ("vc-ru-marketplace", "VC.ru - Marketplace/Transport", "https://vc.ru/marketplace"),
    ("reddit-smallbusinessindia", "Reddit - smallbusinessindia", "https://www.reddit.com/r/smallbusinessindia/"),
    ("reddit-negociosargentina", "Reddit - NegociosArgentina", "https://www.reddit.com/r/NegociosArgentina/"),
    ("hangsunbang-logistics-community", "航隼帮货代网-物流交流圈", "https://www.hangsunbang.com/"),
    ("reddit-askargentina", "Reddit - AskArgentina", "https://www.reddit.com/r/AskArgentina/"),
    ("yict-vessel-schedule", "盐田国际集装箱码头船期服务", "https://www.yict.com.cn/service-vesselSchedule/vessel-schedule.html?locale=en_US"),
    ("zim-service-updates", "ZIM航线与服务更新", "https://www.zim.com/"),
    ("nvoccs-registry", "无船承运人备案信息服务", "https://www.nvoccs.cn/list/900.html"),
    ("web-hc23-transport-directory", "交通网库（荟萃网库）", "https://jt.hc23.com/"),
    ("web-bq-biquwang-marketplace", "必去网企业供求平台", "https://www.bq.cm/"),
    ("web-jinxiu-logistics", "锦秀物流公开业务信息", "https://dgjxhy.com/"),
    ("community-bokee-business-blog", "企博网职业博客", "https://www.bokee.net/"),
    ("web-linktrans-official", "Linktrans 官方网站（主体核验源）", "https://en.link-trans.com/"),
    ("web-welisen-logistics", "威立森国际物流公开业务文章", "https://www.welisen.com/"),
    ("web-zerrand-crossborder-runner", "差遣跑腿 Zerrand 深港跨境服务", "https://www.zerrand.com/pricing/shenzhen-hongkong-fresh-food-delivery/"),
]


AUDIT_DETAILS = {
    "reddit-alibaba": ("新增3条", "保留3组近30天线索，其中1组与货代板块跨版去重；分别涉及低报询问、提单货名差异和宁波—多伦多查验话术。"),
    "reddit-freightforwarding": ("跨版去重", "命中宁波—多伦多同源帖子，未重复入库。"),
    "web-hc23-transport-directory": ("复核既有/日期待核", "既有深圳汇升条目继续保留；另见宁波汇洋“特殊报关”页面，但原始发布日期无法核准，未纳入近30天条目。"),
    "web-bq-biquwang-marketplace": ("复核既有", "四川瀚瑞森CIQ监装、买单/包柜及品牌疑难杂货条目仍在窗口内。"),
    "web-jinxiu-logistics": ("复核既有", "东莞锦秀南沙—印尼线路条目仍在窗口内，因页面同时强调如实申报，维持二级核查。"),
    "community-bokee-business-blog": ("复核既有", "上海进口报关公司账号的手办买单清关/3C条目仍在窗口内，主体仍待反查。"),
    "yict-vessel-schedule": ("路线核验", "用于核对盐田港航线和船期，不单列风险条目。"),
    "zim-service-updates": ("路线核验", "ZEX船期可辅助核对盐田—洛杉矶航次，但不构成风险线索。"),
    "nvoccs-registry": ("主体核验", "用于核对无船承运人备案，不单列风险条目。"),
    "web-linktrans-official": ("新增主体核验源", "用于同名品牌中国总部与线路消歧，不能用于证明帖子指称。"),
    "web-welisen-logistics": ("新增监测源", "页面含低申报、改品名等高风险模式词；相关页面日期为2026-06-17，超出窗口，仅进入模式库。"),
    "web-zerrand-crossborder-runner": ("季节性专项监测", "服务页显示中秋、国庆期间继续营业，并提供大闸蟹等生鲜的专人跨境直送、口岸交接和罗湖往返；原始页面日期超窗，不作为近30天风险条目。"),
    "community-wearesellers": ("未保留", "发现近期匿名合规讨论，但缺少可核中国企业、口岸或运输标识。"),
    "forum-baidu-clearance": ("未保留", "搜索结果存在近期清关推广，但原帖时间、企业和业务字段无法可靠核准。"),
    "social-linkedin-trade-groups": ("未保留", "近期内容以普通DDP宣传和合规解读为主，未形成强风险组合。"),
    "hangsunbang-logistics-community": ("超窗排除", "直接风险表述的帖子早于2026-07-09。"),
    "reddit-negociosargentina": ("对象不符", "仅有境外个人或阿根廷本地核查对象，不符合中国可核实体要求。"),
    "reddit-askargentina": ("对象不符", "未形成中国企业、口岸或中国运输标识闭环。"),
    "reddit-smallbusinessindia": ("对象不符", "未形成中国可核实体和直接单证标识组合。"),
    "reddit-india-business": ("对象不符", "未形成中国可核实体和直接单证标识组合。"),
}


SOURCE_AUDIT = []
for source_id, name, url in SOURCE_CATALOG:
    status, note = AUDIT_DETAILS.get(
        source_id,
        ("未发现合格条目", "未发现同时满足近30天、中国可核实体和强海关风险信号组合的公开内容。"),
    )
    SOURCE_AUDIT.append({"id": source_id, "name": name, "url": url, "status": status, "note": note})


PROMPT_APPENDIX = r"""

[2026-08-08 全源复核与互联网补充规则]
一、时间硬门槛：仅把原帖首次发布时间落在最近30天内的内容作为当期条目。搜索引擎抓取时间、页面更新时间或目录刷新时间不得替代原帖时间；只能确认在窗口内但无法取得精确UTC时间时，必须标记“时间待平台核准”。
二、中国核查对象硬门槛：优先保留中国企业全称、统一社会信用代码、平台订单号/店铺号、境内收付款主体、中国口岸/仓库/货源地、主分提单、订舱号、船名航次、柜号/封志号等至少一项可回溯标识。只有境外个人姓名的内容不入本主题。
三、强风险组合：单独出现DDP、包税、双清、LCL或第三国转运不升级。优先识别“降低申报货值/低申报+明确税费”“提单货名与实货不一致”“HS描述差异+无进口申报资料”“更少被查验+具体路线货量+私聊/报价”等组合。
四、英文与多语种扩展词：declare a lower cargo value、reasonable range、less likely to be inspected、bill of lading for different goods、no customs clearance documents for DDP、order number、wrong HS description、under-declare、undervalued invoice；中文补充价值低申、集中申报、仿牌专线、名牌包改PU女包。
五、证据分层：原帖作者陈述、评论区推断、企业官网自述、第三方目录信息必须分开写；评论对保障措施、CBAM、关税或走私动机的解释不得改写成企业事实。官网只用于主体和线路消歧。
六、同名主体消歧：品牌名、英文简称或近似公司名不能直接绑定中国法律实体。必须以平台账号、营业执照、订单、合同、收款账户、报价单或运单至少一项交叉确认。
七、跨版去重：同一作者、同一货量、同一路线和相同文本在不同论坛/版块重复发布时，只保留一条主记录，并保存crosspost URL。
八、超窗内容利用：超出30天但含直接风险模式词的页面不进入当期报告，可纳入信息源和模式词库，为后续近月监测提供检索规则。
九、输出结构：每条必须包含原帖链接、发布时间及可信度、内容摘要、中国可核实体/标识、风险点、证据边界、下一步核查建议和当前缺失字段；不得把待核线索表述为违法事实。
"""


NEW_KEYWORDS = [
    "declare a lower cargo value",
    "reasonable range",
    "less likely to be inspected",
    "bill of lading for different goods",
    "no customs clearance documents for DDP",
    "Alibaba order number",
    "价值低申",
    "集中申报",
    "仿牌专线",
    "名牌包改PU女包",
    "大闸蟹香港直送",
    "中秋十一继续营业",
    "深港生鲜跑腿",
    "人肉跨境手提",
    "每日往返罗湖口岸",
    "口岸交接",
    "地铁沿线交收",
    "蚂蚁搬家式代带",
    "多人拆分携带",
    "商业用途伪装自用",
    "大闸蟹卫生证明书",
    "大闸蟹售卖许可证",
]


SEASONAL_ALERT = {
    "title": "中秋、国庆前深港大闸蟹及生鲜“人肉直送”季节性风险预警",
    "service_url": "https://www.zerrand.com/pricing/shenzhen-hongkong-fresh-food-delivery/",
    "case_url": "https://www.zerrand.com/sz-hk-hairy-crab-fresh-delivery/",
    "customs_faq_url": "https://www.customs.gov.hk/tc/service-enforcement-information/passenger-clearance/faqs/index.html",
    "cfs_url": "https://www.cfs.gov.hk/english/press/20251114_11966.html",
    "direct_supply_url": "https://hk.mofcom.gov.cn/jmxx/art/2025/art_518e69fa80744977bab8c586be9d3426.html",
    "summary": (
        "Zerrand公开服务页当前显示“中秋十一超长连假继续营业”，并提供深圳至香港的大闸蟹、海鲜、水果等生鲜的专人点对点配送，"
        "页面列出罗湖口岸日常往返、东铁线地铁站交收、口岸交接、订单数量和业务微信等字段。其2025年11月案例页还描述了从深圳罗湖口岸附近取大闸蟹送往香港红磡，"
        "使用人工看护并以减少海关疑问为卖点。两页原始日期均早于本轮30天窗口，且页面同时声称会提供合规携带建议，因此不作为当期走私条目，"
        "但可作为中秋、国庆前商业代带和“蚂蚁搬家”风险的预警样本。"
    ),
    "entities": [
        "平台/品牌：Zerrand（差遣跑腿）；尚未从公开页面锁定唯一中国工商主体",
        "业务联系方式：微信 d17810000；邮箱 contact@zerrand.com；页面电话仅显示为+86 137****7410",
        "境内节点：深圳、罗湖口岸附近、金光华广场；跨境节点：罗湖口岸",
        "香港节点：东铁线地铁站交收、红磡及上门配送",
        "公开跑腿账号：楽呦呦跑腿、港深达商务服务、汐汐深港跑腿、悟空深港跑腿（均需平台后台核实名义主体）",
    ],
    "risk_signals": [
        "中秋、国庆假期持续接单与季节性大闸蟹需求叠加",
        "收费的采购+跨境配送、专人手提、口岸交接和每日往返",
        "历史案例页出现减少海关疑问的营销话术",
        "同一平台存在多个跑腿账号、订单计数和地铁站交收节点",
    ],
    "boundary": [
        "香港海关现行公开问答明确，旅客在私人行李中携带合理数量的海产（包括大闸蟹）供个人自用，一般不受限制；不能因携带大闸蟹或使用保温箱就认定走私。",
        "风险升级应建立在商业收费、代购代送、重复往返、多人拆分、实际用于销售、隐瞒或虚报用途、缺少来源/卫生文件等组合事实之上。",
        "内地大闸蟹已于2025年恢复直接供港；大陆来源或内地直运本身不是异常，合法批次应以卫生证明、进口商和销售许可作为排除样本。",
        "公开页面没有披露具体单票数量、旅客身份或明确夹藏行为，本节是季节性预警，不是对平台或跑腿员违法行为的认定。",
    ],
    "next_steps": [
        "在中秋、国庆前60天至节后两周，对Zerrand及相同业务模式页面按账号、微信、订单数量、取货点、交收站、服务费和商品清单持续留存快照。",
        "如依法取得平台订单，按同一联系方式、付款账户、跑腿账号和出入境记录聚类，识别商业收费、多人拆分或短期高频往返，而不是针对普通个人自用旅客。",
        "围绕罗湖口岸及东铁线交收节点，核对取货商户、实际数量、包装标签、最终收货人和是否进入餐饮/零售渠道；个人合理自用应从商业风险样本中排除。",
        "对拟销售的大闸蟹核验进口商登记、出口地卫生证明、香港食环署相关许可或书面准许、进货与销售记录；与2025年恢复的合规内地直供批次作对照。",
    ],
    "missing_fields": "平台经营主体和ICP备案、跑腿账号实名、节日期间具体订单、每票数量、收费与付款账户、实际过境口岸和时间、最终收货用途、卫生证明及销售许可。",
}


SEASONAL_PROMPT_APPENDIX = r"""

[2026-08-08 中秋国庆时令生鲜夹藏与商业代带专项规则]
一、提前量：每年中秋、国庆前60天至节后两周，对大闸蟹、活体水产、冻品、肉类、月饼及礼盒等时令商品增加监测频次。
二、不得误判：旅客私人行李中合理数量、个人自用的海产（包括大闸蟹）一般不因商品本身升级；保温箱、冰袋、口岸自提和个人携带也不是独立风险证据。
三、商业风险组合：优先识别“收费代购/代送+每日或高频往返+多人账号/拆分携带+口岸或地铁站交收+商户/餐厅收货”，以及“减少海关疑问/无需申报/包过关/不问品名”等规避型话术。
四、夹藏证据门槛：必须出现隐藏于其他货物、伪装包装、虚报自用、拆分批次、重复过关、未申报商业用途或缺少卫生/检疫/销售文件等至少一项直接信息，才标记为夹藏或走私风险；不得从“人肉跑腿”直接推定。
五、实体字段：提取平台或公司、跑腿账号、微信/电话、取货商户、境内仓库/商场、深圳口岸、香港交收站、餐厅/零售收货人、订单数、费用、数量、包装、付款账户和出入境时间。
六、合规对照：核验进口商登记、出口地卫生证明、香港食环署相关许可或书面准许、进货销售记录；内地大闸蟹已恢复直接供港，不得把大陆来源或直运本身视为异常。
七、输出：将当期直接帖子与超窗模式样本分栏；超窗样本只进入季节性预警和提示词库，不计入近30天风险条目。
"""


def build_markdown() -> str:
    lines = [
        f"# {REPORT_TITLE}",
        "",
        f"- 采集窗口：{DATE_RANGE_START} 至 {DATE_RANGE_END}",
        f"- 检索范围：{len(SOURCE_AUDIT)}个已配置/新增信息源，并进行一次开放互联网补充检索",
        "- 口径：排除执法案例；仅保留近30天、中国可核对象、强风险组合；公开帖子只作待核线索",
        "",
        "## 本轮结论",
        "",
        "本轮新增并入库3组线索，复核保留既有4组近月线索，共形成7组当前核查清单。新增线索中，Alibaba订单号290841751001029390可直接向平台锁定中国卖家，证据闭环价值最高；Linktrans低报询问帖需先消歧同名主体；宁波—多伦多帖子需先取得当前货代报价和账号。",
        "",
        "## 当前7组核查条目",
        "",
    ]
    for index, lead in enumerate(REPORT_LEADS, 1):
        lines.extend([
            f"### {index}. {lead['title']}",
            "",
            f"- 原帖：[{lead['url']}]({lead['url']})",
            f"- 发布时间：{lead['published_at'][:10]}",
            f"- 核查等级：{lead['risk_level']}",
            f"- 主要内容：{lead['content_summary']}",
            f"- 中国实体/标识：{'；'.join(lead['china_entities'])}",
            f"- 风险点：{'；'.join(lead['risk_points'])}",
            f"- 下一步：{'；'.join(lead['next_steps'])}",
            f"- 缺失字段：{lead['missing_fields']}",
            f"- 证据边界：{lead['source_note']}",
            "",
        ])
        if lead.get("crosspost_url"):
            lines.insert(-1, f"- 跨版链接：[{lead['crosspost_url']}]({lead['crosspost_url']})（已去重）")
    lines.extend([
        "## 中秋、国庆时令生鲜夹藏与商业代带专项预警",
        "",
        f"### {SEASONAL_ALERT['title']}",
        "",
        f"- 当前服务页：[{SEASONAL_ALERT['service_url']}]({SEASONAL_ALERT['service_url']})",
        f"- 历史案例页：[{SEASONAL_ALERT['case_url']}]({SEASONAL_ALERT['case_url']})",
        f"- 主要内容：{SEASONAL_ALERT['summary']}",
        f"- 中国实体/节点：{'；'.join(SEASONAL_ALERT['entities'])}",
        f"- 风险信号：{'；'.join(SEASONAL_ALERT['risk_signals'])}",
        f"- 证据边界：{'；'.join(SEASONAL_ALERT['boundary'])}",
        f"- 下一步核查：{'；'.join(SEASONAL_ALERT['next_steps'])}",
        f"- 缺失字段：{SEASONAL_ALERT['missing_fields']}",
        "- 官方合规口径：[香港海关旅客携带食物问答](https://www.customs.gov.hk/tc/service-enforcement-information/passenger-clearance/faqs/index.html)；[香港食安中心大闸蟹销售与卫生证明要求](https://www.cfs.gov.hk/english/press/20251114_11966.html)；[内地大闸蟹恢复直接供港](https://hk.mofcom.gov.cn/jmxx/art/2025/art_518e69fa80744977bab8c586be9d3426.html)",
        "",
        "本轮未发现发布时间在近30天内、且公开给出明确夹藏方法、具体数量和中国经营主体的合格帖子，因此未新增当期风险条目。本节作为节前预警和后续采集规则，不与7组当前核查条目混计。",
        "",
        "## 信息源复核台账",
        "",
    ])
    for audit in SOURCE_AUDIT:
        lines.append(f"- [{audit['name']}]({audit['url']})｜{audit['status']}｜{audit['note']}")
    lines.extend([
        "",
        "## 重要限制",
        "",
        "帖子、评论、企业官网和目录页均可能存在误述、营销、转载、同名主体或时间刷新。报告用于确定调取单证和主体核验的优先级，不构成对任何企业或个人违法违规的认定。",
    ])
    return "\n".join(lines)
