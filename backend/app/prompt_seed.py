"""Built-in reusable prompt templates."""

from app.inforoute_prompts import INFOROUTE_PROMPTS, PLAYBOOK_PROMPT_IDS

AFRICA_CUSTOMS_RISK_PROMPT_ID = "africa-customs-risk-watch"
SUPPLY_CHAIN_EXPERT_PROMPT_ID = "supply-chain-expert-research"
ENFORCEMENT_TOPIC_ID = "weekly-enforcement-intelligence"
ENFORCEMENT_PROMPT_NAME = "执法案例采集"
AFRICA_CUSTOMS_RISK_PROMPT = """金属污染；海关；运输；查获；走私；非法；限制；进出口；外贸；港口；罢工；停运
危险爆炸物；袖珍打火机；
鞭炮；烟花；
矿物；金属；动物；枪械；武器
减少关税；降低关税；增加关税；入侵；未申报
海关查获爆炸物来自中国；中国走私商品到非洲
软件、游戏、电商平台、非洲
中国；非洲；禁令；政府；国家

(非洲|南非|北非|西非|东非|埃塞俄比亚|肯尼亚|乌干达|卢旺达|刚果|苏丹|阿尔及利亚|摩洛哥|几内亚)
(Africa|South Africa|North Africa|West Africa|East Africa|Ethiopia|Kenya|Uganda|Rwanda|Congo|Sudan|Algeria|Morocco|Guinea)
(加纳|尼日利亚|马里|中非|喀麦隆|加蓬|赞比亚|安哥拉|津巴布韦|马拉维|莫桑比克|博茨瓦纳|纳米比亚)
(Ghana|Nigeria|Mali|Central African Republic|Cameroon|Gabon|Zambia|Angola|Zimbabwe|Malawi|Mozambique|Botswana|Namibia)

*+(金矿|钻石|钴矿|铜矿|锂矿|稀土|宝石|锡矿|钨矿|钽铌矿|锰矿|铀矿|黄金|铬矿|战略矿产|矿石|铝土矿|铁矿|铅矿|锌矿|钛矿|工业矿物|矿|精矿|矿砂|钍矿|放射性矿物|核原料|铍矿|铟矿|镓矿|锗矿|铼矿|稀有金属|稀散金属|高纯金属)+(伪报品名|瞒报|低报|夹带|夹藏|混杂|掺杂|伪报规格|伪报含量|品名伪报|价格伪报|逃避关税|走私|非法出口|逃避监管|未申报|低报|放射性超标|无证运输|两用物项|扩散风险|核安全)+(海关|缉私|边防|查验|风险布控|邮递|口岸查验|集装箱|散货|海运|行李|拼箱|重量异常|密度异常|出口管制|进口管制|非洲航线)

*+(象牙|犀牛角|穿山甲鳞片|红木|紫檀|沉香|豹皮|河马牙|龟壳|濒危木材|濒危物种|野生动植物)+(走私|非法贸易|非法采伐|伪报品名|夹藏|藏匿|伪装|夹带|伪报|瞒报)+(海关|缉私|边防|濒危公约|监管|口岸查验|快件|邮递|行李|集装箱|海运|机场)

*+(精矿|矿渣|尾矿|冶炼渣|金属废料|废金属|合金|粗铜|粗铅|阳极泥|冶炼中间品|加工贸易)+(伪报品名|瞒报|夹藏|固废走私|洋垃圾|伪报规格|伪报含量|逃避监管|非法进口|非法出口|危险废物)+(海关|环保|固废监管|风险布控|集装箱|散货|海运|进口|出口|非洲航线)

*+(两用物项|无人机|违禁品|危险货物|烟花爆竹|打火机|易燃易爆品|火柴|烟花|爆竹|烟花|礼花|组合烟花|喷花|吐珠|升空烟花|玩具烟花|烟火药剂|引信|火工品|第1类爆炸品|UN0336|UN0306|3604100000|打火机|气体打火机|一次性打火机|可充气打火机|点火枪|打火器|点火棒|2.1类易燃气体|UN1057|危险货物|易燃易爆品|爆炸品|易燃气体|第1类爆炸品|2.1类易燃气体|烟花爆竹|打火机|烟火药剂|引信|UN0336|UN0306|UN1057|GB12268|烟花爆竹|打火机|火柴|烟火药剂|危险货物|易燃易爆品|UN0336|UN1057)+(走私|伪报|瞒报|夹藏|未申报|逃避监管|非法出口|非法进口|夹藏|藏匿|伪报|瞒报|未申报|伪报品名|低报|逃避监管|走私|混杂|夹带|伪装成普货|藏匿于|隐蔽包装|暗格|夹层|机检异常|密度异常|图像特征不符|跨境电商|邮递|快件|包裹|行李|日用品|礼品|工艺品|玩具|服装|鞋子|无危包证|未申报|逃避监管|风险布控)+(海关|监管|缉私|风险布控|集装箱|拼箱|海运|邮递|快件|行李|口岸查验|出口管制|反恐|防扩散|危包证|性能检验|使用鉴定|法检|商检|烟花爆竹检验|监管条件|危险品申报|无证出口|危险品包装|GHS标签|无危标|伪包装|集装箱|海运|拼箱|散货|跨境电商|邮递|快件|行李|非洲航线|东南亚航线|风险布控|人工查验)

*+(可卡因|大麻|海洛因|合成毒品|麻黄碱|胡椒醛|丙酮|乙醚|甲苯|易制毒化学品|制毒物品|前体化学品|毒品|液体毒品)+(走私|藏匿|中转|伪装|伪报|夹藏|未申报|人体藏毒|物流寄递|毒品中转|毒品转运)+(海关|缉毒|缉私|监管|邮递|快件|集装箱|航班|海运|出口管制)"""

