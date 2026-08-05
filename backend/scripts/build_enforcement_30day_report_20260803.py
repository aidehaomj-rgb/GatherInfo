"""Build and persist the verified 30-day enforcement intelligence report."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, Report  # noqa: E402
from app.report_export import _write_html, _write_md, _write_pdf  # noqa: E402


TOPIC_ID = "weekly-enforcement-intelligence"
REPORT_ID = "rpt-enforcement-30d-20260803"
DATE_FROM = datetime(2026, 7, 5, 0, 0, 0)
DATE_TO = datetime(2026, 8, 3, 23, 59, 59)
TITLE = "执法信息采集 近30日综合分析报告（2026年7月5日至8月3日）"
OUTPUT_DIR = ROOT_DIR / "data" / "reports" / "2026-08-03"
OUTPUT_STEM = "执法信息采集_近30日综合分析报告_多语种多模态复核及柜号补充版_2026-07-05至2026-08-03"
STRUCTURED_PATH = ROOT_DIR / "work" / "enforcement_report_20260803.json"
ENRICHMENT_PATH = ROOT_DIR / "work" / "enforcement_strong_case_enrichment.json"


CATEGORY_ORDER = [
    "毒品及药品",
    "贸易合规与一般走私",
    "濒危物种及野生动植物",
    "烟草及新型烟草制品",
    "知识产权侵权",
    "枪爆及武器",
    "其他边境执法",
]

LEVEL_LABELS = {
    "strong": "强涉华",
    "weak": "弱涉华",
    "major_non_china": "重大非涉华",
    "unclassified": "未分类",
}

JURISDICTION_ZH = {
    "Argentina": "阿根廷",
    "Australia": "澳大利亚",
    "Brazil": "巴西",
    "Canada": "加拿大",
    "Hong Kong": "中国香港",
    "India": "印度",
    "Indonesia": "印度尼西亚",
    "Italy": "意大利",
    "Japan": "日本",
    "New Zealand": "新西兰",
    "Pakistan": "巴基斯坦",
    "Panama": "巴拿马",
    "Philippines": "菲律宾",
    "Portugal": "葡萄牙",
    "Singapore": "新加坡",
    "Sri Lanka": "斯里兰卡",
    "Taiwan": "中国台湾",
    "Thailand": "泰国",
    "United Kingdom": "英国",
    "United States": "美国",
}


STRONG_CASE_DETAILS = {
    "a5128dfb24239123": {
        "headline": "台湾地区侦办人工智能服务器和芯片转运中国大陆案",
        "core_fact": "基隆地检部门羁押包括1名NVIDIA员工、2名Super Micro员工和1名青云科技员工在内的相关人员；案件指向伪造商业文件，将约50台含先进NVIDIA芯片的Super Micro服务器运往中国大陆，部分货物经台湾地区海关放行后由日本转运。",
        "persons": "NVIDIA员工1名、Super Micro员工2名、青云科技员工1名，公开报道均未披露姓名；全案共羁押7人。",
        "companies": "NVIDIA；Super Micro Computer；青云科技（Albatron Technology）。",
        "documents": "公开来源未披露报关单号、出口许可证号、集装箱号、提单号或运单号。",
        "transport": "公开来源确认部分服务器经台湾地区海关放行并经日本转运至中国大陆；具体运输工具、承运人及口岸未披露。",
        "goods": "约50台Super Micro高端人工智能服务器，内含先进NVIDIA芯片；具体芯片型号和序列号未披露。",
        "disposition": "建议围绕3家企业、服务器型号及日本转运路径，核查许可证、最终用户声明、报关单、物流承运人和设备序列号；重点比对商业单证伪造、转口贸易和实际最终用户不一致风险。",
    },
    "472a75422de01d1b": {
        "headline": "芝加哥海关查获中国来源未批准药品“主纸箱”走私货物",
        "core_fact": "美国海关与边境保护局在芝加哥奥黑尔国际机场查获来自中国、拟运往纽约州锡拉丘兹的货物，内含10412片未批准药物及2144瓶生长激素、类固醇等。单票货物内装有多件未列舱单且已预贴境内配送标签的小包裹。",
        "persons": "涉案寄件人、收件人未披露；Michael Pfeiffer为执法机关发言人，不属于涉案对象。",
        "companies": "境外供应商、美国收件企业及境内包裹承运商均未披露。",
        "documents": "公开来源未披露主运单、分运单、包裹追踪号或申报主体。",
        "transport": "奥黑尔国际机场货运渠道入境，拟拆分后交由美国境内包裹承运商投递。",
        "goods": "10412片药物和2144瓶制剂，涉及肿瘤、甲状腺、呼吸系统用药、生长激素、减肥药、勃起功能障碍药物和类固醇。",
        "disposition": "建议按“主纸箱+预贴境内面单”特征开展同寄件人、同收件地址、同电话和同支付账户串并分析，重点核查药品通用名、生产企业、批号、FDA批准状态及国内出口主体。",
    },
    "c9697ddf3b5ae6e1": {
        "headline": "休斯敦机场查获大批中国来源世界杯侵权商品",
        "core_fact": "美国海关与边境保护局休斯敦IAH贸易执法队查获近2万件侵犯FIFA等商标权的商品，建议零售价接近900万美元；涉案货物包括球衣、短裤、酒具、足球等，多数货物来自中国，目的地既有美国境内也有境外。",
        "persons": "公开来源未披露寄件人、收件人或责任人姓名；Roderick Hudson为执法机关发言人。",
        "companies": "权利人包括FIFA；生产商、发货企业、进口商及电商平台未披露。",
        "documents": "公开来源未披露包裹追踪号、运单号、报关单号或知识产权扣留案号。",
        "transport": "IAH航空口岸及国际邮件、快件渠道；该通报为集中执法结果，并非单一集装箱案件。",
        "goods": "近2万件世界杯相关侵权商品，涉及美国、墨西哥、葡萄牙、法国、德国、巴西、西班牙、阿根廷和厄瓜多尔等国家队标识。",
        "disposition": "建议获取扣留清单和包裹级数据，反查中国寄件企业、电商店铺、支付账户、收件地址及重复发货轨迹；对高频寄件人和同款侵权标识开展风险画像。",
    },
    "codex-us-chinese-meth-australia-20260724": {
        "headline": "中国籍人员参与从美国向澳大利亚出口超1吨冰毒案",
        "core_fact": "美国法院判处中国籍人员Jing Tang Li 87个月监禁。2023年2月至12月间，美国海关查验7票拟从洛杉矶运往澳大利亚的货物，申报为地毯、家具、轮毂测试设备和铸造机，实际夹藏甲基苯丙胺，累计查获超过1000公斤。",
        "persons": "Jing Tang Li，中国籍，34岁；联邦法官Wesley L. Hsu、检察官Brenda N. Galván为司法人员。",
        "companies": "发货单所列公司被认定为虚假企业，公开来源未披露企业名称；洛杉矶仓库为犯罪网络集散点。",
        "documents": "公开来源未披露7票货物的提单号、集装箱号、承运人或虚假公司注册信息。",
        "transport": "洛杉矶至澳大利亚的出口货运；货物以托盘、纸箱、金属管和机械设备为载体，具体海运或空运方式未披露。",
        "goods": "超过1000公斤甲基苯丙胺；其中一票为2个托盘、23个纸箱夹藏约855.5公斤。",
        "disposition": "建议围绕Jing Tang Li、涉案仓库地址、7票虚假发货企业和澳大利亚收货方开展提单及舱单反查，重点筛查低经营痕迹企业申报大型机械设备、地毯家具但重量体积异常的出口货物。",
    },
    "codex-us-chinese-turtle-trafficking-20260723": {
        "headline": "两名中国籍人员将受保护龟类虚假申报出口至香港案",
        "core_fact": "Kin Keung Ho和Lihua Owen Ma承认违反美国《雷斯法案》，在无许可证和申报的情况下出口多种受保护龟类。Ho承认2024年6月至2025年11月寄出约99个包裹、共578只龟，并将货物虚假标注为水晶或石头。",
        "persons": "Kin Keung Ho；Lihua Owen Ma，二人均居住在纽约史坦顿岛。",
        "companies": "公开来源未披露经营企业、宠物贸易商或香港收货企业。",
        "documents": "公开来源未披露邮包追踪号、海关申报号、CITES许可证号；明确指出涉案货物没有所需许可证或申报。",
        "transport": "国际邮包渠道，自美国纽约发往亚洲，案件标题明确指向中国香港；美国邮政检查局协助调查。",
        "goods": "东部箱龟、西部箱龟、三趾箱龟、斑点龟和钻纹龟等，约578只。",
        "disposition": "建议以两名人员及史坦顿岛地址为核心，调取国际邮包申报、追踪号、收件人和支付信息，关联香港收货地址、宠物交易平台及CITES许可记录。",
    },
    "codex-us-unapproved-chinese-drugs-20260723": {
        "headline": "美国人员销售中国来源未批准减重药物案",
        "core_fact": "Brandon Piper因串谋将中国来源、未经批准且标签不实的处方药引入美国市场被判21个月监禁。涉案药物包括司美格鲁肽和替尔泊肽，曾经加拿大网站及其自营网站销售，部分货物虚假标注为“美国产品”。",
        "persons": "Brandon Piper，35岁；共同被告Mayze Nichols。",
        "companies": "MilestonePurity.com；另一加拿大销售网站名称未披露；中国生产商或供应商未披露。",
        "documents": "公开来源未披露进口报关单、快件运单、药品批号或采购订单。",
        "transport": "中国至美国的跨境电商/邮包式进口及美国境内配送，具体承运人未披露。",
        "goods": "未经批准的司美格鲁肽、替尔泊肽及其他肽类处方药，缺少处方、使用说明和黑框警告。",
        "disposition": "建议围绕MilestonePurity.com、Brandon Piper、Mayze Nichols和收付款账户追溯中国供应商，筛查“科研用途”“美国产品”等掩饰标签及肽类药物、冻干粉、小瓶制剂高频小包出口。",
    },
    "codex-thailand-origin-fraud-20260722": {
        "headline": "泰国查获中国商品换标冒充“泰国制造”案",
        "core_fact": "泰国海关与外贸部门在林查班港查获两批中国进口商品，分别为537万支TWOMOON香烟和超过20.2万套美工刀、多功能工具，货物在包装上虚假标注“泰国制造”，并不当利用泰国海关及自由区便利。",
        "persons": "公开来源未披露企业负责人或经办人员。",
        "companies": "公开来源仅披露TWOMOON品牌，未披露中国出口商、泰国进口商和自由区经营企业。",
        "documents": "公开来源未披露集装箱号、提单号、原产地证书编号或自由区单证。",
        "transport": "中国至泰国林查班港的海运/港口货物，后续利用自由区进行换标和再出口的具体路线未披露。",
        "goods": "537万支香烟；20.2万余套美工刀及多功能工具；总值超过1亿泰铢。",
        "disposition": "建议锁定TWOMOON品牌及相关HS编码，调取同期开往林查班港的提单、自由区入出区记录和原产地证书，核对包装、生产批次、加工增值比例及再出口目的地。",
    },
    "codex-ph-china-frozen-food-20260721": {
        "headline": "菲律宾查获5个中国来源误报冷冻农产品货柜",
        "core_fact": "菲律宾海关在马尼拉港查验5个来自中国的货柜。货物原申报为鱼丸、鱼豆腐、鱼籽丸、千页豆腐等，实货包括去皮鸡胸、冻鸽、北京鸭、冻鸭肉等，总值约2326.89万比索。",
        "persons": "公开来源未披露发货人、进口商或实际控制人；Ariel F. Nepomuceno、Rizalino Jose C. Torralba为执法机关负责人。",
        "companies": "公开来源未披露中菲企业名称；申报品名出现Fu Hua Lao Jiang和Qianye等品牌或商品标识。",
        "documents": "涉及3份装载前控制令和2份预警令；公开来源未披露货柜号、提单号和报关单号。",
        "transport": "中国至菲律宾马尼拉港的5个海运货柜。",
        "goods": "去皮/无皮鸡胸、冻鸽、北京鸭、冻鸭肉及其他冷冻食品；涉嫌误报和非法进口。",
        "disposition": "建议按5个货柜、申报品牌和具体品名调取提单及装箱单，反查中国生产企业、出口食品备案、冷链承运人和菲律宾进口商；比对申报品名与动物源性产品检疫许可。",
    },
    "codex-sri-lanka-chinese-cigarettes-20260717": {
        "headline": "斯里兰卡查获冷库板夹藏中国香烟案",
        "core_fact": "斯里兰卡海关中央情报部门依据国际合作信息，查获申报为冷库板的进口货物，板材内部夹藏约360万支、超过1.8万条香烟，市场价值超过4.5亿斯里兰卡卢比。货物拟交付德希瓦拉一家企业，海关怀疑在斯中国籍人员与案件有关。",
        "persons": "可能涉及在斯里兰卡居住或工作的中国籍人员，姓名未披露。",
        "companies": "德希瓦拉收货企业名称未披露；中国发货企业未披露。",
        "documents": "公开来源未披露集装箱号、提单号、进口报关单号或货物原产地证明。",
        "transport": "进口冷库板货物，具体起运港、承运船舶、航次和中转港未披露。",
        "goods": "约360万支香烟，夹藏于冷库板内部；预计逃税超过4亿斯里兰卡卢比。",
        "disposition": "建议先识别德希瓦拉收货企业和在斯中国籍关联人员，再以冷库板、保温板及相关HS编码反查同期提单；重点核验板材重量、密度、X光图像与正常货物参数偏离。",
    },
    "8d7c2ec3714b5419": {
        "headline": "中国籍旅客经曼谷、马尼拉赴港行李藏毒案",
        "core_fact": "香港海关在香港国际机场侦破两宗行李藏毒案。强涉华部分为一名47岁中国籍男旅客自泰国曼谷经菲律宾马尼拉抵港，在寄舱行李内夹藏约10公斤大麻花；同一通报另涉及两名菲律宾籍女子携带约12公斤大麻花。",
        "persons": "47岁中国籍男性，姓名未披露；另有26岁、33岁菲律宾籍女性2名。",
        "companies": "无企业主体披露。",
        "documents": "公开来源未披露航班号、行李牌号、护照号或订票信息。",
        "transport": "国际商业航班旅客渠道；路线为曼谷—马尼拉—香港，寄舱行李夹藏。",
        "goods": "强涉华部分约10公斤大麻花；两案合计约22公斤，估值约410万港元。",
        "disposition": "建议围绕旅客身份、航班、行李牌、购票和同行关系开展串并，关注曼谷—马尼拉—香港多段中转路线及临近时间同路线、同订票代理、同支付方式旅客。",
    },
    "codex-portugal-ipr-bags-20260710": {
        "headline": "葡萄牙海关扣停并销毁中国来源侵权箱包",
        "core_fact": "葡萄牙阿尔韦卡海关在2026年第二季度扣停一票来自中国的250件箱包，商业价值8747.50欧元；经权利人代表确认构成知识产权侵权后，货物依法销毁。",
        "persons": "公开来源未披露寄件人、收件人、权利人代表或责任人姓名。",
        "companies": "中国出口商、葡萄牙进口商、品牌权利人及承运商均未披露。",
        "documents": "公开来源未披露报关单号、提单/运单号、扣留案号或商标注册号。",
        "transport": "一票中国至葡萄牙的进口货物，具体海运、空运或邮递方式未披露。",
        "goods": "250件箱包，商业价值8747.50欧元。",
        "disposition": "建议获取扣留案卷中的品牌、款式、申报主体、收发货人及运单信息，反查国内生产企业和历史出口记录；对低货值、高品牌相似度箱包实施图片识别和价格偏离筛查。",
    },
    "codex-indonesia-illegal-used-phones-20260710": {
        "headline": "印度尼西亚侦结中国来源二手手机非法进口网络案",
        "core_fact": "印尼警方侦结中国来源二手手机及配件非法进口网络案，查扣约5万部手机及LCD、电池、主板等配件，并查扣25.63万件婴儿用品；另一处地点还查获1895部iPhone等。三名嫌疑人案件已完成P-21移送，一人在逃。",
        "persons": "DCP别名PR、SJ，均为中国籍；MT，PT TSL董事；TW，PT TSI董事并被列为在逃人员。",
        "companies": "PT TSL；PT TSI；中国供货企业未披露。",
        "documents": "案件依据2026年4月14日、15日两份警情报告立案；公开来源未披露进口报关单、提单号、集装箱号和商业发票。",
        "transport": "中国至印度尼西亚的非法进口网络，具体海运、空运、陆运路径及口岸未披露。",
        "goods": "约5万部二手手机及LCD、电池、主板等配件，25.63万件婴儿用品；另案查获1895部iPhone、408部损坏手机、1696个手机盒和674个充电器。",
        "disposition": "建议围绕DCP/PR、SJ、MT、TW及PT TSL、PT TSI开展工商、报关、提单和资金流关联核查，重点识别中国供应商、境外集货仓、拆机件申报和手机IMEI批次。",
    },
    "codex-indonesia-gold-smuggling-20260709": {
        "headline": "中国籍旅客拟由印度尼西亚携金赴马来西亚案",
        "core_fact": "印度尼西亚班达亚齐海关等部门在苏丹伊斯坎达尔·穆达国际机场查获一名拟乘商业航班前往马来西亚的中国籍旅客，其随身小包内有2根金条，重2989克，估值约72.54亿印尼盾。",
        "persons": "中国籍旅客，姓名仅披露首字母GP。",
        "companies": "无企业主体披露。",
        "documents": "公开来源未披露航班号、护照号、登机牌号、黄金编号或购买凭证。",
        "transport": "国际商业航班旅客渠道；印度尼西亚苏丹伊斯坎达尔·穆达国际机场至马来西亚；随身小包携带。",
        "goods": "2根金条，合计2989克；来源是否合法采矿仍在调查。",
        "disposition": "建议调取GP身份、航班和近期出入境记录，核查黄金购买凭证、序列标识、资金来源及马来西亚接货人；串并同机场、同航线高价值金属未申报案件。",
    },
    "codex-us-fentanyl-from-china-20260708": {
        "headline": "美国监狱遥控网络从中国获取芬太尼及合成大麻素案",
        "core_fact": "美国司法部通报，Devito Duran Young和Trace Davrin Works分别被判327个月和262个月监禁；案件涉及从中国向美国西南佐治亚州输送2610粒芬太尼药片和5502克合成大麻素。中国境内被告Xin Wang、Gao Yong仍在逃。",
        "persons": "Devito Duran Young（别名Big、Big Man）；Trace Davrin Works；Andreaus Benard Oliver Sr.（别名Doomie Oliver）；Andreaus Benard Oliver Jr.（别名Dray Oliver）；Xin Wang；Gao Yong。",
        "companies": "公开来源未披露中国生产企业、贸易商或美国收货企业。",
        "documents": "公开来源未披露国际邮包追踪号、运单号、支付订单或虚拟账户。",
        "transport": "中国至美国西南佐治亚州的邮递渠道；美国邮政检查局参与调查。",
        "goods": "2610粒芬太尼药片和5502克合成大麻素。",
        "disposition": "建议以Xin Wang、Gao Yong及美国5名共犯身份为锚点，核查国际邮包、收件地址、支付账户、通讯平台和同批次化学品/压片设备出口；对实名变体和地址共用关系开展图谱分析。",
    },
    "codex-singapore-gold-carousel-20260708": {
        "headline": "中新警方协作侦办信号转换器夹金及增值税循环骗税案",
        "core_fact": "新加坡警方起诉4人。中国境内犯罪团伙将黄金藏入信号转换器，向中国海关高价申报为高科技产品后出口至3家新加坡企业；货到后拆出黄金销售，主板再经香港公司返回中国重新组装，形成循环贸易并向香港幕后人员转移骗取的出口退税收益。",
        "persons": "Seow Choon Pheng；Seow Choon Lien；Chu Tung Wu；Tan Kui Moi，年龄60至63岁；香港幕后人员未披露姓名。",
        "companies": "Macropac System Pte Ltd；Megaspeed Services Pte Ltd；Seg Metallic Electronics Trading Pte Ltd；中国境内2家供应商及香港中转公司名称未披露。",
        "documents": "公开来源未披露报关单号、出口退税凭证、集装箱号、提单号、商业发票或主板回运单证。",
        "transport": "中国—新加坡—中国香港—中国的循环贸易链；具体运输工具、港口和承运人未披露。",
        "goods": "夹藏黄金的信号转换器及拆解后的主板，申报价格被人为抬高。",
        "disposition": "建议以4名人员和3家新加坡企业为核心，关联中国2家供应商、香港公司、报关价格、退税账户和主板回运记录；重点筛查高价低技术“信号转换器”重复往返、重量异常和同一主板循环申报。",
    },
    "codex-ph-china-vapes-20260708": {
        "headline": "菲律宾查获9个中国来源误报电子烟货柜",
        "core_fact": "菲律宾海关在马尼拉国际集装箱港对9个来自中国的货柜发布预警并实施100%实货查验。货物申报为纸箱、配件、包装袋、厨具、内衣、衣架、鞋盒和鞋类，实际为电子烟套装、一次性设备、烟弹等，估值约1.369亿比索。",
        "persons": "公开来源未披露发货人、进口商或实际控制人；Ariel F. Nepomuceno、Geoffrey K. De Vera IV为执法机关负责人。",
        "companies": "中国出口商、菲律宾进口商、报关行及电子烟品牌未披露。",
        "documents": "涉及9份预警令。完整柜号：CAAU 630269-2，ISO 6346校验位复算一致。残缺柜号线索：GCXU 50252…、CAOU 96270…，因末位和校验位被锁杆或构图遮挡，仅保留原图可见字符，不视为完整柜号、不作猜补。其余柜号、提单号、报关单号、封志号和许可证编号仍未公开。",
        "transport": "中国至菲律宾马尼拉国际集装箱港的9个海运货柜。",
        "goods": "电子烟套装、一次性电子烟、烟弹及配套产品，估值136924250比索；同期原图可辨识XBLACK Elite 25000、XBLACK Elite 30000及S-SAM外包装标签。",
        "disposition": "建议获取9个货柜的箱号、提单、申报主体和查验照片，围绕多品名拼报、低关联申报品名及同一进口商多柜集中到港特征开展国内出口端反查。",
    },
}


def _metadata(item: CollectedItem) -> dict:
    return item.raw_metadata if isinstance(item.raw_metadata, dict) else {}


def _review(item: CollectedItem) -> dict:
    value = _metadata(item).get("enforcement_review")
    return value if isinstance(value, dict) else {}


def _translation(item: CollectedItem) -> dict:
    value = _metadata(item).get("translation_zh")
    return value if isinstance(value, dict) else {}


def _clean(value: object, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    text = re.sub(r"^\s*#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    if limit and len(text) > limit:
        return text[:limit].rstrip("，,；;。 ") + "。"
    return text


def _broad_category(case_type: str | None) -> str:
    value = str(case_type or "").casefold()
    if any(key in value for key in ("firearm", "weapon")):
        return "枪爆及武器"
    if any(key in value for key in ("drug", "narcotic", "methamphetamine", "fentanyl", "heroin")):
        return "毒品及药品"
    if any(key in value for key in ("wildlife", "endangered")):
        return "濒危物种及野生动植物"
    if any(key in value for key in ("tobacco", "cigarette", "vape")):
        return "烟草及新型烟草制品"
    if any(key in value for key in ("counterfeit", "intellectual property")):
        return "知识产权侵权"
    if value == "other":
        return "其他边境执法"
    return "贸易合规与一般走私"


def _case_record(item: CollectedItem) -> dict:
    review = _review(item)
    translation = _translation(item)
    title_zh = _clean(translation.get("title_zh") or item.title or "未命名案例")
    summary_zh = _clean(
        translation.get("summary_zh")
        or translation.get("content_zh")
        or item.summary
        or item.content
        or "公开来源未提供案件摘要。",
        360,
    )
    case_type = str(review.get("case_type") or item.category or "other")
    level = str(review.get("china_relevance_level") or "unclassified")
    jurisdiction = str(review.get("jurisdiction") or "待核验")
    return {
        "id": item.id,
        "published_at": item.published_at.isoformat() if item.published_at else "",
        "published_date": item.published_at.strftime("%Y-%m-%d") if item.published_at else "待核验",
        "title": title_zh,
        "original_title": _clean(item.title or ""),
        "summary": summary_zh,
        "url": item.url or "",
        "source_id": item.source_id or "",
        "source_name": str(review.get("source_name") or review.get("authority") or item.source_id or "待核验"),
        "authority": str(review.get("authority") or "待核验"),
        "jurisdiction": JURISDICTION_ZH.get(jurisdiction, jurisdiction),
        "case_type": case_type,
        "category": _broad_category(case_type),
        "level": level,
        "level_label": LEVEL_LABELS.get(level, level),
        "subject": _clean(review.get("subject") or "公开来源未披露"),
        "nexus": _clean(review.get("mainland_nexus_evidence") or "公开来源未披露明确涉华依据。"),
    }


def _stats_line(counter: Counter) -> str:
    return "、".join(f"{name}{count}条" for name, count in counter.most_common())


def _build_markdown(records: list[dict], strong_cases: list[dict], stats: dict) -> str:
    category_counts = Counter(record["category"] for record in records)
    jurisdiction_counts = Counter(record["jurisdiction"] for record in records)
    lines = [
        "# 执法信息采集 近30日综合分析报告",
        "",
        "**统计时段：** 2026年7月5日至2026年8月3日（按原文发布日期，北京时间口径）",
        "",
        "**数据范围：** GatherInfo系统“执法信息采集”主题内发布日期可核验的59条境外执法信息。",
        "",
        "**编制说明：** 本报告以系统采集正文、中文译文及原始网页为依据。强涉华案例中的人名、企业、集装箱号、提单号和运输工具只摘录公开来源明确披露的内容；未披露字段统一标注，不作推测性补全。",
        "",
        "## 一、总体态势",
        "",
        f"近30日共纳入{stats['total']}条执法信息，其中强涉华{stats['levels'].get('strong', 0)}条、弱涉华{stats['levels'].get('weak', 0)}条、重大非涉华{stats['levels'].get('major_non_china', 0)}条。强涉华信息占全部条目的{stats['strong_ratio']:.1f}%。",
        "",
        f"从案件类型看，{_stats_line(category_counts)}。毒品及药品案件数量最多，反映国际航空旅客、海运货柜、邮包快件和一般贸易货运仍是主要风险载体；贸易合规与一般走私案件则突出表现为原产地换标、误报品名、非法进口、贵金属夹藏和出口管制规避。",
        "",
        f"从国家和地区看，信息主要分布在{_stats_line(Counter(dict(jurisdiction_counts.most_common(10))))}。强涉华案例覆盖美国、中国台湾、泰国、菲律宾、斯里兰卡、中国香港、葡萄牙、印度尼西亚和新加坡，来源结构较以往更为多元。",
        "",
        "## 二、分类研判",
        "",
        "### （一）毒品及药品",
        "",
        "共26条。大宗毒品案件继续呈现跨国组织化、藏匿载体机械化和运输路径多段化特征；强涉华案例同时出现中国籍人员参与、从中国采购芬太尼及合成大麻素、中国来源未批准处方药经跨境电商和邮包进入境外市场等情形。对华关联不只体现在货物原产地，也体现在人员、支付、邮包和网络销售环节。",
        "",
        "### （二）贸易合规与一般走私",
        "",
        "共10条。重点风险包括先进计算设备绕道转运、自由区换标、冷冻农产品和电子烟误报、二手手机非法进口、黄金夹藏及循环贸易骗税。多起案件没有在新闻稿中公布企业和单证号码，后续处置必须以执法机关案卷、舱单、提单、报关单和资金流数据补齐主体链条。",
        "",
        "### （三）濒危物种及野生动植物",
        "",
        "共7条。案件主要涉及活体龟、蜥蜴和鸟类等，运输渠道包括旅客行李和国际邮包。美国龟类案件已披露中国籍人员姓名、包裹数量和虚假申报品名，具备进一步串并收件人、交易平台和CITES许可记录的条件。",
        "",
        "### （四）烟草及新型烟草制品",
        "",
        "共7条。风险形态包括海运货柜误报电子烟、冷库板夹藏香烟、原产地换标和一般私烟运输。大批量货柜案件与小批量旅客、快件案件并存，应同步关注货柜级申报异常和品牌、包装、税标等商品特征。",
        "",
        "### （五）知识产权侵权",
        "",
        "共3条。美国和葡萄牙案件均显示中国来源商品在体育赛事周边、箱包等品类中仍具较高侵权风险。当前公开通报多缺少生产商和进口商信息，需通过包裹级、扣留案卷级数据识别国内生产和出口主体。",
        "",
        "### （六）枪爆及武器",
        "",
        "共3条，均属重大非涉华案件，主要来自澳大利亚。虽然未形成直接涉华线索，但其零部件采购、非法制造和港口查获方式可作为枪爆风险规则及关键词库的补充样本。",
        "",
        "### （七）其他边境执法",
        "",
        "共3条，其中部分条目与进出口执法关联度较低，建议后续采集审核进一步收紧“具体跨境行为”条件，将纯属人员通缉或境内极端材料案件降级至观察池，避免稀释周报主题。",
        "",
        "## 三、强涉华案例深度分析",
        "",
        "本部分对16条强涉华案例逐案提取主体、货物、单证和运输信息。案件当事人处于调查、起诉或审理阶段的，相关身份和行为表述均以原公开来源为限，不作超出来源的定性。",
    ]
    for index, case in enumerate(strong_cases, 1):
        detail = case["detail"]
        research = case["research"]
        extra_sources = "；".join(
            f"[{label}]({url})" for label, url in research["sources"]
        )
        lines.extend([
            "",
            f"### {index}. {detail['headline']}",
            "",
            f"**核心事实：** {detail['core_fact']}",
            "",
            f"- **人名及人员线索：** {detail['persons']}",
            f"- **企业及机构线索：** {detail['companies']}",
            f"- **集装箱号、提单号等单证：** {detail['documents']}",
            f"- **运输工具及路线：** {detail['transport']}",
            f"- **涉案货物：** {detail['goods']}",
            f"- **下一步处置提示：** {detail['disposition']}",
            f"- **多语种复核范围：** {research['languages']}",
            f"- **关联报道补充：** {research['findings']}",
            f"- **图片及多模态核验：** {research['multimodal']}",
            f"- **证据判断：** {research['assessment']}",
            f"- **补充来源：** {extra_sources}",
            f"- **来源：** [{case['source_name']}]({case['url']})，发布日期{case['published_date']}。",
        ])
    lines.extend([
        "",
        "## 四、跨案风险特征",
        "",
        "一是涉华关联由单一“中国产地”向人员、企业、转运地和交易网络复合关联发展。16条强涉华案件中，既有中国来源货物，也有中国籍涉案人员、香港中转公司、日本转运路径和中国境内供应商等多种线索，应实行多字段联合识别。",
        "",
        "二是申报伪装与货物物理夹藏交织。电子烟、冷冻食品、香烟、黄金、毒品等案件分别使用多品名误报、原产地换标、冷库板夹层、信号转换器夹金和机械设备藏毒等手法，风险规则应同时覆盖申报文本、价格重量、设备结构和X光图像。",
        "",
        "三是海运货柜、航空旅客和邮包快件三类渠道均存在高价值涉华线索。货柜案件数量虽少，但单案货值和规模较大；航空旅客案件身份、航班和行李信息较完整；邮包快件案件则具有高频、小批、主体分散和平台化特征，需要按渠道建立不同的串并模型。",
        "",
        "四是公开报道通常不会同步披露集装箱号、提单号和完整企业名称。16条强涉华案例中，仅少数披露涉案人员和企业，多数未公开单证号码。公开源情报适合作为风险发现入口，不能替代海关内部数据和执法协作渠道的二次核验。",
        "",
        "## 五、下一步处置建议",
        "",
        "1. 建立强涉华案例线索台账。将本报告已披露的人名、企业、网站、品牌、路线、货物和数量录入结构化台账，对别名、英文名和公司简称进行统一规范，逐项标记来源和可信度。",
        "",
        "2. 开展单证反查。对菲律宾9个电子烟货柜、5个冷冻食品货柜、泰国换标货物、斯里兰卡冷库板夹烟等案件，通过国际执法合作或公开案卷申请获取箱号、提单号、收发货人和报关行信息，再与国内出口报关、舱单和物流数据比对。",
        "",
        "3. 强化人员和企业关系串并。优先核查Xin Wang、Gao Yong、Jing Tang Li、Kin Keung Ho、Lihua Owen Ma、DCP/PR、SJ、MT、TW以及Macropac、Megaspeed Services、Seg Metallic、PT TSL、PT TSI等主体，关联地址、电话、邮箱、账户、历史申报和共同交易方。",
        "",
        "4. 设置渠道化风险规则。海运侧突出多柜集中到港、申报品名与实货用途不一致、自由区换标和设备异常增重；航空侧突出多段中转、行李重量异常和高价值贵金属未申报；邮包侧突出主纸箱拆分、预贴境内面单、科研用途标签和高频小包。",
        "",
        "5. 建立反馈闭环。对反查命中的企业和人员形成核查任务，记录是否发现同类申报、是否进入风险参数、是否开展查验及处置结果，并将反馈用于调整信息源权重、关键词和大模型审核规则。",
        "",
        "## 附录：近30日境外进出口执法案例分类汇编",
        "",
        "以下59条按案件类型分组、组内按原文发布日期倒序排列。摘要优先采用系统中文译文，原始网页链接附后备查。",
    ])
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["category"]].append(record)
    overall_index = 0
    for category in CATEGORY_ORDER:
        category_records = grouped.get(category, [])
        if not category_records:
            continue
        lines.extend(["", f"### {category}（{len(category_records)}条）"])
        for record in category_records:
            overall_index += 1
            lines.extend([
                "",
                f"**{overall_index}. {record['title']}**",
                "",
                f"{record['summary']}",
                "",
                f"发布日期：{record['published_date']}；国家或地区：{record['jurisdiction']}；涉华等级：{record['level_label']}；执法机关：{record['authority']}。",
                "",
                f"原文链接：[{record['source_name']}]({record['url']})",
            ])
    return "\n".join(lines).strip()


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STRUCTURED_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        items = (
            db.query(CollectedItem)
            .filter(CollectedItem.topic_id == TOPIC_ID)
            .filter(CollectedItem.published_at >= DATE_FROM)
            .filter(CollectedItem.published_at <= DATE_TO)
            .order_by(CollectedItem.published_at.desc())
            .all()
        )
        records = [_case_record(item) for item in items]
        levels = Counter(record["level"] for record in records)
        categories = Counter(record["category"] for record in records)
        jurisdictions = Counter(record["jurisdiction"] for record in records)
        enrichment = json.loads(ENRICHMENT_PATH.read_text(encoding="utf-8"))
        strong_cases = []
        for record in records:
            if record["level"] != "strong":
                continue
            detail = STRONG_CASE_DETAILS.get(record["id"])
            if not detail:
                raise RuntimeError(f"Missing verified detail for strong case: {record['id']}")
            research = enrichment.get(record["id"])
            if not research:
                raise RuntimeError(f"Missing extended research for strong case: {record['id']}")
            strong_cases.append({**record, "detail": detail, "research": research})
        if len(records) != 59 or len(strong_cases) != 16:
            raise RuntimeError(
                f"Unexpected report population: total={len(records)} strong={len(strong_cases)}"
            )
        stats = {
            "total": len(records),
            "levels": dict(levels),
            "categories": dict(categories),
            "jurisdictions": dict(jurisdictions),
            "strong_ratio": len(strong_cases) / len(records) * 100,
        }
        markdown = _build_markdown(records, strong_cases, stats)
        structured = {
            "report_id": REPORT_ID,
            "title": TITLE,
            "subtitle": "境外进出口执法动态分类研判及强涉华案例线索提取",
            "date_range": "2026年7月5日至2026年8月3日",
            "generated_at": "2026-08-03T12:30:00+08:00",
            "stats": stats,
            "strong_cases": strong_cases,
            "records": records,
            "category_order": CATEGORY_ORDER,
            "markdown": markdown,
        }
        STRUCTURED_PATH.write_text(
            json.dumps(structured, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        report = db.get(Report, REPORT_ID)
        if report is None:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID, title=TITLE)
            db.add(report)
        report.title = TITLE
        report.report_type = "analytical"
        report.content = markdown
        report.summary = (
            "近30日共梳理59条境外执法信息，其中强涉华16条、弱涉华16条、"
            "重大非涉华27条；对强涉华案例逐案提取人员、企业、单证、运输路线和处置线索。"
        )
        report.status = "completed"
        report.model_id = "codex-verified-open-source-analysis"
        report.tokens_used = 0
        report.item_count = len(records)
        report.item_ids = [record["id"] for record in records]
        report.date_range_start = DATE_FROM
        report.date_range_end = DATE_TO
        # Report timestamps are stored as naive UTC and converted to Beijing time by the UI.
        report.generated_at = datetime(2026, 8, 3, 4, 30, 0)
        report.error_log = None

        md_path = OUTPUT_DIR / f"{OUTPUT_STEM}.md"
        html_path = OUTPUT_DIR / f"{OUTPUT_STEM}.html"
        docx_path = OUTPUT_DIR / f"{OUTPUT_STEM}.docx"
        pdf_path = OUTPUT_DIR / f"{OUTPUT_STEM}.pdf"
        _write_md(str(md_path), TITLE, markdown)
        _write_html(str(html_path), TITLE, markdown)
        _write_pdf(str(pdf_path), TITLE, markdown)
        report.output_dir = str(OUTPUT_DIR)
        report.output_files = {
            "md": str(md_path),
            "html": str(html_path),
            "docx": str(docx_path),
            "pdf": str(pdf_path),
        }
        db.commit()
        print(json.dumps({
            "report_id": REPORT_ID,
            "total": len(records),
            "strong": len(strong_cases),
            "structured_path": str(STRUCTURED_PATH),
            "docx_path": str(docx_path),
            "output_dir": str(OUTPUT_DIR),
        }, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
