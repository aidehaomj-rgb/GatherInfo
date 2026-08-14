from __future__ import annotations

from datetime import datetime, timezone

import build_current_affairs_customs_report_20260813 as base

LEADS = base.LEADS


LEADS.extend([
    {
        "id": "current-affairs-customs-20260813-04",
        "title": "中国将10家美国军工及稀土相关实体列入出口管制管控名单",
        "published_at": datetime(2026, 6, 22, tzinfo=timezone.utc),
        "url": "https://www.mofcom.gov.cn/zwgk/zcfb/art/2026/art_dfa9cc5c1e004d7fbb86f83d249e7986.html",
        "category": "实体清单与最终用户",
        "summary": "Aveox、Red Cat、Teal Drones、MP Materials等10家美国实体被禁止获得中国两用物项。",
        "content": "公开事实：商务部2026年第23号公告将Aveox、Red Cat Holdings、Teal Drones、IMSAR、Jaia Robotics、Ball Aerospace、Oshkosh Defense、L3Harris Maritime、MP Materials和USA Rare Earth列入管控名单。监管研判：风险覆盖航空电子、无人机、雷达、机器人、海事设备和稀土材料，直接出口及境外转移均受约束。进一步核查：将名称、别名和公告地址接入申报及舱单拦截；倒查公告前后订单，核验最终用户、用途、许可证和第三国分销商，关注同址公司及关联采购。",
        "entities": {"companies": ["Aveox", "Red Cat Holdings", "Teal Drones", "IMSAR", "Jaia Robotics", "Ball Aerospace", "Oshkosh Defense", "L3Harris Maritime", "MP Materials", "USA Rare Earth"], "products": ["航空电子", "无人机", "雷达", "稀土材料"]},
    },
    {
        "id": "current-affairs-customs-20260813-05",
        "title": "中国将20家日本防务相关实体列入出口管制管控名单",
        "published_at": datetime(2026, 6, 29, tzinfo=timezone.utc),
        "url": "https://xkzj.mofcom.gov.cn/tzgg/art/2026/art_a1636a6f32a943b2b98ae305da897224.html",
        "category": "实体清单与最终用户",
        "summary": "防卫研究所、日钢特机、三菱电机防卫与空间技术等20家日本实体受到两用物项出口禁令。",
        "content": "公开事实：商务部公告将防卫研究所等20家参与提升日本军事实力的实体列入管控名单，禁止中国出口经营者和境外主体向其提供中国原产两用物项。监管研判：日本综合商社、制造商或研究机构可能作为采购及最终用户链条节点。进一步核查：使用附件中的日英名称和地址筛查收货人、通知人和最终用户；对电子、材料加工、传感器、船舶和航空航天物项核验单项许可、技术规格、用途声明及转售条款。",
        "entities": {"organizations": ["防卫研究所", "日钢特机株式会社", "三菱电机防卫与空间技术株式会社"], "countries": ["中国", "日本"], "products": ["两用物项"]},
    },
    {
        "id": "current-affairs-customs-20260813-06",
        "title": "三井E&S等20家日本实体因最终用户用途难核实被列入关注名单",
        "published_at": datetime(2026, 6, 29, tzinfo=timezone.utc),
        "url": "https://policy.mofcom.gov.cn/claw/clawContent.shtml?id=106215",
        "category": "最终用户核验",
        "summary": "相关企业不得使用通用许可，申请单项许可时须提交风险评估和非军事用途承诺。",
        "content": "公开事实：三井E&S等20家日本实体因两用物项最终用户、最终用途无法核实被列入关注名单，出口方只能申请单项许可并提交风险评估与书面承诺。监管研判：这类交易并非一律禁止，但文件真实性和用途穿透是海关验核重点。进一步核查：拦截使用通用许可或登记凭证的申报；比对风险评估、书面承诺、合同技术条款、安装地点和售后服务记录；对中间商代采及最终安装地点变更转人工复核。",
        "entities": {"companies": ["三井E&S株式会社"], "countries": ["中国", "日本"], "documents": ["单项许可", "风险评估报告", "非军事用途承诺"]},
    },
    {
        "id": "current-affairs-customs-20260813-07",
        "title": "美国放宽对阿联酋部分两用物项出口条件，转运监测变量增加",
        "published_at": datetime(2026, 7, 10, tzinfo=timezone.utc),
        "url": "https://www.bis.gov/press-release/department-commerce-eases-export-controls-uae",
        "category": "转运与来源国管制",
        "summary": "美国将阿联酋调整至A:5组，部分军民两用、卫星、油气及核能物项可适用许可例外。",
        "content": "公开事实：美国BIS于2026年7月10日调整阿联酋出口管制待遇，部分受控军品、商用卫星及油气、海水淡化、民用核能两用物项可适用STA许可例外。监管研判：阿联酋合法获得敏感货物的范围扩大，也使经阿联酋转口中国或其他目的地的来源、许可条件更复杂。进一步核查：对阿联酋启运的高端电子、卫星部件、油气设备核验原产国、ECCN、STA条件、再出口授权及最终用户；关注短期换单、自由区仓储和贸易商无终端能力。",
        "entities": {"organizations": ["美国商务部工业与安全局"], "countries": ["阿联酋", "中国", "美国"], "products": ["卫星部件", "油气设备", "民用核能物项"]},
    },
    {
        "id": "current-affairs-customs-20260813-08",
        "title": "博世因向华为及关联方供应MEMS传感器和软件被美国处罚",
        "published_at": datetime(2026, 6, 17, tzinfo=timezone.utc),
        "url": "https://www.bis.gov/news-updates",
        "category": "供应链与受限最终用户",
        "summary": "BIS称博世向华为及关联方供应约7237万美元MEMS传感器和汽车软件，达成3600万美元和解。",
        "content": "公开事实：美国BIS称Robert Bosch GmbH在2020至2024年间未经所需许可向华为及其关联方供应受EAR约束的MEMS传感器和汽车软件，并于2026年6月17日公布3600万美元和解。监管研判：同类货物进入中国时可能涉及多层制造商、组装商和最终用户，外方处罚不等同于中国进口违法。进一步核查：针对博世及其海外工厂至华为关联方的传感器和软件载体，核验原产地、生产工序、ECCN、许可证、收发货主体及实际用途；关注由第三国组装后改变品名或供应商的路线。",
        "entities": {"companies": ["Robert Bosch GmbH", "Huawei Technologies Co."], "products": ["MEMS传感器", "汽车软件"]},
    },
    {
        "id": "current-affairs-customs-20260813-09",
        "title": "美国警示与伊朗原油交易的中国独立炼厂及影子船队风险",
        "published_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
        "url": "https://ofac.treasury.gov/system/files/2026-04/20260428_teapot_refinery_alert.pdf",
        "category": "能源与船舶监管",
        "summary": "OFAC提示中国独立炼厂、贸易商、船东和服务商参与伊朗原油交易可能面临制裁风险。",
        "content": "公开事实：OFAC于2026年4月发布警示，称伊朗原油贸易使用影子船队、船对船过驳、伪造文件和AIS操纵，并提示与中国独立炼厂交易的制裁风险。监管研判：中国海关风险落点是进口原油原产地、装货港、船舶轨迹和价格单证一致性，不应把外方指控直接视为违法结论。进一步核查：联查提单、原产地证、品质证书、船舶IMO/AIS、历史船名、STS记录和付款路径；关注马来西亚等中转地、航迹中断、异常折价及装货港与原产地矛盾。",
        "entities": {"organizations": ["美国财政部外国资产控制办公室"], "products": ["原油"], "risk_objects": ["独立炼厂", "影子船队", "船对船过驳"]},
    },
    {
        "id": "current-affairs-customs-20260813-10",
        "title": "无人机、特种石墨和锂电池无证出口成为海关查验高风险模式",
        "published_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "url": "https://exportcontrol.mofcom.gov.cn/article/hgfw/hgal/202605/1290.html",
        "category": "海关执法与申报不实",
        "summary": "出口管制信息网归纳南京海关案例，指出伪报税号、低报货值、瞒报参数和无证出口的典型风险。",
        "content": "公开事实：中国出口管制信息网依据南京海关公开案例，归纳无人机、特种石墨、锂电池、光学镜片等两用物项无证出口及申报不实模式。监管研判：小额、民用名义或首次出口不能排除管制属性，技术参数比商品俗称更关键。进一步核查：对相关商品逐票比对材质、纯度、强度、续航、载荷等参数与完整HS编码；联查许可证、技术说明、检测报告、合同和最终用途证明；关注拆单、快件、跨境电商及市场采购渠道。",
        "entities": {"organizations": ["南京海关"], "products": ["无人机", "特种石墨", "锂电池", "光学镜片"], "risk_modes": ["伪报税号", "低报货值", "瞒报参数"]},
    },
])

