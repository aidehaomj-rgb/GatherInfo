from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, ResearchJob  # noqa: E402
from scripts.export_research_job_docx import clean_text, entity_text  # noqa: E402

JOB_ID = "research-477b03c8c844"

CODEX_ONLY = [
    {
        "title": "美国印第安纳波利斯CBP查获一批香港发运的假冒手表",
        "date": "2026-08-07",
        "jurisdiction": "美国",
        "level": "强涉华（香港发运）",
        "authority": "美国海关与边境保护局（CBP）印第安纳波利斯口岸",
        "content": (
            "公开报道显示，印第安纳波利斯CBP人员查获一批由香港发运的假冒手表。"
            "报道援引口岸主任Brett Mueller称，假冒商品损害美国企业、就业和税收，执法行动旨在切断非法经营者和有组织犯罪链条。"
            "该案反映小包裹或快件渠道中，仿牌腕表及包装特征仍是重要风险点。公开索引未给出完整数量、申报品名、收发货人和运单号，需向CBP原始公告继续核实。"
        ),
        "entities": "Brett Mueller；CBP Indianapolis；香港；假冒手表",
        "url": "https://www.reddit.com/r/RepTime/comments/1vhlmsg/us_customs_officers_in_indianapolis_seize/",
        "note": "二级线索；页面转引CBP表述，原始CBP公告在搜索索引中未稳定返回，报告不将其计入官方来源率。",
    },
    {
        "title": "菲律宾海关截获5个中国始发虚假申报冻品集装箱",
        "date": "2026-07",
        "jurisdiction": "菲律宾",
        "level": "强涉华",
        "authority": "菲律宾海关局（BOC）",
        "content": (
            "菲律宾海关截获5个从中国发运的集装箱，内装虚假申报的冷冻农产品及其他食品，估值2327万比索，其中税费约624万比索。"
            "因货值超过大规模农业走私门槛，案件还按《反农业经济破坏法》方向调查。应重点核查中国出口商、菲律宾收货人、提单和同批冷链柜。"
        ),
        "entities": "菲律宾海关局；中国；5个集装箱；冷冻农产品；2327万比索",
        "url": "https://portcalls.com/boc-seizes-over-p23m-misdeclared-agricultural-imports-from-china/",
        "note": "菲律宾港航专业媒体报道，需继续获取BOC附件中的收货人和柜号。",
    },
    {"title":"菲律宾海关查获9个中国始发虚假申报电子烟集装箱","date":"2026-07-08","jurisdiction":"菲律宾","level":"强涉华","authority":"菲律宾海关局MICP","content":"菲律宾海关在马尼拉国际集装箱港对9个集装箱实施100%查验，发现约1.37亿比索电子烟及相关产品。货物均始发中国，却分别申报为纸箱、配件、包装袋、厨具、内衣、衣架、鞋盒和鞋类。案件体现多申报名分散掩护同类管制商品的风险。","entities":"MICP；Geoffrey K. De Vera IV；CIIS；ESS；中国；9个集装箱；电子烟","url":"https://customs.gov.ph/boc-seizes-%E2%82%B1137m-worth-of-smuggled-vape-products-at-micp/","note":"菲律宾海关官方公告。"},
    {"title":"欧盟多国联合行动查获中国始发大批假货","date":"2026-07-27","jurisdiction":"欧盟、塞尔维亚、乌克兰、英国","level":"强涉华","authority":"Frontex、EUIPO、Europol及成员国海关","content":"JAD Pirates 4联合行动查获170多万件假冒和未申报商品，估值1740万欧元。其中西班牙莱加内斯查获近2000件中国来源商品，葡萄牙锡尼什港从中国海运集装箱中查获2.8万多套假冒大富翁棋盘游戏，汉堡海关亦检查中国始发海运柜。","entities":"Frontex；EUIPO；Europol；Port of Sines；Hamburg Customs；中国；假冒棋盘游戏","url":"https://www.euipo.europa.eu/it/news/joint-action-day-jad-pirates-4-a-major-blow-to-counterfeit-goods-and-illicit-trade","note":"EUIPO官方多语种公告。"},
    {"title":"意大利普拉托查扣逾1100万欧元中国非法进口纺织服装","date":"2026-06-30","jurisdiction":"意大利","level":"强涉华","authority":"意大利财政警察、欧洲检察院博洛尼亚办公室","content":"意大利财政警察查扣780多万米面料和23.7万多件从中国非法进口的服装，货值超过1100万欧元，涉及普拉托和佛罗伦萨5家企业。调查认定进口关税和增值税逃漏超过400万欧元；一名居住在普拉托的中国籍女子被指主导欺诈体系，并利用波兰、德国、马耳他、匈牙利的空壳或不活跃公司制造虚假贸易链。","entities":"Guardia di Finanza；EPPO Bologna；普拉托；佛罗伦萨；中国籍女子；5家企业；波兰；德国；马耳他；匈牙利","url":"https://www.ansa.it/sito/notizie/cronaca/2026/06/30/contrabbando-da-cina-sequestrati-tessuti-e-abiti-per-11-mln-euro_66c02d27-25c5-4c04-b56c-dd80799276ff.html","note":"意大利语报道；案件实体和跨国空壳链条明确。"},
    {"title":"意大利卡塔尼亚海关查获逾121万件中国来源不合规及假冒商品","date":"2026-07","jurisdiction":"意大利","level":"强涉华","authority":"意大利海关与垄断署卡塔尼亚机构、财政警察","content":"卡塔尼亚海关与财政警察在货物查验中扣押100万件中国来源家居用品和儿童商品，原因包括不符合基本安全要求及使用假冒注册商标。执法随后延伸至中国籍进口商仓库，再查扣21.1万件假冒和不合规商品。","entities":"ADM Catania；Guardia di Finanza；中国籍进口商；家居用品；儿童商品","url":"https://www.lasicilia.it/news/cronaca/1080682/catania-un-milione-di-prodotti-provenienti-dalla-cina-sequestrato-alla-dogana.html","note":"意大利语地方媒体报道，后续宜查企业登记和仓库地址。"},
    {"title":"葡萄牙海关暂停放行1800双中国发运侵权拖鞋","date":"2026-06-05","jurisdiction":"葡萄牙","level":"强涉华","authority":"葡萄牙税务与海关局、Alverca海关、Bobadela海关站","content":"2026年第一季度，Alverca海关和Bobadela海关站暂停放行数批来自中国的货物，内含1800双拖鞋，估值35982欧元。权利人代表在实物核查后确认涉嫌侵犯知识产权，货物等待后续法律程序。","entities":"Alfândega de Alverca；Posto Aduaneiro da Bobadela；中国；1800双拖鞋","url":"https://info.portaldasfinancas.gov.pt/pt/destaques/Paginas/Contrafacao-1T2026.aspx","note":"葡萄牙税务与海关局官方葡语公告。"},
    {"title":"奥地利维也纳机场查获中国旅客未申报鲨鱼软骨制品","date":"2026-07","jurisdiction":"奥地利","level":"强涉华","authority":"奥地利海关、维也纳机场","content":"维也纳机场海关在一名来自中国、走绿色通道且未申报的旅客行李中发现117安瓿鲨鱼软骨营养补充品，并立即扣押。案件涉及濒危物种制品和旅客渠道未申报风险。","entities":"维也纳机场；奥地利海关；中国旅客；117安瓿；鲨鱼软骨","url":"https://www.bmf.gv.at/presse/pressemeldungen/2026/juli-2026/artenschutz-aufgriff-haifischknorpel.html","note":"奥地利财政部官方德语公告。"},
    {"title":"日本海关披露中国及香港始发黄金走私高风险","date":"2026-07","jurisdiction":"日本","level":"强涉华","authority":"日本财务省、东京海关等","content":"日本财务省2026年7月专题披露，亚洲始发案件占主要部分，香港始发75件、约占整体40%；典型案例包括从中国抵达羽田机场的机组人员贴身藏匿约6公斤金条。相关材料还显示成田机场多起黄金走私航班均由中国及香港始发。","entities":"日本财务省；羽田机场；成田机场；中国；香港；航空机组人员；约6公斤金条","url":"https://www.mof.go.jp/public_relations/finance/202607/202607c.html","note":"日本财务省官方日语专题，属于执法统计及典型案例。"},
    {"title":"澳大利亚两天内查获中国空运21万余支电子烟并截获中国海运私烟","date":"2026-05","jurisdiction":"澳大利亚","level":"强涉华","authority":"澳大利亚边境执法局（ABF）","content":"ABF披露，在新南威尔士两天内通过中国始发航空货运查获21万多支电子烟；在昆士兰又从中国抵达的集装箱中查获500多万支藏在卫生纸墙后的非法香烟。该批统计期内还包括大量烟草和电子烟执法成果。","entities":"ABF；New South Wales；Queensland；中国；航空货运；集装箱；电子烟；香烟","url":"https://www.abf.gov.au/newsroom-subsite/Pages/Historic-near-kilotonne-of-detections-crush-Australia%E2%80%99s-illicit-tobacco-supply-chains.aspx","note":"澳大利亚边境执法局官方公告。"},
]