SUPPLY_CHAIN_EXPERT_PROMPT = """你是“供应链穿透专家”，负责从公开互联网、官方文件、企业披露和贸易数据中发现“来自中国的供应边”与“目标企业的军工用途边”，形成可审核、可追溯的候选供应链。

一、不可违反的证据规则
1. 供应流向必须是“中国出口商 → 目标国家进口企业”。不得把目标企业向中国出口、在中国销售、泛称中国供应链或仅出现“中国”关键词的材料当成自中国进口证据。
2. importer 必须是同时出现在贸易边和军工边的企业主体；不得把国防部、军种、海关、采购机关或最终用户误作进口企业。
3. 贸易证据必须明确出现进口商、中国出口商或中国原产地、产品，以及可核验的运输/报关日期或明确报道发布日期。贸易日期必须位于系统传入的近期窗口内；缺少日期或超出窗口时只能标记待补证。
4. 军工合同可以早于近期进口记录。只要合同仍能证明该企业承担军工项目、供货角色或持续履约，即可作为军工边；但时间相近不能替代因果证明。
5. 完整链至少需要两个角色不同的独立 URL：一个证明军工合同/项目，一个证明自中国进口。URL 必须来自本轮检索结果，不得编造、改写或用同一来源兼任两条边。
6. 不得声称某一进口批次进入具体武器、平台或合同，除非原始来源、BOM、图号、料号、订单或批次追溯材料直接证明。否则只能表述为进入该企业总体供应链或构成待核线索。

二、多轮调查方法
第一轮建立信号集：并行检索官方合同、军方采购、企业公告、提单/海关索引、进口商页、供应商页及已有 audit/report/investigation。美国用英语；印度用英语和印地语；日本用日语和英语；中国台湾用繁体中文和英语。
第二轮实体穿透：从已得来源抽取企业法定名称、当地语名称、别名、地址、母子公司、产品、型号/料号、合同号、提单号和贸易对手，再按每个实体分别反查另一条证据边。优先读取 ImportGenius、ImportYeti、Panjiva、Volza、52wmb 等可公开索引页中的表格记录。
第三轮逐边验证和反证：核对企业/地址一致性、产品或料号关联、贸易日期是否在窗口内；主动搜索 civilian/commercial application、经销转售、同名企业、不同业务线、合同已终止等反证。已有调查报告只能作为线索入口，关键事实仍回到原始来源复核。

三、发现路径与输出标准
- 贸易优先：从近期中国出口/目标企业进口记录反查进口企业的军工合同。
- 军工优先：从军方合同、采购公告和主承包商名单反查近期中国供应商与进口记录。
- 桥接发现：用企业、地址、型号/料号、合同号、提单号和时间进行跨来源交叉。
- 双边证据闭合后可评 B/A 级；单边强来源只能为 C 级待补证，并具体写明“待补近期中国进口/提单证据”或“待补军工合同/最终用途证据”。
- 所有事实字段保持来源原值以便审计；页面描述使用中文，企业显示“中文名（英文或当地语原名）”，型号、合同号、提单号和金额保持原样。

只依据系统在当前阶段提供的来源和字段工作。信息不足时明确返回空结果或待补证，不用推测填满数量。"""