def build_content() -> str:
    lines = [
        "# 涉进出口时政热点海关监管风险简报（2026年8月13日）",
        "", "## 一、总体判断", "",
        "本轮先执行自动检索，120条候选因日期或正文无法可靠核验未直接入库；经定向检索和原文复核后纳入10条。风险集中在两用物项许可、受限最终用户、第三国转运、能源船舶单证和技术参数申报。外方制裁或风险提示仅作为核查线索，不直接认定相关主体违法。",
        "", "## 二、核心发现", "",
        "1. **清单变化密集。** 美国、日本、欧洲相关实体名单连续调整，名称匹配必须扩展到别名、地址、关联方和代理采购方。",
        "2. **技术参数决定管制属性。** 无人机、MEMS传感器、特种石墨、锂电池、光学镜片等不能只按品名和税号判断。",
        "3. **转运链条是共同风险点。** 香港、阿联酋、中亚、土耳其及自由区仓储需要联查货物流、单证流和资金流。",
        "4. **能源风险可明确落到船货。** 伊朗原油线索可用IMO、AIS、STS过驳、原产地证、装货港和价格进行交叉核验。",
        "", "## 三、优先核查动作", "",
        "- 将本报告所列企业中英文名、别名、地址和关联方接入申报、舱单、许可证及企业画像碰撞。",
        "- 对无人机及部件、微电子、CNC机床、半导体设备、传感器、特种石墨和锂电池设置技术参数完整性规则。",
        "- 筛查近90日经香港、阿联酋、哈萨克斯坦、吉尔吉斯斯坦和土耳其转运的敏感货物量价及主体异常。",
        "- 对原油进口联查提单、原产地证、船舶IMO/AIS、历史船名、STS记录、付款路径和异常折价。",
        "", "## 四、采集线索", "",
    ]
    for index, lead in enumerate(LEADS, 1):
        lines.extend([
            f"### {index}. {lead['title']}", "",
            lead["content"],
            f"原文：{lead['url']}", "",
        ])
    return "\n".join(lines)


# The base persistence function reads this shared list and the replaced builder.
base.build_content = build_content

if __name__ == "__main__":
    base.persist = None
    base.main()
