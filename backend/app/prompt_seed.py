"""Built-in reusable prompt templates."""

AFRICA_CUSTOMS_RISK_PROMPT_ID = "africa-customs-risk-watch"
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

    topic = db.query(Topic).filter(Topic.id == ENFORCEMENT_TOPIC_ID).first()
    if topic and AFRICA_CUSTOMS_RISK_PROMPT_ID not in (topic.prompt_template_ids or []):
        topic.prompt_template_ids = [*(topic.prompt_template_ids or []), AFRICA_CUSTOMS_RISK_PROMPT_ID]
    db.commit()