def ensure_builtin_prompt_templates(db) -> None:
    """Insert built-ins, apply safe metadata migrations, and attach defaults."""
    from app.models import PromptTemplate, Topic

    prompt = db.query(PromptTemplate).filter(
        PromptTemplate.id == AFRICA_CUSTOMS_RISK_PROMPT_ID,
    ).first()
    if not prompt:
        prompt = PromptTemplate(
            id=AFRICA_CUSTOMS_RISK_PROMPT_ID,
            name=ENFORCEMENT_PROMPT_NAME,
            description="覆盖海关查获、走私违规、危险品、矿产、野生动植物和毒品等执法案例线索。",
            content=AFRICA_CUSTOMS_RISK_PROMPT,
            is_active=True,
        )
        db.add(prompt)
    elif prompt.name == "非洲海关与走私风险监测":
        prompt.name = ENFORCEMENT_PROMPT_NAME
        prompt.description = "覆盖海关查获、走私违规、危险品、矿产、野生动植物和毒品等执法案例线索。"

    supply_chain_prompt = db.query(PromptTemplate).filter(
        PromptTemplate.id == SUPPLY_CHAIN_EXPERT_PROMPT_ID,
    ).first()
    if not supply_chain_prompt:
        db.add(PromptTemplate(
            id=SUPPLY_CHAIN_EXPERT_PROMPT_ID,
            name="供应链专家深度采集与证据链审核",
            description="供应链专家运行时自动加载；控制多语种检索、实体穿透、近期中国进口校验和军工证据闭合。",
            content=SUPPLY_CHAIN_EXPERT_PROMPT,
            is_active=True,
        ))

    # 融合自 InfoRoute 的 9 套证据化整理/研究提示词（缺失才插入，不覆盖已编辑版本）。
    # 其中 3 套为「采集处理宝典」（采集方法指引），标注 kind=playbook 以独立呈现。
    for prompt_id, name, description, content in INFOROUTE_PROMPTS:
        kind = "playbook" if prompt_id in PLAYBOOK_PROMPT_IDS else "prompt"
        existing = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
        if not existing:
            db.add(PromptTemplate(
                id=prompt_id,
                name=name,
                description=description,
                content=content,
                kind=kind,
                is_active=True,
            ))
        elif getattr(existing, "kind", "prompt") != kind:
            existing.kind = kind

    topic = db.query(Topic).filter(Topic.id == ENFORCEMENT_TOPIC_ID).first()
    if topic and AFRICA_CUSTOMS_RISK_PROMPT_ID not in (topic.prompt_template_ids or []):
        topic.prompt_template_ids = [*(topic.prompt_template_ids or []), AFRICA_CUSTOMS_RISK_PROMPT_ID]
    db.commit()


def resolve_supply_chain_expert_prompt(db) -> tuple[str, str | None]:
    """Return the editable expert prompt; a disabled row intentionally injects nothing."""
    from app.models import PromptTemplate

    prompt = db.query(PromptTemplate).filter(
        PromptTemplate.id == SUPPLY_CHAIN_EXPERT_PROMPT_ID,
    ).first()
    if prompt is None:
        return SUPPLY_CHAIN_EXPERT_PROMPT, SUPPLY_CHAIN_EXPERT_PROMPT_ID
    if not prompt.is_active or not prompt.content.strip():
        return "", None
    return prompt.content.strip(), prompt.id
