"""Rebuild the forum topic as a rolling 31-day port-risk collection.

Only original posts published from 2026-07-05 through 2026-08-05 are kept.
Forum statements are unverified leads and never a finding that an entity has
committed smuggling or another customs offence.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal, _db_file_path
from app.models import CollectionRun, CollectedItem, Report, SourceConfig, Topic


TOPIC_ID = "foreign-trade-forum-risk-monitoring"
FOB_SOURCE_ID = "forum-fobshanghai"
REPORT_ID = "report-forum-risk-20260805044348"
RUN_ID = "codex-forum-port-risk-30d-20260805-fob"
CHINA_TZ = timezone(timedelta(hours=8))
WINDOW_START = datetime(2026, 7, 5, 0, 0, tzinfo=CHINA_TZ)
WINDOW_END = datetime(2026, 8, 5, 23, 59, 59, tzinfo=CHINA_TZ)


def dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=CHINA_TZ)


def structured(main: str, risks: list[str], checks: list[str]) -> str:
    risk_lines = "\n".join(f"- {value}" for value in risks)
    check_lines = "\n".join(f"- {value}" for value in checks)
    return f"## 主要内容\n\n{main}\n\n## 涉及风险点\n\n{risk_lines}\n\n## 后续排查方向\n\n{check_lines}"


ITEMS = [
    {
        "id": "codex-forum-port30d-20260805-01",
        "url": "https://bbs.fobshanghai.com/thread-9334648-1-1.html",
        "published_at": dt("2026-08-05 00:00"),
        "title": "南沙敏感货买单报关并承接南沙—香港整柜服务",
        "main": (
            "帖子自称南沙本土报关行，公开承接南沙敏感货买单报关及南沙—香港整柜敏感货，"
            "并宣称可覆盖申报、查验、拖车、仓库和全程跟踪。帖子没有披露具体货物、企业全称、箱号或报关单号。"
        ),
        "risks": [
            "“敏感货 + 买单报关 + 南沙—香港整柜”组合，存在真实货主、出口经营单位与报关抬头分离风险。",
            "同时掌握申报、查验、拖车和仓库环节，若单证审核不足，可能形成货物流与申报信息脱节。",
            "敏感货品名、数量、价格、许可证或检验检疫条件可能被简化、漏报或错报。",
        ],
        "checks": [
            "围绕南沙—香港整柜，筛查买单抬头高频但无稳定生产经营记录的出口主体。",
            "串联舱单、装箱单、仓库入库、装柜记录、过磅、查验和放行信息，核对真实货主及货物。",
            "对敏感货复核HS编码、申报要素、许可证、商检/危包资料及实际货值。",
        ],
        "entities": {
            "口岸": ["南沙口岸", "香港"],
            "运输方式": ["整柜", "拖车"],
            "业务模式": ["敏感货买单报关"],
            "环节": ["申报", "查验", "拖车", "仓库"],
        },
        "risk_level": "critical_lead",
        "score": 99.0,
    },
    {
        "id": "codex-forum-port30d-20260805-02",
        "url": "https://bbs.fobshanghai.com/thread-9334335-1-1.html",
        "published_at": dt("2026-08-04 10:23"),
        "title": "美国电子烟专线同时承接买单报关、双清包税及韩国中转",
        "main": (
            "以“汇智通国际货运”名义发布的广告承接电子烟、烟弹、烟油和配件，支持正式报关或买单报关、"
            "美国双清包税、拼箱或整柜。帖子列出ZIM盐田—洛杉矶直航，以及深圳—威海—仁川—釜山—洛杉矶"
            "韩国中转路线，并承诺美国海关扣关时按申报货值赔付。海运500千克起、空运1000千克起。"
        ),
        "risks": [
            "电子烟、烟油、电池等受运输安全、知识产权、消费品和目的国准入多重监管。",
            "“买单报关 + 双清包税 + 第三地中转 + 扣关赔付”组合可能弱化真实出口人、进口人和税费责任。",
            "直航仅接正式报关、韩国中转可接买单报关的差异值得关注，可能体现渠道风险分层。",
        ],
        "checks": [
            "按盐田—洛杉矶及深圳—威海—仁川—釜山—洛杉矶路线筛查电子烟相关订舱和舱单。",
            "核对ZIM航次、拼整箱信息、实际重量、品名、品牌、烟油成分、电池资料与申报记录。",
            "核验出口抬头、境外IOR/收货人、税费凭证及美国准入文件，关注同一抬头高频分散申报。",
        ],
        "entities": {
            "企业或商号": ["汇智通国际货运（帖子自称）"],
            "口岸": ["盐田港", "洛杉矶", "威海", "仁川", "釜山", "芝加哥"],
            "船公司": ["ZIM"],
            "货物": ["电子烟", "烟弹", "烟油", "电子烟配件"],
            "运输方式": ["拼箱", "整柜", "空运", "韩国中转"],
            "业务模式": ["买单报关", "美国双清包税", "扣关赔付"],
        },
        "risk_level": "critical_lead",
        "score": 100.0,
    },
    {
        "id": "codex-forum-port30d-20260805-03",
        "url": "https://bbs.fobshanghai.com/thread-9334323-1-1.html",
        "published_at": dt("2026-08-04 10:01"),
        "title": "南沙拖车报关广告公开承接食品、化妆品及仿牌货物",
        "main": (
            "帖子以南沙拖车报关公司名义揽货，标题公开宣称专做食品、化妆品和“仿牌类”，"
            "正文仅留下业务联系信息，没有说明品牌授权、食品化妆品资质或具体申报方式。联系方式未入库。"
        ),
        "risks": [
            "“仿牌类”直接涉及海关知识产权保护和侵权货物进出口风险。",
            "食品、化妆品与仿牌货混合揽收，存在准入证明、标签、成分、数量或品牌申报不实风险。",
            "南沙拖车与报关一体化操作可能使装货、运输和申报由同一链条控制。",
        ],
        "checks": [
            "筛查南沙近期食品、化妆品及品牌服饰等高风险品类的知识产权布控与查验记录。",
            "核对品牌授权、商标备案、生产企业、成分标签、检验检疫和进口/出口许可证。",
            "倒查拖车、仓库、报关抬头和收付款主体，识别同一链条反复代理不同真实货主的情况。",
        ],
        "entities": {
            "口岸": ["南沙口岸"],
            "货物": ["食品", "化妆品", "仿牌货物"],
            "业务环节": ["拖车", "报关"],
            "风险类型": ["知识产权侵权", "准入及申报真实性"],
        },
        "risk_level": "critical_lead",
        "score": 99.0,
    },
    {
        "id": "codex-forum-port30d-20260805-04",
        "url": "https://bbs.fobshanghai.com/thread-9334316-1-1.html",
        "published_at": dt("2026-08-04 09:53"),
        "title": "生物菌粉剂经中国多口岸或陆路出口越南并承诺双清包税",
        "main": (
            "“递接物流”广告承接生物菌粉剂至越南陆运或海运，提供双清包税到门，并称单一品名可当天放行。"
            "帖子列举广州、深圳、厦门、上海、青岛、天津、宁波等出运口岸，目的地为河内、胡志明市，"
            "同时覆盖报关报检、仓储、整柜和散货。"
        ),
        "risks": [
            "菌粉属于粉末状及可能具有生物属性的货物，品名、菌种/成分、用途和检疫条件需要重点核实。",
            "“双清包税 + 单一品名当天放行”容易掩盖真实进口人、税费承担人及具体申报要素。",
            "多口岸、陆海运并行可能导致同类货物在不同口岸选择性申报。",
        ],
        "checks": [
            "核验菌种或成分、用途、生产企业、HS编码、MSDS/检测报告、检疫和目的国准入文件。",
            "比对陆路口岸及所列海港的申报品名、重量、包装、收发货人和税费记录。",
            "关注以笼统“菌粉/添加剂/样品”等名称申报或将多种成分合并为单一品名的情况。",
        ],
        "entities": {
            "企业或商号": ["递接物流（帖子自称）"],
            "口岸": ["广州", "深圳", "厦门", "上海", "青岛", "天津", "宁波", "河内", "胡志明市"],
            "货物": ["生物菌粉剂"],
            "运输方式": ["陆运", "海运", "整柜", "散货"],
            "业务模式": ["双清包税到门", "单一品名当天放行"],
        },
        "risk_level": "high_lead",
        "score": 96.0,
    },
    {
        "id": "codex-forum-port30d-20260805-05",
        "url": "https://bbs.fobshanghai.com/thread-9333683-1-1.html",
        "published_at": dt("2026-07-31 13:20"),
        "title": "南沙蛇口近期查验与审价收紧，帖子称买单及敏感品仍可接单",
        "main": (
            "报关从业者称近期南沙查验排队、审价和归类核查收紧，散货拼箱、品名笼统、单价偏离市场区间的货物"
            "更容易被抽查；同时表示正规单证和买单均可接单，并提示新旧设备、二手零部件及敏感品不要简化申报。"
        ),
        "risks": [
            "帖子直接给出南沙近期高风险画像：拼箱、笼统品名、异常单价、新旧设备和二手零部件。",
            "同一批合格品与瑕疵品可能出现品名、质量状态或价格拆分不准确。",
            "在查验收紧背景下仍公开承接买单和敏感品业务，需关注报关抬头及真实货主不一致。",
        ],
        "checks": [
            "按南沙、蛇口近月拼箱申报筛选笼统品名、异常单价和同柜多货主组合。",
            "对合格品/瑕疵品、新设备/旧设备核对质检记录、生产台账、序列号和成交价格。",
            "关联查验通知、码头排队回执、改单记录、超堆/柜租及买单抬头历史申报。",
        ],
        "entities": {
            "口岸": ["南沙口岸", "蛇口口岸"],
            "货物": ["散货拼箱", "合格品", "瑕疵品", "新旧设备", "二手零部件", "敏感品"],
            "风险方式": ["品名笼统", "价格偏离", "买单报关", "简化申报"],
        },
        "risk_level": "high_lead",
        "score": 98.0,
    },
    {
        "id": "codex-forum-port30d-20260805-06",
        "url": "https://bbs.fobshanghai.com/thread-9332061-1-1.html",
        "published_at": dt("2026-07-24 00:00"),
        "title": "南沙黄埔二手汽车发动机出口面临废物属性及残油查验风险",
        "main": (
            "帖子称南沙、黄埔口岸二手拆车发动机出货增加，查验重点包括机油和冷却液是否排空、外壳油污、"
            "型号与序列号是否如实申报，以及机件是否仍具使用功能；报废机件可能被认定为固体废物并暂扣。"
        ),
        "risks": [
            "可利用旧机件与报废固废界限模糊，存在将废旧物资申报为可用零部件的风险。",
            "残留机油、冷却液可能涉及危险性、环境及运输安全问题。",
            "型号、序列号、品牌、数量和新旧状态若与实物不符，易形成伪报瞒报。",
        ],
        "checks": [
            "对南沙、黄埔二手发动机申报核验序列号、可使用性检测、来源拆解记录和成交价格。",
            "查验残油残液、外观和包装，必要时开展固废属性及危险特性鉴别。",
            "比对报关单、装箱单、照片、装柜视频、过磅和目的国进口要求。",
        ],
        "entities": {
            "口岸": ["南沙口岸", "黄埔口岸"],
            "货物": ["二手拆车发动机"],
            "实物标识": ["型号", "序列号"],
            "风险类型": ["固体废物属性", "残油残液", "新旧状态及品名不实"],
        },
        "risk_level": "high_lead",
        "score": 98.0,
    },
    {
        "id": "codex-forum-port30d-20260805-07",
        "url": "https://bbs.fobshanghai.com/thread-9330367-1-1.html",
        "published_at": dt("2026-07-18 00:00"),
        "title": "电池实际18.5V/2600mAh，客户要求虚标24V/4A并询问海关查验",
        "main": (
            "发帖人说明电池包由3.7V电芯五串二并组成，实际为18.5V、2600mAh，UN38.3证书亦显示该参数；"
            "客户要求产品虚标为24V、4A，发帖人直接询问遇海关查验如何处理。"
        ),
        "risks": [
            "帖子明确出现“虚标”要求，实物标签、UN38.3证书与申报资料可能不一致。",
            "电池属于运输安全重点货物，电压、容量、能量及包装参数关系危险品分类和承运条件。",
            "客户指示改变参数可能沿订单、标签、发票、装箱单和报关资料多环节传导。",
        ],
        "checks": [
            "核对电芯组合、额定电压/容量/瓦时、UN38.3、MSDS、鉴定报告和外包装标签。",
            "比对订单、客户邮件、生产记录、商业发票、装箱单、托运书及报关申报要素。",
            "关注华东口岸同型号电池以24V/4A申报但证书显示18.5V/2600mAh的记录。",
        ],
        "entities": {
            "区域": ["华东口岸（帖子标签，未给出具体口岸）"],
            "货物": ["锂电池包"],
            "实际参数": ["18.5V", "2600mAh"],
            "拟虚标参数": ["24V", "4A"],
            "文件": ["UN38.3证书"],
        },
        "risk_level": "critical_lead",
        "score": 100.0,
    },
    {
        "id": "codex-forum-port30d-20260805-08",
        "url": "https://bbs.fobshanghai.com/thread-9328982-1-1.html",
        "published_at": dt("2026-07-13 00:00"),
        "title": "青岛买单报关杂货中明确包含食品和有品牌服装",
        "main": (
            "帖子寻找可在青岛操作买单报关的同行，称货物为大量普货杂货，并补充其中含食品和有品牌的衣服。"
            "正文未披露品牌、食品种类、数量、货值、箱号或真实货主；联系方式未入库。"
        ),
        "risks": [
            "“买单报关 + 杂货混装 + 食品 + 品牌服装”同时出现，具有较直接的夹藏、混报和知识产权风险。",
            "笼统使用“普货杂货”可能掩盖食品检疫、品牌授权及不同税号货物。",
            "真实货主、生产商与出口抬头可能分离，责任链不清。",
        ],
        "checks": [
            "筛查青岛口岸杂货/普货拼箱中同时出现食品和服装实物的查验及机检异常。",
            "核对装柜清单、仓库分票、品牌授权、食品生产与检疫资质、HS编码和数量。",
            "关联买单抬头、实际交货人、付款主体、货代和境外收货人，识别多货主拼装。",
        ],
        "entities": {
            "口岸": ["青岛口岸"],
            "货物": ["普货杂货", "食品", "有品牌服装"],
            "业务模式": ["买单报关"],
            "风险类型": ["夹藏混报", "知识产权", "食品检疫"],
        },
        "risk_level": "critical_lead",
        "score": 100.0,
    },
    {
        "id": "codex-forum-port30d-20260805-09",
        "url": "https://bbs.fobshanghai.com/thread-9328433-1-1.html",
        "published_at": dt("2026-07-10 00:00"),
        "title": "出口报关数量遗漏导致金额相差近15%，船已开后询问是否不改单",
        "main": (
            "发帖人称出口报关时漏报数量，导致申报金额与实际相差接近15%；货物不退税且船舶已经开走。"
            "发帖人询问是否主动披露、能否不修改报关单，以及非优惠原产地证发票金额应按报关金额还是客户发票金额填写。"
        ),
        "risks": [
            "货物数量和金额已出现明确差额，构成报关单、商业发票及原产地证之间的不一致风险。",
            "“不改报关单”会使漏报状态延续，影响统计、收汇、原产地和目的国清关。",
            "船已开走后再发现问题，需要关注是否及时改单或主动披露。",
        ],
        "checks": [
            "比对报关单、舱单、提单、装箱单、商业发票、过磅和原产地证。",
            "核实漏报具体品项、数量、金额、原因及是否已申请改单或主动披露。",
            "沿同一企业历史申报检查数量/金额差异是否重复发生，区分偶发错误与系统性少报。",
        ],
        "entities": {
            "运输状态": ["船舶已开航"],
            "差异": ["数量遗漏", "金额相差接近15%"],
            "文件": ["报关单", "商业发票", "非优惠原产地证"],
        },
        "risk_level": "high_lead",
        "score": 98.0,
    },
    {
        "id": "codex-forum-port30d-20260805-10",
        "url": "https://bbs.fobshanghai.com/thread-9327867-1-1.html",
        "published_at": dt("2026-07-08 00:00"),
        "title": "上海出口寻求买单报关并同时要求办理原产地证",
        "main": (
            "帖子公开寻求上海出口买单报关，并提出需要办理原产地证。正文没有披露货物、生产企业、"
            "实际出口人、目的国、金额或运输标识符。"
        ),
        "risks": [
            "买单抬头与真实生产/出口主体可能不一致。",
            "在第三方报关抬头基础上同步办理原产地证，存在生产商、出口商和原产资格信息错配风险。",
            "若货物或目的国涉及贸易救济，原产地文件不实会放大追溯和处罚风险。",
        ],
        "checks": [
            "核查上海口岸相关出口抬头、真实生产商、购销合同、资金流和委托报关关系。",
            "比对原产地证申请、商业发票、提单、报关单和生产资料中的企业及货物信息。",
            "关注同一代理或抬头短期内为多家无关联货主申请原产地证的情况。",
        ],
        "entities": {
            "口岸": ["上海口岸"],
            "业务模式": ["买单报关"],
            "文件": ["原产地证"],
        },
        "risk_level": "high_lead",
        "score": 96.0,
    },
    {
        "id": "codex-forum-risk-20260805044348-02",
        "url": "https://bbs.fobshanghai.com/thread-9327008-1-1.html",
        "published_at": dt("2026-07-06 09:58"),
        "title": "马来西亚换柜转口铝材至意大利并被追溯反倾销风险",
        "main": (
            "7月6日发布的复盘帖称，佛山铝材2×40HQ由蛇口经阳明海运抵达巴生西港，在马来西亚保税仓换柜，"
            "以马来西亚名义报关并使用当地原产地文件出口意大利。帖子称后续同类业务被意大利海关调查，"
            "客户被追补反倾销税并处罚14万欧元；金额和处罚过程未获官方文书独立验证。"
        ),
        "risks": [
            "第三国仅换柜和短暂停留，未见实质性加工，存在原产地伪报和规避反倾销措施风险。",
            "以转口国名义报关并出具当地文件，可能与真实生产地、生产能力和货物流不一致。",
            "路线、船公司、箱型箱量及保税仓环节具体，具备进一步串联物流轨迹的条件。",
        ],
        "checks": [
            "串联蛇口装柜、YML航次、2×40HQ、巴生西港提箱/换柜及赴意大利的二程提单。",
            "核验马来西亚原产地证签发依据、当地企业生产能力、加工增值、能耗和人员记录。",
            "调取意大利进口申报、反倾销税追补及处罚文书，确认帖子所述金额和责任主体。",
        ],
        "entities": {
            "口岸": ["蛇口码头", "巴生港西港", "意大利目的港"],
            "船公司": ["阳明海运（YML）"],
            "货物": ["佛山铝材", "2×40HQ"],
            "风险方式": ["第三国换柜", "转口国名义报关", "马来西亚原产地文件", "规避反倾销风险"],
            "金额": ["14万欧元处罚（论坛自述，待核）"],
        },
        "risk_level": "critical_lead",
        "score": 100.0,
    },
]


ORDERED_IDS = [item["id"] for item in ITEMS]


def build_report() -> str:
    lines = [
        "# 外贸论坛近一个月口岸走私、伪瞒报与夹藏风险报告",
        "",
        "**时间窗：** 2026-07-05—2026-08-05（按原帖发布时间）  ",
        "**采集方式：** Codex直接读取论坛公开页面，未调用项目内百度搜索API或Tavily。  ",
        "**判断边界：** 以下均为公开论坛帖子及广告形成的待核线索，不代表相关账号、商号或企业已经实施走私或其他违法行为。",
        "",
        "## 一、总体判断",
        "",
        "本期保留11条原帖。高风险组合主要集中在：敏感货与买单报关；电子烟与双清包税、韩国中转及扣关赔付；"
        "杂货拼装中夹有食品和品牌服装；南沙承接仿牌、食品和化妆品；危险品参数虚标；二手发动机的新旧/固废属性；"
        "第三国换柜并使用转口国原产地文件。未发现帖子公开完整集装箱号，但已出现2×40HQ、具体船公司、口岸和多段路线。",
        "",
        "## 二、逐帖研判",
        "",
    ]
    for index, item in enumerate(ITEMS, 1):
        lines.extend(
            [
                f"### {index}. {item['title']}",
                "",
                f"**发布日期：** {item['published_at'].astimezone(CHINA_TZ).strftime('%Y-%m-%d')}  ",
                f"**原帖：** [{item['url']}]({item['url']})  ",
                f"**风险级别：** {item['risk_level']}",
                "",
                item["content"],
                "",
            ]
        )
    lines.extend(
        [
            "## 三、共性排查建议",
            "",
            "1. 以口岸、发布日期、品类和业务模式为入口，优先筛选南沙、蛇口、盐田、黄埔、青岛、上海的买单及敏感货申报。",
            "2. 串联报关单、舱单、提单、仓库入库、装柜视频、过磅、查验、改单、原产地证和资金流。",
            "3. 对电子烟、电池、菌粉、食品、化妆品、二手发动机和品牌货分别核验准入、安全、检疫、固废及知识产权条件。",
            "4. 对第三国中转关注原箱/换箱、两程提单、保税仓作业和实质性加工；对买单关注真实货主与报关抬头关系。",
            "5. 只有申报、物流、实物、资金或官方文书相互印证后，才将论坛线索升级为确定性风险结论。",
        ]
    )
    return "\n".join(lines)


for item in ITEMS:
    item["content"] = structured(item["main"], item["risks"], item["checks"])


def backup_db() -> str:
    path = _db_file_path()
    if not path or not os.path.exists(path):
        raise RuntimeError("SQLite database file not found")
    backup_dir = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"gather.before_forum_port30d_rebuild.{stamp}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    return dest


def upsert_item(db, item: dict, now: datetime) -> bool:
    row = db.get(CollectedItem, item["id"])
    is_new = row is None
    if row is None:
        row = CollectedItem(id=item["id"], source_id=FOB_SOURCE_ID, topic_id=TOPIC_ID)
        db.add(row)
    row.source_id = FOB_SOURCE_ID
    row.run_id = RUN_ID
    row.topic_id = TOPIC_ID
    row.title = item["title"]
    row.content = item["content"]
    row.content_hash = hashlib.sha256(item["content"].encode("utf-8")).hexdigest()
    row.summary = item["main"]
    row.url = item["url"]
    row.language = "zh"
    row.category = "口岸走私伪瞒报夹藏风险/论坛近月线索"
    row.entities = {
        **item["entities"],
        "主要内容": item["main"],
        "涉及风险点": item["risks"],
        "后续排查方向": item["checks"],
    }
    row.status = "enriched"
    row.quality_score = item["score"]
    row.relevance_score = item["score"]
    row.published_at = item["published_at"]
    row.collected_at = row.collected_at or now
    row.updated_at = now
    row.authorization_level = "public"
    row.raw_metadata = {
        "collector": "Codex direct public forum collection",
        "public_access": True,
        "original_post_within_window": True,
        "window_start": WINDOW_START.isoformat(),
        "window_end": WINDOW_END.isoformat(),
        "risk_level": item["risk_level"],
        "verification_status": "pending",
        "allegation_notice": "论坛帖子或广告形成的待核线索，不构成违法认定",
        "contact_details_stored": False,
        "used_baidu_search_api": False,
        "used_tavily": False,
    }
    return is_new


def main() -> None:
    backup = backup_db()
    now = datetime.now(timezone.utc)
    removed_ids: list[str] = []
    new_count = 0

    with SessionLocal() as db:
        topic = db.get(Topic, TOPIC_ID)
        source = db.get(SourceConfig, FOB_SOURCE_ID)
        report = db.get(Report, REPORT_ID)
        if not topic or not source or not report:
            raise RuntimeError("Required topic, source, or report is missing")

        for row in db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).all():
            if row.id not in ORDERED_IDS:
                removed_ids.append(row.id)
                db.delete(row)

        db.flush()
        for item in ITEMS:
            new_count += int(upsert_item(db, item, now))
        db.flush()

        run = db.get(CollectionRun, RUN_ID)
        if run is None:
            run = CollectionRun(id=RUN_ID, source_id=FOB_SOURCE_ID, topic_id=TOPIC_ID)
            db.add(run)
        run.status = "completed"
        run.batch_id = "codex-forum-port-risk-30d-20260805"
        run.keywords_used = [
            "口岸", "敏感货", "买单报关", "伪报", "瞒报", "夹藏", "混报", "仿牌",
            "双清包税", "扣关赔付", "虚标", "原产地证", "二手发动机", "危险品",
        ]
        run.items_found = len(ITEMS)
        run.items_new = 10
        run.items_updated = 1
        run.items_failed = 0
        run.started_at = run.started_at or now
        run.completed_at = now
        run.duration_ms = 0
        run.window_start = WINDOW_START
        run.window_end = WINDOW_END
        run.error_log = []
        run.metadata_json = {
            "collector": "codex_direct_forum",
            "selection": "original_post_published_within_31_days",
            "focus": "port_smuggling_false_declaration_concealment",
            "removed_out_of_window_or_duplicate_items": removed_ids,
            "used_baidu_search_api": False,
            "used_tavily": False,
            "actual_container_numbers_found": 0,
        }
        run.progress_events = [
            {"at": now.isoformat(), "message": "完成近一个月口岸伪瞒报夹藏风险论坛帖重建"}
        ]

        topic.description = (
            "仅采集近31天公开论坛原帖，重点监测口岸走私、伪报、瞒报、夹藏、混报、买单报关、"
            "敏感货、仿牌、危险品和第三国转口风险；每条必须形成主要内容、风险点和后续排查方向。"
        )
        topic.collect_window_days = 31
        topic.keywords = list(
            dict.fromkeys(
                (topic.keywords or [])
                + [
                    "口岸", "港口", "买单报关", "敏感货", "伪报", "瞒报", "夹藏", "夹带",
                    "混报", "混装", "仿牌", "双清包税", "扣关赔付", "虚标", "少报数量",
                    "品名笼统", "原产地证", "二手发动机", "危险品", "电子烟", "菌粉",
                ]
            )
        )
        topic.description_prompt = (
            "严格按原帖发布时间筛选最近31天。仅保留与口岸实货监管有关的走私、伪报、瞒报、夹藏、混报、"
            "买单、仿牌、敏感货、危险品或异常转口线索。不得因近期回复收录旧帖。每条输出：主要内容、"
            "涉及风险点、后续排查方向，并提取口岸、路线、船公司、货物、箱型箱量及其他运输标识符。"
        )
        topic.last_run_at = now
        topic.last_collection_run_id = RUN_ID
        topic.last_error = None
        topic.updated_at = now

        report.title = "外贸论坛近一个月口岸走私、伪瞒报与夹藏风险报告（2026-07-05—2026-08-05）"
        report.report_type = "analytical"
        report.content = build_report()
        report.summary = (
            "按原帖发布时间重建，保留2026-07-05至2026-08-05共11条口岸风险线索。"
            "重点涉及南沙敏感货买单、电子烟韩国中转与双清包税、青岛杂货夹有食品和品牌服装、"
            "南沙仿牌揽货、电池参数虚标、二手发动机固废属性及马来西亚换柜原产地风险。"
        )
        report.status = "completed"
        report.item_ids = ORDERED_IDS
        report.item_count = len(ORDERED_IDS)
        report.collection_run_id = RUN_ID
        report.date_range_start = WINDOW_START
        report.date_range_end = WINDOW_END
        report.generated_at = now
        report.error_log = None

        db.flush()
        topic.total_items_collected = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).count()
        for cfg in db.query(SourceConfig).filter(SourceConfig.id.in_(topic.source_ids or [])).all():
            cfg.items_collected = db.query(CollectedItem).filter(CollectedItem.source_id == cfg.id).count()
            if cfg.id == FOB_SOURCE_ID:
                cfg.last_sync_at = now
                cfg.last_error = None
        db.commit()

        print(f"backup={backup}")
        print(f"removed={len(removed_ids)} ids={removed_ids}")
        print(f"new={new_count} total={topic.total_items_collected}")
        print(f"run={run.id} report={report.id} report_items={report.item_count}")


if __name__ == "__main__":
    main()