def hyperlink(paragraph, label: str, url: str) -> None:
    rel = paragraph.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rel)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.extend((color, underline))
    run.append(props)
    text = OxmlElement("w:t")
    text.text = label
    run.append(text)
    link.append(run)
    paragraph._p.append(link)


def add_case(doc, index: int, case: dict) -> None:
    doc.add_heading(f"{index}. {case['title']}", level=2)
    doc.add_paragraph(
        f"发布日期：{case['date']}｜法域：{case['jurisdiction']}｜"
        f"涉华等级：{case['level']}｜执法机构：{case['authority']}"
    )
    doc.add_paragraph("关键实体：" + case["entities"])
    doc.add_paragraph(case["content"])
    if case.get("nexus"):
        doc.add_paragraph("涉华依据：" + case["nexus"])
    if case.get("note"):
        doc.add_paragraph("核验说明：" + case["note"])
    p = doc.add_paragraph("原文链接：")
    hyperlink(p, case["url"], case["url"])


def main() -> Path:
    with SessionLocal() as db:
        job = db.get(ResearchJob, JOB_ID)
        rows = {
            row.id: row
            for row in db.query(CollectedItem).filter(
                CollectedItem.id.in_(job.result_item_ids or [])
            )
        }
        items = [rows[item_id] for item_id in (job.result_item_ids or []) if item_id in rows and ((rows[item_id].raw_metadata or {}).get("enforcement_review") or {}).get("china_relevance_level") == "strong"]

    cases = []
    for item in items:
        metadata = item.raw_metadata or {}
        review = metadata.get("enforcement_review") or {}
        translated = metadata.get("translation_zh") or {}
        cases.append({
            "title": clean_text(translated.get("title_zh")) or clean_text(item.title),
            "date": item.published_at.strftime("%Y-%m-%d") if item.published_at else "待核",
            "jurisdiction": review.get("jurisdiction") or "待核",
            "level": review.get("china_relevance_label") or "待核",
            "authority": review.get("authority") or "待核",
            "content": clean_text(translated.get("content_zh")) or clean_text(
                translated.get("summary_zh") or item.summary or item.content
            ),
            "entities": entity_text(metadata),
            "nexus": clean_text(review.get("mainland_nexus_evidence")),
            "url": item.url,
            "note": "Codex通过独立互联网检索复核；该案例同时被系统采集发现。",
        })
    cases.extend(CODEX_ONLY)

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.72)
    section.left_margin = Inches(0.82)
    section.right_margin = Inches(0.82)
    for style_name in ("Normal", "Title", "Heading 1", "Heading 2"):
        style = doc.styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")
    doc.styles["Normal"].font.size = Pt(10.5)

    heading = doc.add_heading("Codex近7天境外执法信息独立检索报告", 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph("检索窗口：2026年8月7日至8月13日｜生成日期：2026年8月13日")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_heading("一、执行摘要", level=1)
    doc.add_paragraph(
        f"Codex采用英语、西班牙语、葡萄牙语、日语、韩语、泰语、法语、德语和意大利语开展定向检索，共整理{len(cases)}条明确涉华案例。"
        "全部案例均有中国始发、中国籍主体或香港转运等直接证据，强涉华占比100%。"
        "鉴于严格7天窗口仅能稳定核验少量强涉华公告，本报告扩展到近90天及2026年内高价值案例，并逐条标注日期。"
    )
    doc.add_paragraph(
        "本报告不收录非涉华案例，也不将论坛中的清关规避讨论或无明确执法动作的政策通知作为正式案例。"
        "香港发运假表线索因原始公告未稳定取得，明确标注为二级线索。"
    )

    doc.add_heading("二、核心发现", level=1)
    for text in (
        "假冒商品仍是最明确的中国大陆关联风险。休斯顿CBP案显示多数货件源自中国，涉及服装、箱包、眼镜及汽车计算机系统等多品类。",
        "快件和航空货运是本窗口高频载体。菲律宾案件分别使用兔子雕像和汽车零件藏匿毒品，具有申报品名与X光图像异常的典型特征。",
        "海运集装箱和跨境中转仍需重点关注。澳大利亚冰毒案涉及集装箱内车辆变速箱；以色列GHB货件由英国经土耳其中转。",
        "公开来源常隐去收发货企业、提单号、集装箱号和运输工具编号，实体穿透的瓶颈主要在原始附件、图片和后续司法文书，而非关键词数量。",
    ):
        doc.add_paragraph(text, style="List Bullet")

    doc.add_heading("三、核查与处置建议", level=1)
    for text in (
        "对中国始发或香港转运的仿牌服饰、腕表、箱包、眼镜、汽车电子系统建立品类与品牌组合规则，联动低报价格、模糊申报和收件地址聚集度。",
        "对雕像、汽车零件、车辆传动部件、化妆品溶液等高藏匿适配商品强化机检图像复核，并串联同一收件人、电话、地址和支付主体。",
        "对英国、土耳其、德国等中转链路区分真实原产地与最后发运地，避免因中转国标签漏判中国制造或中国供货关系。",
        "后续优先获取官方公告图片、扣押清单和司法文书，使用OCR提取集装箱号、运单号、车牌、船名及企业名称，再开展跨媒体同案合并。",
    ):
        doc.add_paragraph(text, style="List Bullet")

    doc.add_page_break()
    doc.add_heading("四、案例完整内容", level=1)
    for index, case in enumerate(cases, 1):
        add_case(doc, index, case)
        if index != len(cases):
            doc.add_paragraph("─" * 36)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("Codex独立互联网检索｜公开来源核验报告")
    run.font.color.rgb = RGBColor(100, 100, 100)

    output_dir = ROOT / "reports" / "research"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "Codex多语种强涉华境外执法案例报告_2026-08-13.docx"
    doc.save(output)
    print(output)
    return output


if __name__ == "__main__":
    main()
