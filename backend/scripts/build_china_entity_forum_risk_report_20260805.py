"""Build a forum-risk report constrained to entities that can be checked in China."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from app.database import SessionLocal, _db_file_path
from app.models import CollectedItem, PromptTemplate, Report, Topic


TOPIC_ID = "foreign-trade-forum-risk-monitoring"
PROMPT_ID = "forum-social-customs-risk-search"
REPORT_ID = "report-forum-risk-china-entity-20260805"
NOW = datetime.now(timezone.utc)
DATE_FROM = datetime(2026, 7, 5, tzinfo=timezone.utc)
DATE_TO = datetime(2026, 8, 5, 23, 59, 59, tzinfo=timezone.utc)

SELECTED_IDS = [
    "codex-forum-iterative-risk-20260805-02",
    "codex-forum-risk-20260805044348-02",
    "codex-forum-port30d-20260805-04",
    "codex-forum-port30d-20260805-03",
    "codex-forum-port30d-20260805-08",
    "codex-forum-port30d-20260805-07",
    "codex-forum-port30d-20260805-01",
    "codex-forum-port30d-20260805-05",
    "codex-forum-port30d-20260805-06",
    "codex-forum-port30d-20260805-10",
]

LEADS = {
    "codex-forum-iterative-risk-20260805-02": {
        "priority": "一级",
        "china_entities": [
            "深圳汇智通国际货运代理有限公司",
            "统一社会信用代码：914403000663312240（第三方企业信息页，须以官方登记复核）",
            "法定代表人：余堂成（第三方企业信息页，须复核）",
            "注册地址：深圳市宝安区福永街道福围社区下沙十二巷2号",
            "公开业务联系人：刘经理；电话/微信：13710430264；QQ：971125951",
            "境内节点：盐田港、深圳、威海",
        ],
        "source_supplement": (
            "同企业福步帖子：https://bbs.fobshanghai.com/thread-9334335-1-1.html；"
            "企业信息：https://www.job5156.com/comp/1859017；"
            "NVOCC名称佐证：https://www.nvoccs.cn/list/136.html"
        ),
        "risk": [
            "电子烟、烟油、烟弹及电池相关货物同时涉及危险品运输、出口申报、知识产权和目的国准入监管。",
            "买单报关件与正式报关件采用不同运输路径，前者称经釜山中转；结合双清包税和扣关赔付，需核查真实出口人、报关抬头和境外进口主体是否一致。",
            "40HQ/DG柜、每柜22个卡板、最低500KG及具体开船日均已披露，具备从盐田订舱和舱单数据中筛查的条件。",
        ],
        "followup": [
            "先在国家企业信用信息公示系统核准企业统一社会信用代码、法定代表人、注册地址、股东及历史变更，再核验国际货代和无船承运业务资格。",
            "以企业全称、电话13710430264、盐田港及帖子列明的7月14/15/21/22/28/29日、8月4/5日开船窗口，筛查电子烟或DG柜订舱、出口舱单和报关委托。",
            "对经釜山中转的买单件，比对前后程主/分提单、集装箱号映射、出口经营单位、实际交货人和境外进口人；对直航件核验美森、ZIM、EMC HTW实际船名航次。",
            "调取危险货物托运申报、UN38.3/MSDS、烟油成分、品牌授权、商业发票和收付款记录，检查申报品名、货值、重量及品牌是否一致。",
        ],
        "gaps": "真实货主、出口报关抬头、订舱号、提单号、船名航次和集装箱号尚未在公开帖子中出现。",
    },
    "codex-forum-risk-20260805044348-02": {
        "priority": "一级",
        "china_entities": [
            "境内生产/货源地：佛山铝材企业（帖子未披露企业名称）",
            "境内出口口岸：蛇口码头",
            "运输标识：阳明海运YML、2×40HQ",
        ],
        "source_supplement": "帖子给出佛山—蛇口—巴生港Westport—意大利的完整路线框架。",
        "risk": [
            "帖子称铝材在马来西亚仅换柜、未实施实质性加工，却以马来西亚名义报关并使用当地原产地文件，存在原产地伪报及规避反倾销措施风险。",
            "2×40HQ、蛇口、YML和巴生西港等信息能够形成较窄的运输筛查窗口。",
            "帖子自述的14万欧元追税处罚尚无官方文书支持，不应作为已确认事实。",
        ],
        "followup": [
            "从蛇口口岸筛查帖子发布时间附近出口至马来西亚的2×40HQ铝材申报，按YML承运、佛山交货来源及目的港Westport进一步收窄。",
            "比对出口报关单、装箱单、主分提单、箱号、佛山生产企业发票和收汇记录，确认真实生产商、出口抬头和境外收货人。",
            "串联巴生港换柜前后箱号和两程提单，核查马来西亚原产地证申请企业、生产能力、加工记录、能耗和增值比例。",
        ],
        "gaps": "未披露佛山企业名称、具体HS编码、YML船名航次、提单号和箱号。",
    },
    "codex-forum-port30d-20260805-04": {
        "priority": "一级",
        "china_entities": [
            "经营标识：递接物流（帖子自称，尚未对应到唯一工商主体）",
            "境内口岸/城市：广州、深圳、厦门、上海、青岛、天津、宁波",
            "境内货物：生物菌粉剂",
        ],
        "source_supplement": "帖子同时宣称陆运、海运、整柜和散货均可承接。",
        "risk": [
            "生物菌粉剂的菌种、成分、用途和检疫条件具有较强监管属性，笼统品名可能掩盖真实成分或准入要求。",
            "双清包税、多个出运口岸及“单一品名当天放行”组合，需关注不同成分是否被合并申报、不同口岸是否选择性申报。",
        ],
        "followup": [
            "先从福步账号、页面业务联系方式、收款账户和仓库地址反查“递接物流”对应的中国公司全称和统一社会信用代码，避免仅凭商号误认主体。",
            "按所列口岸筛查近期出口越南的菌粉、微生物制剂、添加剂或粉末类申报，比对同一发货人、电话、仓库和境外收货人。",
            "核验生产企业、菌种/成分、用途、HS编码、MSDS、检测报告、检验检疫及危险品属性，并检查是否长期使用单一笼统品名。",
        ],
        "gaps": "“递接物流”工商主体、联系电话、仓库地址、具体菌种、报关单和运单尚缺。",
    },
    "codex-forum-port30d-20260805-03": {
        "priority": "一级",
        "china_entities": [
            "境内口岸：南沙口岸",
            "经营线索：南沙拖车报关业务账号/广告联系方式",
            "境内货物：食品、化妆品、仿牌货物",
        ],
        "source_supplement": "原帖标题直接宣称承接“仿牌类”货物。",
        "risk": [
            "“仿牌类”直接对应海关知识产权保护风险；食品和化妆品还涉及生产资质、成分标签及检验检疫。",
            "拖车和报关由同一链条承接，若实际货物、装柜清单和报关资料不一致，可能形成混报、夹藏或品牌瞒报。",
        ],
        "followup": [
            "固化论坛页面、账号、业务电话/微信和历史发帖，以联系方式反查中国企业、报关企业和拖车企业。",
            "围绕该账号涉及的南沙仓库、车辆、司机和报关抬头，关联近期食品、化妆品及品牌货物装柜和查验记录。",
            "核验品牌授权、知识产权备案、生产企业、配方标签、检验检疫证明和申报品名数量。",
        ],
        "gaps": "企业全称、业务电话、车牌、仓库、品牌和报关单号尚未入库，应优先补采。",
    },
    "codex-forum-port30d-20260805-08": {
        "priority": "一级",
        "china_entities": [
            "境内口岸：青岛口岸",
            "经营线索：寻找青岛买单报关同行的福步账号",
            "境内货物：大量普货杂货、食品、有品牌服装",
        ],
        "source_supplement": "帖子明确说明杂货中含食品和有品牌服装。",
        "risk": [
            "买单报关、杂货混装、食品及品牌服装共同出现，兼具真实出口人错配、食品检疫、知识产权及夹藏混报风险。",
            "用“普货杂货”笼统覆盖多种监管属性货物，可能造成品名、数量、税号和品牌信息不实。",
        ],
        "followup": [
            "提取论坛账号、联系人和交货仓库，反查对应中国货主、货代和报关抬头。",
            "筛查青岛口岸同期杂货/普货拼箱，重点比对机检图像、查验照片、装箱单和仓库分票中是否同时出现食品与服装。",
            "核验食品生产/检疫资料、品牌授权、HS编码、实际交货人、付款主体和境外收货人。",
        ],
        "gaps": "具体食品、品牌、数量、货值、联系人、仓库、箱号和出口抬头尚缺。",
    },
    "codex-forum-port30d-20260805-07": {
        "priority": "一级",
        "china_entities": [
            "境内范围：华东口岸（具体口岸尚未披露）",
            "产品标识：锂电池包，实际18.5V/2600mAh，拟虚标24V/4A",
            "国内可核文件：UN38.3证书、MSDS、危险特性/运输鉴定资料",
        ],
        "source_supplement": "帖子给出电芯五串二并结构和真实、拟标参数。",
        "risk": [
            "客户明确要求虚标电压和容量，可能造成产品标签、UN38.3、商业单证、危险品托运资料及海关申报之间不一致。",
            "锂电池参数直接关系瓦时、危险品分类、包装和承运条件，虚标还可能形成运输安全风险。",
        ],
        "followup": [
            "通过论坛账号和附件信息提取企业、联系人、产品图片、型号及UN38.3报告编号，再反查国内报告持有人、送检企业和生产企业。",
            "筛查华东口岸以24V/4A申报、但配套UN38.3或MSDS显示18.5V/2600mAh的电池记录。",
            "比对订单、客户邮件、铭牌印刷、生产记录、装箱单、托运书、鉴定报告和报关申报要素。",
        ],
        "gaps": "企业、具体口岸、产品型号、UN38.3报告号、订单号和运单号尚缺。",
    },
    "codex-forum-port30d-20260805-01": {
        "priority": "二级",
        "china_entities": [
            "境内口岸：南沙口岸",
            "境内经营线索：自称南沙本土报关行的论坛账号",
            "运输方向：南沙—香港整柜及拖车",
        ],
        "source_supplement": "帖子自称覆盖申报、查验、拖车、仓库和全程跟踪。",
        "risk": [
            "敏感货、买单报关和南沙—香港整柜共同出现，存在实际货主、出口经营单位和报关抬头分离风险。",
            "同一服务链控制仓库、拖车和申报环节，需防范货物流与申报信息脱节。",
        ],
        "followup": [
            "补采论坛账号公开联系方式、企业全称、仓库地址和拖车车辆，以电话、收款账户和地址反查境内经营主体。",
            "围绕南沙—香港整柜筛查短期高频使用买单抬头、但无稳定生产经营记录的出口主体，并串联仓库、过磅、装柜和查验资料。",
            "取得具体货物后复核HS编码、申报要素、许可证、商检/危包资料和实际货值。",
        ],
        "gaps": "具体货物、企业全称、联系方式、车牌、仓库、船名航次和箱号均缺。",
    },
    "codex-forum-port30d-20260805-05": {
        "priority": "二级",
        "china_entities": [
            "境内口岸：南沙口岸、蛇口口岸",
            "境内经营线索：发布查验、审价和买单业务信息的报关从业者账号",
            "重点货物：拼箱、新旧设备、二手零部件、敏感品",
        ],
        "source_supplement": "帖子反映近期南沙查验排队、审价和归类核查趋严。",
        "risk": [
            "在查验和审价收紧背景下仍公开承接买单及敏感品，需关注真实货主与出口抬头不一致。",
            "笼统品名、异常单价、合格品/瑕疵品、新旧设备状态容易形成归类、价格和品质申报差异。",
        ],
        "followup": [
            "提取发帖账号、业务电话和历史广告，反查实际报关企业、货代企业及其常用出口抬头。",
            "按南沙、蛇口近期拼箱筛选笼统品名、单价显著偏离、同柜多货主和二手零部件申报。",
            "关联查验通知、改单记录、码头排队回执、超堆/柜租、生产台账和序列号。",
        ],
        "gaps": "未披露企业、联系方式、具体报关单、箱号和客户。",
    },
    "codex-forum-port30d-20260805-06": {
        "priority": "二级",
        "china_entities": [
            "境内口岸：南沙口岸、黄埔口岸",
            "境内货物：二手拆车发动机",
            "可核实物标识：发动机型号、序列号、残油残液及可使用状态",
        ],
        "source_supplement": "帖子称相关货物近期出货增加，并列出查验关注点。",
        "risk": [
            "可利用旧机件和报废固体废物边界模糊，存在将报废机件申报为可使用二手零部件的风险。",
            "残留机油、冷却液以及型号、序列号、新旧状态不一致，会同时影响固废属性、危险性和申报真实性。",
        ],
        "followup": [
            "筛查南沙、黄埔近期二手汽车发动机出口，以型号、序列号、来源拆解企业和成交价格识别重复或异常申报。",
            "核验拆解来源、可使用性检测、清洗排液记录、固废属性鉴别、装柜照片和目的国进口要求。",
            "将报关单、装箱单、过磅、查验照片和序列号逐台对应，识别实物与申报状态差异。",
        ],
        "gaps": "企业、车辆来源、发动机型号/序列号清单、数量、箱号和报关单号尚缺。",
    },
    "codex-forum-port30d-20260805-10": {
        "priority": "二级",
        "china_entities": [
            "境内口岸：上海口岸",
            "境内经营线索：寻求买单报关及原产地证服务的论坛账号",
            "中国单证：出口报关单、非优惠/优惠原产地证申请资料",
        ],
        "source_supplement": "帖子将买单报关和办理原产地证同时提出。",
        "risk": [
            "买单抬头与真实生产商、出口商可能不一致；同步申请原产地证会放大生产商、出口商及原产资格错配风险。",
            "若货物涉及贸易救济或目的国差别税率，不实原产地信息可能造成更大追溯风险。",
        ],
        "followup": [
            "补采论坛账号、联系电话、货物、目的国和办理原产地证的代理机构，反查中国生产商、实际货主及报关抬头。",
            "比对原产地证申请、生产企业材料、商业发票、提单、报关单、资金流和委托报关关系。",
            "关注同一代理、生产企业或买单抬头短期内为多家无关联货主集中申请原产地证。",
        ],
        "gaps": "货物、企业、目的国、联系方式、证书编号、报关单和运输标识均缺。",
    },
}

PROMPT_APPENDIX = """

[2026-08-05 中国实体优先约束]
本主题报告的核查对象必须能够在中国境内落地。正文条目至少满足以下一项：①中国企业全称、统一社会信用代码、公开业务电话/微信/邮箱或可反查的论坛账号；②明确中国口岸、仓库、工厂/货源城市、车辆或国内段运输节点；③可关联中国企业的产品型号、UN38.3/检测报告号、报关抬头、原产地证或国内订舱资料。
仅有外国个人姓名、外国税号、境外收件人或境外一般讨论的条目，不进入主要报告；即使风险表达直接，也只能列入排除说明或模式库。境外帖子只有在明确披露中国供应商/货代名称、联系方式、中国口岸或可反查的国内物流标识时才可入选。
每条报告固定输出：论坛及原帖链接、发布日期、采集内容摘要、可核查的中国实体/口岸/实物标识、风险分析、下一步核查建议、当前缺失字段。不得用外国承运人、码头、支付机构或末端配送商替代中国核查实体，也不得因其作为运输节点被提及而推定其参与违规。
"""


def backup_database() -> str:
    path = _db_file_path()
    if not path or not os.path.exists(path):
        raise RuntimeError("Database path is unavailable")
    backup_dir = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, f"gather.before_china_entity_report.{NOW:%Y%m%d_%H%M%S}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    return dest


def build_report(topic: Topic, items: list[CollectedItem]) -> str:
    lines = [
        f"# {topic.name}中国实体核查报告（2026-07-05—2026-08-05）",
        "",
        "## 一、报告说明",
        "",
        "本报告从主题库近一个月公开论坛信息中重新筛选，只保留能够在中国境内落地核查的10条线索。阿根廷个人、CUIT/CUIL、境外一般DDP讨论等无法直接对应中国企业或境内口岸的内容，已从正文剔除。",
        "",
        "正文中的企业、账号和业务广告均为公开网络线索；风险等级表示核查优先级，不构成违法事实认定。船公司、境外码头、支付机构和末端配送企业如被提及，仅作为运输或资金节点。",
        "",
        "## 二、中国核查对象总览",
        "",
        "| 核查类型 | 已提取对象 |",
        "|---|---|",
        "| 明确中国企业 | 深圳汇智通国际货运代理有限公司；递接物流（商号待落工商主体） |",
        "| 公开业务标识 | 刘经理、13710430264、QQ 971125951；其余福步账号/联系方式待补采 |",
        "| 珠三角口岸 | 南沙、黄埔、蛇口、盐田、深圳、广州 |",
        "| 其他境内口岸 | 青岛、上海、厦门、天津、宁波、威海 |",
        "| 境内货源/产品 | 佛山铝材、电子烟及烟油、菌粉剂、食品、化妆品、品牌服装、锂电池、二手发动机 |",
        "| 可核运输/单证 | 40HQ/DG柜、2×40HQ、卡板/重量、UN38.3、原产地证、主分提单、订舱及出口舱单 |",
        "",
        "## 三、论坛信息、风险分析及核查建议",
        "",
    ]
    for index, item in enumerate(items, 1):
        lead = LEADS[item.id]
        date = item.published_at.strftime("%Y-%m-%d") if item.published_at else "未知"
        lines.extend([
            f"### {index}. {item.title}（{lead['priority']}核查）",
            "",
            f"- 论坛来源：[{item.source.name if item.source else item.source_id}]({item.url})",
            f"- 发布日期：{date}",
            f"- 采集到的主要内容：{item.summary}",
            "- 可核查的中国实体或标识：",
        ])
        lines.extend(f"  - {value}" for value in lead["china_entities"])
        lines.append(f"- 交叉信息：{lead['source_supplement']}")
        lines.append("- 风险分析：")
        lines.extend(f"  - {value}" for value in lead["risk"])
        lines.append("- 下一步核查建议：")
        lines.extend(f"  {idx}. {value}" for idx, value in enumerate(lead["followup"], 1))
        lines.extend([f"- 当前缺失字段：{lead['gaps']}", ""])

    lines.extend([
        "## 四、排除及降级说明",
        "",
        "- 阿根廷多CUIT、仿牌服装交叉帖：虽然风险表达直接，但当前只有境外个人账号、外国身份号和境外物流节点，无法直接对应中国企业或中国口岸，因此不列入本报告正文。",
        "- 罗马尼亚无MRN、印度Bill of Entry、美国第三方IOR等帖子：未披露中国供应商或中国货代名称、电话、国内仓库和起运口岸，保留在模式库，不作为境内实查对象。",
        "- 出口数量遗漏近15%的帖子：风险行为直接，但没有企业、口岸、账号联系方式或运输标识，暂不纳入中国实体核查前十；应先补齐论坛账号及交易主体。",
        "- 汇智通福步广告与航隼帮船期帖属于同一企业和业务线，本报告合并分析，避免重复计为两条独立企业线索。",
        "",
        "## 五、建议执行顺序",
        "",
        "1. **立即核查**：深圳汇智通电子烟线路——中国企业、电话、地址、盐田口岸、DG柜、承运线路和日期均已具备。",
        "2. **口岸数据筛查**：佛山铝材蛇口转口、菌粉剂多口岸、南沙仿牌、青岛食品与品牌服装混装。",
        "3. **产品/证书反查**：18.5V/2600mAh电池虚标及二手发动机型号、序列号、固废属性。",
        "4. **先补主体再查业务**：南沙—香港敏感货、南沙/蛇口买单业务、上海买单报关与原产地证。",
        "",
        f"> 生成时间：{NOW.astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}。全部内容为公开网络待核线索。",
    ])
    return "\n".join(lines)


def main() -> None:
    backup = backup_database()
    with SessionLocal() as db:
        topic = db.get(Topic, TOPIC_ID)
        prompt = db.get(PromptTemplate, PROMPT_ID)
        if topic is None or prompt is None:
            raise RuntimeError("Required topic or prompt template is missing")

        items = [db.get(CollectedItem, item_id) for item_id in SELECTED_IDS]
        if any(item is None for item in items):
            missing = [item_id for item_id, item in zip(SELECTED_IDS, items) if item is None]
            raise RuntimeError(f"Missing report items: {missing}")

        selected = set(SELECTED_IDS)
        topic_items = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).all()
        foreign_markers = {
            "codex-forum-iterative-risk-20260805-01",
            "codex-foreign-forum-risk-20260805-01",
            "codex-foreign-forum-risk-20260805-03",
            "codex-foreign-forum-risk-20260805-04",
            "codex-foreign-forum-risk-20260805-05",
            "codex-foreign-forum-risk-20260805-06",
            "codex-foreign-forum-risk-20260805-07",
        }
        for item in topic_items:
            metadata = dict(item.raw_metadata or {})
            if item.id in selected:
                decision = "selected_china_entity_report"
                reason = "具备中国企业、公开业务标识、境内口岸、货源地或可反查产品/单证标识"
            elif item.id == "codex-forum-port30d-20260805-02":
                decision = "corroboration_only"
                reason = "与航隼帮汇智通电子烟线索合并，避免重复"
            elif item.id in foreign_markers:
                decision = "excluded_foreign_only"
                reason = "缺少可直接落地的中国企业、联系方式或境内口岸"
            else:
                decision = "reserve_missing_china_entity"
                reason = "风险内容保留，但中国主体或运输标识不足"
            metadata["china_entity_audit_20260805"] = {
                "decision": decision,
                "reason": reason,
                "report_id": REPORT_ID if item.id in selected else None,
                "required_fields": ["中国企业/账号", "境内口岸/仓库/货源地", "境内运输或单证标识"],
                "legal_notice": "公开帖子待核线索，不构成违法认定",
            }
            item.raw_metadata = metadata
            item.updated_at = NOW

        if "[2026-08-05 中国实体优先约束]" not in prompt.content:
            prompt.content = prompt.content.rstrip() + PROMPT_APPENDIX
        prompt.updated_at = NOW
        topic.keywords = list(dict.fromkeys((topic.keywords or []) + [
            "中国企业全称", "统一社会信用代码", "公开业务电话", "中国口岸", "境内仓库",
            "境内货源地", "中国报关抬头", "国内订舱", "UN38.3报告号", "原产地证申请企业",
        ]))
        description_marker = "[中国实体优先]"
        description_rule = (
            "[中国实体优先] 报告正文只保留可在境内核查的企业、账号、联系方式、口岸、仓库、货源地、"
            "产品证书或中国段运输标识；仅有外国个人或外国税号的条目降为模式库。"
        )
        if description_marker not in (topic.description_prompt or ""):
            topic.description_prompt = ((topic.description_prompt or "").rstrip() + "\n\n" + description_rule).strip()
        topic.updated_at = NOW

        report_text = build_report(topic, items)
        report = db.get(Report, REPORT_ID)
        if report is None:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID, title="")
            db.add(report)
        report.title = "外贸论坛违规清关与走私风险线索中国实体核查报告（2026-07-05—2026-08-05）"
        report.report_type = "analytical"
        report.content = report_text
        report.summary = (
            "从近一个月论坛信息中筛选10条可在中国境内落地核查的风险线索，逐条列明原帖、采集内容、"
            "中国企业/电话/口岸/产品标识、风险分析、下一步核查建议和缺失字段；外国个人线索已剔除。"
        )
        report.status = "completed"
        report.model_id = "codex-china-entity-forum-audit"
        report.tokens_used = 0
        report.item_count = len(items)
        report.item_ids = SELECTED_IDS
        report.error_log = None
        report.collection_run_id = "codex-forum-iter-round3-20260805"
        report.date_range_start = DATE_FROM
        report.date_range_end = DATE_TO
        report.output_files = None
        report.output_dir = None
        report.generated_at = NOW
        report.created_at = report.created_at or NOW

        db.commit()
        print(f"backup={backup}")
        print(f"report_id={report.id} status={report.status} items={report.item_count}")
        print(f"topic_items_audited={len(topic_items)} prompt_chars={len(prompt.content)}")


if __name__ == "__main__":
    main()
