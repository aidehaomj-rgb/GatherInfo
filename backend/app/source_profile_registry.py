"""Audited source profiles ported from the local InfoRoute evidence registry."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from urllib.parse import urljoin, urlsplit

from sqlalchemy.orm import Session

from app.models import SourceConfig


@dataclass(frozen=True, slots=True)
class VerifiedSourceProfile:
    country: str
    languages: tuple[str, ...]
    discovery_urls: tuple[str, ...]
    robots_status: str
    terms_status: str
    crawl_delay_seconds: int
    llm_ingest_allowed: bool
    origin_resolution_required: bool
    note: str
    allowed_channels: tuple[str, ...]
    allowed_path_prefixes: tuple[str, ...]


VERIFIED_SOURCE_PROFILES = MappingProxyType({
    "api.tavily.com": VerifiedSourceProfile(
        "全球", ("multi",),
        ("https://docs.tavily.com/documentation/api-reference/introduction",),
        "api_required", "allowed_customer_api_output", 1, True, True,
        "仅处理 Tavily Search API 返回的带源链接内容片段；原站详情需另行核验，默认不抓全文。",
        ("api_search",), ("/search",),
    ),
    "cbp.gov": VerifiedSourceProfile(
        "美国", ("en", "es"),
        ("https://www.cbp.gov/sitemap.xml", "https://www.cbp.gov/newsroom/media-releases/all"),
        "allowed_with_disallows", "public_domain_with_exceptions", 2, True, False,
        "使用公开 sitemap/新闻栏目，避开搜索、登录和 robots 禁止目录。",
        ("rss", "web_scrape", "official"), ("/newsroom", "/rss/newsroom", "/sitemap"),
    ),
    "customs.govt.nz": VerifiedSourceProfile(
        "新西兰", ("en", "mi"),
        ("https://www.customs.govt.nz/sitemap", "https://www.customs.govt.nz/about-us/news/media-releases/"),
        "allowed_disallow_search", "linking_allowed_logo_restricted", 5, True, False,
        "使用 sitemap lastmod 和新闻列表，不访问站内搜索。",
        ("rss", "web_scrape", "official"), ("/about-us/news/media-releases", "/sitemap"),
    ),
    "abf.gov.au": VerifiedSourceProfile(
        "澳大利亚", ("en",),
        ("https://www.abf.gov.au/_layouts/15/AppPages/Rss.aspx?site=newsroom",),
        "allowed_disallow_search", "government_conditions_apply", 5, True, False,
        "RSS 优先，不探测 SharePoint 内部接口。",
        ("rss", "web_scrape", "official"), ("/sitenewsroom", "/_layouts/15/AppPages/Rss.aspx"),
    ),
    "zoll.de": VerifiedSourceProfile(
        "德国", ("de", "en"),
        ("https://www.zoll.de/DE/Presse/Pressemitteilungssuche/pressemitteilungen_fnode.html",),
        "allowed_crawl_delay_180", "government_conditions_apply", 180, True, False,
        "严格单并发，相邻请求至少 180 秒。",
        ("web_scrape", "official"), ("/DE/Presse/Pressemitteilungssuche",),
    ),
    "gov.br": VerifiedSourceProfile(
        "巴西", ("pt",),
        ("https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS",),
        "allowed", "government_conditions_apply", 2, True, False,
        "优先公开 RSS，过滤海关与外贸主题，不调用登录和表单路径。",
        ("rss", "web_scrape", "official"), ("/receitafederal/pt-br/assuntos/noticias", "/mdic/"),
    ),
    "gov.uk": VerifiedSourceProfile(
        "英国", ("en", "cy"),
        ("https://www.gov.uk/api/content/", "https://www.gov.uk/sitemap.xml"),
        "allowed_disallow_search_print", "open_government_licence_with_exceptions", 1, True, False,
        "优先官方 Content API/RSS，遵守 OGL 署名与例外内容要求。",
        ("rss", "web_scrape", "official", "json_api"), ("/api/content/", "/government/organisations/", "/sitemap"),
    ),
    "federalregister.gov": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://www.federalregister.gov/developers/documentation/api/v1",),
        "api_required_search_paths_disallowed", "us_government_publication_with_exceptions", 2, True, False,
        "只使用官方 API，不绕过 CAPTCHA，不抓取搜索与账户路径。",
        ("official", "json_api"), ("/api/v1/", "/developers/documentation/api/v1"),
    ),
    "defense.gov": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://www.defense.gov/News/Contracts/",),
        "allowed_with_system_path_disallows", "us_government_content_with_imagery_exceptions", 5, True, False,
        "使用公开合同列表与详情，不请求 CAPTCHA、打印或系统目录。",
        ("web_scrape", "official"), ("/News/Contracts/",),
    ),
    "ec.europa.eu": VerifiedSourceProfile(
        "欧盟", ("en", "multi"),
        (
            "https://ec.europa.eu/commission/presscorner/api/rss?language=en",
            "https://commission.europa.eu/legal-notice_en",
        ),
        "allowed_with_disallows", "cc_by_4_0_with_exceptions", 2,
        True, False,
        "使用 European Commission Press Corner 官方 RSS；欧委会自有文本按 CC BY 4.0 "
        "署名复用，第三方内容、标识和其他明确例外不进入全文处理。",
        ("rss", "web_scrape", "official", "json_api"), (
            "/commission/presscorner/api/rss",
            "/commission/presscorner/detail/",
            "/policy.trade.ec.europa.eu/",
            "/taxation-customs.ec.europa.eu/",
        ),
    ),
    "wto.org": VerifiedSourceProfile(
        "全球", ("en", "fr", "es"),
        (
            "https://www.wto.org/english/rss/news_e.xml",
            "https://www.wto.org/english/rss/tmrd_e.xml",
        ),
        "allowed_with_disallows", "wto_public_information_with_exceptions", 2,
        True, False,
        "使用 WTO 官方 RSS 新闻和贸易监测 feed；遵守 WTO 版权声明，不抓取搜索和账户路径。",
        ("rss", "web_scrape", "official"), ("/english/rss/", "/english/news_e/",),
    ),
    "unctad.org": VerifiedSourceProfile(
        "全球", ("en", "fr", "es"),
        ("https://unctad.org/rss.xml",),
        "allowed", "unctad_public_information", 2, True, False,
        "使用 UNCTAD 官方 RSS；遵守联合国版权声明，不抓取搜索和登录路径。",
        ("rss", "web_scrape"), ("/rss", "/news", "/press-release", "/publication"),
    ),
    "oecd.org": VerifiedSourceProfile(
        "全球", ("en", "fr"),
        ("https://www.oecd.org/rss.xml",),
        "allowed_with_disallows", "oecd_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 OECD 官方 RSS；遵守 OECD 使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/newsroom", "/content/", "/topics/"),
    ),
    "imf.org": VerifiedSourceProfile(
        "全球", ("en",),
        ("https://www.imf.org/en/News/RSS",),
        "allowed_with_disallows", "imf_public_information_with_exceptions", 2,
        True, False,
        "使用 IMF 官方 RSS；遵守 IMF 使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/en/News/", "/en/Research/", "/en/Publications/"),
    ),
    "ustr.gov": VerifiedSourceProfile(
        "美国", ("en", "es"),
        ("https://ustr.gov/rss/press-releases.xml",),
        "allowed_with_disallows", "us_government_publication_with_exceptions", 2,
        True, False,
        "使用 USTR 官方 RSS；遵守美国公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss/", "/about-us/policy-offices/press-office/"),
    ),
    "usitc.gov": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://www.usitc.gov/rss/releases.xml",),
        "allowed_with_disallows", "us_government_publication_with_exceptions", 2,
        True, False,
        "使用 USITC 官方 RSS；遵守美国公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss/", "/pressroom/", "/investigations/"),
    ),
    "bis.gov": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://www.bis.gov/rss.xml",),
        "allowed_with_disallows", "us_government_publication_with_exceptions", 2,
        True, False,
        "使用 BIS 官方 RSS；遵守美国公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/news", "/press-releases", "/policies-and-regulations"),
    ),
    "ofac.treasury.gov": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://ofac.treasury.gov/sanctions-programs-and-country-information",),
        "allowed_with_disallows", "us_government_publication_with_exceptions", 3,
        True, False,
        "使用 OFAC 公开制裁信息页面；遵守美国公共信息使用条款，不抓取搜索和账户路径。",
        ("web_scrape", "official"), ("/sanctions-programs-and-country-information", "/releases"),
    ),
    "gov.uk": VerifiedSourceProfile(
        "英国", ("en", "cy"),
        (
            "https://www.gov.uk/api/content/",
            "https://www.gov.uk/sitemap.xml",
            "https://www.gov.uk/government/organisations/department-for-business-and-trade.atom",
        ),
        "allowed_disallow_search_print", "open_government_licence_with_exceptions", 1, True, False,
        "优先官方 Content API/RSS，遵守 OGL 署名与例外内容要求。",
        ("rss", "web_scrape", "official", "json_api"),
        ("/api/content/", "/government/organisations/", "/government/news/", "/sitemap"),
    ),
    "wcoomd.org": VerifiedSourceProfile(
        "全球", ("en", "fr"),
        ("https://www.wcoomd.org/en/rss.aspx", "https://www.wcoomd.org/en/media/newsroom.aspx"),
        "allowed_with_disallows", "wco_public_information_with_exceptions", 3,
        True, False,
        "使用 WCO 官方 RSS 和新闻室页面；遵守 WCO 使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/en/rss", "/en/media/newsroom", "/en/topics/"),
    ),
    "asean.org": VerifiedSourceProfile(
        "东盟", ("en",),
        ("https://asean.org/feed/",),
        "allowed", "asean_public_information", 2, True, False,
        "使用 ASEAN 官方 RSS feed；遵守东盟使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/feed", "/press-release", "/news", "/communities"),
    ),
    "adb.org": VerifiedSourceProfile(
        "亚太", ("en",),
        ("https://www.adb.org/rss/news",),
        "allowed_with_disallows", "adb_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 ADB 官方 RSS；遵守亚行使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss/", "/news/", "/publications/"),
    ),
    "iisd.org": VerifiedSourceProfile(
        "全球", ("en", "fr", "es"),
        ("https://www.iisd.org/rss.xml",),
        "allowed", "iisd_creative_commons_with_exceptions", 2, True, False,
        "使用 IISD 官方 RSS；遵守 IISD 使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/articles", "/publications", "/topics/"),
    ),
    "piie.com": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://www.piie.com/rss.xml",),
        "allowed_with_disallows", "piie_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 PIIE 官方 RSS；遵守 PIIE 使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/blogs", "/publications", "/research"),
    ),
    "csis.org": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://www.csis.org/rss.xml",),
        "allowed_with_disallows", "csis_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 CSIS 官方 RSS；遵守 CSIS 使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/analysis", "/programs", "/events"),
    ),
    "iea.org": VerifiedSourceProfile(
        "全球", ("en",),
        ("https://www.iea.org/rss/all",),
        "allowed_with_disallows", "iea_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 IEA 官方 RSS；遵守 IEA 使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss/", "/news/", "/reports/", "/topics/"),
    ),
    "blogs.worldbank.org": VerifiedSourceProfile(
        "全球", ("en", "fr", "es", "ar"),
        ("https://blogs.worldbank.org/rss.xml",),
        "allowed_with_disallows", "world_bank_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 World Bank Blogs 官方 RSS；遵守世界银行使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/blog/", "/topic/", "/author/"),
    ),
    "news.un.org": VerifiedSourceProfile(
        "全球", ("en", "fr", "es", "ar", "zh"),
        ("https://news.un.org/feed/subscribe/en/news/all/rss.xml",),
        "allowed", "un_public_information", 2, True, False,
        "使用 UN News 官方 RSS；遵守联合国公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/feed/", "/en/news/", "/story/"),
    ),
    "fas.usda.gov": VerifiedSourceProfile(
        "美国", ("en", "es"),
        ("https://fas.usda.gov/rss.xml",),
        "allowed_with_disallows", "us_government_publication_with_exceptions", 2,
        True, False,
        "使用 USDA FAS 官方 RSS；遵守美国公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/newsroom", "/data", "/markets"),
    ),
    "international.gc.ca": VerifiedSourceProfile(
        "加拿大", ("en", "fr"),
        ("https://www.international.gc.ca/rss/news-nouvelles.aspx",),
        "allowed_with_disallows", "government_of_canada_open_licence", 2,
        True, False,
        "使用 Global Affairs Canada 官方 RSS；遵守加拿大政府开放许可，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss/", "/trade-agreements/", "/export-controls/", "/sanctions/"),
    ),
    "meti.go.jp": VerifiedSourceProfile(
        "日本", ("en", "ja"),
        ("https://www.meti.go.jp/english/rss/meti_news.rss",),
        "allowed_with_disallows", "meti_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 METI 官方 RSS；遵守经产省使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/english/rss/", "/english/press/", "/policy/"),
    ),
    "customs.go.kr": VerifiedSourceProfile(
        "韩国", ("en", "ko"),
        ("https://www.customs.go.kr/english/rss/rss.do",),
        "allowed_with_disallows", "korea_customs_terms_with_exceptions", 2,
        True, False,
        "使用 Korea Customs 官方 RSS；遵守韩国海关使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/english/rss/", "/english/", "/kcus/"),
    ),
    "tid.gov.hk": VerifiedSourceProfile(
        "香港", ("en", "zh"),
        ("https://www.tid.gov.hk/english/rss/whatsnew.xml",),
        "allowed_with_disallows", "hk_government_public_information", 2,
        True, False,
        "使用香港工贸署官方 RSS；遵守香港政府公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/english/rss/", "/english/about/", "/english/trade_related/"),
    ),
    "customs.gov.sg": VerifiedSourceProfile(
        "新加坡", ("en",),
        ("https://www.customs.gov.sg/rss.xml",),
        "allowed_with_disallows", "singapore_government_open_data", 2,
        True, False,
        "使用 Singapore Customs 官方 RSS；遵守新加坡政府开放数据许可，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/newsroom", "/legislation", "/businesses"),
    ),
    "dfat.gov.au": VerifiedSourceProfile(
        "澳大利亚", ("en",),
        ("https://www.dfat.gov.au/news/rss",),
        "allowed_with_disallows", "australian_government_terms_with_exceptions", 2,
        True, False,
        "使用 DFAT 官方 RSS；遵守澳大利亚政府使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/news/", "/trade/", "/sanctions/", "/publications/"),
    ),
    "mfat.govt.nz": VerifiedSourceProfile(
        "新西兰", ("en",),
        ("https://www.mfat.govt.nz/en/trade/rss",),
        "allowed_with_disallows", "nz_government_open_licence", 2,
        True, False,
        "使用 MFAT 官方 RSS；遵守新西兰政府开放许可，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/en/trade/", "/en/news/", "/en/release/"),
    ),
    "eec.eaeunion.org": VerifiedSourceProfile(
        "欧亚经济联盟", ("en", "ru"),
        ("https://eec.eaeunion.org/en/rss/",),
        "allowed_with_disallows", "eaeu_public_information_with_exceptions", 3,
        True, False,
        "使用 EAEU 官方 RSS；遵守欧亚经济委员会使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/en/rss/", "/en/news/", "/en/legal-acts/", "/en/main/"),
    ),
    "globaltradealert.org": VerifiedSourceProfile(
        "全球", ("en",),
        ("https://www.globaltradealert.org/rss.xml",),
        "allowed_with_disallows", "gta_terms_of_use_with_exceptions", 3,
        True, False,
        "使用 Global Trade Alert 官方 RSS；遵守 GTA 使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/intervention/", "/data/", "/about/"),
    ),
    "epingalert.org": VerifiedSourceProfile(
        "全球", ("en", "fr", "es"),
        ("https://epingalert.org/en",),
        "allowed_with_disallows", "wto_public_information_with_exceptions", 2,
        True, False,
        "使用 WTO ePing 官方 API；遵守 WTO 公共信息使用条款，不抓取搜索和账户路径。",
        ("official", "web_scrape"), ("/en", "/api/", "/notifications/"),
    ),
    "eur-lex.europa.eu": VerifiedSourceProfile(
        "欧盟", ("en", "fr", "de", "multi"),
        ("https://eur-lex.europa.eu/",),
        "allowed_with_disallows", "eu_open_data_licence", 2,
        True, False,
        "使用 EUR-Lex 官方 API；遵守欧盟开放数据许可，不抓取搜索和账户路径。",
        ("official", "json_api", "web_scrape"), ("/legal-content/", "/collection/", "/home/"),
    ),
    "fta.mofcom.gov.cn": VerifiedSourceProfile(
        "中国", ("zh", "en"),
        ("http://fta.mofcom.gov.cn/",),
        "allowed", "chinese_government_public_information", 2,
        True, False,
        "使用商务部自贸区服务网公开信息；遵守中国政府公共信息使用条款。",
        ("web_scrape", "official"), ("/", "/fta/", "/list/"),
    ),
    "customs.gov.cn": VerifiedSourceProfile(
        "中国", ("zh",),
        ("http://www.customs.gov.cn/",),
        "allowed", "chinese_government_public_information", 2,
        True, False,
        "使用海关总署公开信息；遵守中国政府公共信息使用条款。",
        ("web_scrape", "official"), ("/customs/", "/publish/", "/302249/", "/302266/"),
    ),
    "mofcom.gov.cn": VerifiedSourceProfile(
        "中国", ("zh",),
        ("http://www.mofcom.gov.cn/",),
        "allowed", "chinese_government_public_information", 2,
        True, False,
        "使用商务部公开信息；遵守中国政府公共信息使用条款。",
        ("web_scrape", "official"), ("/article/", "/zwgk/", "/bnjg/"),
    ),
    "imf.org": VerifiedSourceProfile(
        "全球", ("en",),
        ("https://www.imf.org/en/Research/commodity-prices",),
        "allowed_with_disallows", "imf_public_information_with_exceptions", 2,
        True, False,
        "使用 IMF 公开商品价格数据；遵守 IMF 使用条款，不抓取搜索和账户路径。",
        ("web_scrape", "official"), ("/en/Research/", "/en/News/", "/en/Publications/"),
    ),
    "fao.org": VerifiedSourceProfile(
        "全球", ("en", "fr", "es", "zh"),
        ("https://www.fao.org/worldfoodsituation/foodpricesindex/en/",),
        "allowed_with_disallows", "fao_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 FAO 公开食品价格指数数据；遵守 FAO 使用条款，不抓取搜索和账户路径。",
        ("web_scrape", "official"), ("/worldfoodsituation/", "/newsroom/", "/markets-and-prices/"),
    ),
    "ecb.europa.eu": VerifiedSourceProfile(
        "欧盟", ("en", "de", "fr"),
        ("https://www.ecb.europa.eu/rss/press.html",),
        "allowed_with_disallows", "ecb_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 ECB 官方 RSS；遵守欧洲央行使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss/", "/press/", "/pub/", "/shared/"),
    ),
    "trade.gov": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://www.trade.gov/rss.xml",),
        "allowed_with_disallows", "us_government_publication_with_exceptions", 2,
        True, False,
        "使用 US ITA 官方 RSS；遵守美国公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/news", "/export-controls", "/trade-data"),
    ),
    "ftc.gov": VerifiedSourceProfile(
        "美国", ("en",),
        ("https://www.ftc.gov/feeds/press-releases.xml",),
        "allowed_with_disallows", "us_government_publication_with_exceptions", 2,
        True, False,
        "使用 FTC 官方 RSS；遵守美国公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/feeds/", "/news-events/", "/legal-library/"),
    ),
    "reutersagency.com": VerifiedSourceProfile(
        "全球", ("en",),
        ("https://www.reutersagency.com/feed/",),
        "allowed_with_disallows", "reuters_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 Reuters Agency RSS feed；遵守路透社使用条款，不抓取搜索和账户路径。",
        ("rss",), ("/feed/", "/?best-topics=", "/?post_type="),
    ),
    "brics-info.org": VerifiedSourceProfile(
        "全球", ("en", "ru"),
        ("https://www.brics-info.org/rss.xml",),
        "allowed", "brics_public_information", 3,
        True, False,
        "使用 BRICS 信息门户 RSS；遵守 BRICS 公共信息使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/rss", "/news", "/documents", "/events"),
    ),
    "documents.worldbank.org": VerifiedSourceProfile(
        "全球", ("en", "fr", "es", "ar", "zh"),
        ("https://documents.worldbank.org/en/rss",),
        "allowed_with_disallows", "world_bank_terms_of_use_with_exceptions", 2,
        True, False,
        "使用 World Bank Documents RSS；遵守世界银行使用条款，不抓取搜索和账户路径。",
        ("rss", "web_scrape"), ("/en/rss", "/en/document/", "/curated/en/"),
    ),
})


def match_verified_profile(source: SourceConfig) -> VerifiedSourceProfile | None:
    channel = _channel(source)
    auth_config = source.auth_config if isinstance(source.auth_config, dict) else {}
    search_type = str(auth_config.get("search_type") or "tavily").casefold()
    if source.id == "tavily" and channel == "api_search" and search_type == "tavily":
        return VERIFIED_SOURCE_PROFILES["api.tavily.com"]
    collection_urls = _effective_collection_urls(source)
    if not collection_urls:
        return None
    for domain, profile in VERIFIED_SOURCE_PROFILES.items():
        if domain == "api.tavily.com" and search_type != "tavily":
            continue
        if channel not in profile.allowed_channels:
            continue
        if all(_url_matches(value, domain, profile) for value in collection_urls):
            return profile
    return None


def _effective_collection_urls(source: SourceConfig) -> tuple[str, ...]:
    """Resolve every address field that can influence the connector target."""
    base_url = str(source.base_url or "").strip()
    endpoint = str(source.api_endpoint or "").strip()
    if endpoint and base_url:
        try:
            endpoint_is_absolute = bool(urlsplit(endpoint).scheme)
        except ValueError:
            endpoint_is_absolute = True
        if not endpoint_is_absolute:
            endpoint = urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))
    return tuple(dict.fromkeys(value for value in (base_url, endpoint) if value))


def reconcile_verified_source_profiles(db: Session) -> list[str]:
    """Apply profiles only to legacy-unverified rows; preserve user decisions."""
    updated: tuple[str, ...] = ()
    for source in db.query(SourceConfig).all():
        verification = str(source.verification_status or "").strip().casefold()
        if verification not in {"", "legacy_unverified"}:
            continue
        profile = match_verified_profile(source)
        if profile is None:
            continue
        source.verification_status = "verified_2026_08_04"
        source.discovery_urls = list(profile.discovery_urls)
        source.robots_status = profile.robots_status
        source.terms_status = profile.terms_status
        source.llm_ingest_allowed = profile.llm_ingest_allowed
        source.origin_resolution_required = profile.origin_resolution_required
        source.crawl_delay_seconds = profile.crawl_delay_seconds
        source.verified_at = datetime.now(timezone.utc)
        source.languages = _merge_values(source.languages, profile.languages)
        source.country_focus = _merge_values(source.country_focus, (profile.country,))
        source.compliance_note = _merge_note(source.compliance_note, profile.note)
        updated = (*updated, source.id)
    db.commit()
    return list(updated)


def _host(value: str | None) -> str:
    try:
        return (urlsplit(value or "").hostname or "").casefold()
    except ValueError:
        return ""


def _channel(source: SourceConfig) -> str:
    value = source.channel.value if hasattr(source.channel, "value") else source.channel
    return str(value or "").casefold()


def _url_matches(
    value: str, domain: str, profile: VerifiedSourceProfile,
) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    if parsed.scheme.casefold() != "https":
        return False
    if host != domain and not host.endswith(f".{domain}"):
        return False
    path = parsed.path or "/"
    return any(path.startswith(prefix) for prefix in profile.allowed_path_prefixes)


def _merge_values(existing: object, additions: tuple[str, ...]) -> list[str]:
    current = existing if isinstance(existing, list) else []
    return list(dict.fromkeys([*(str(value) for value in current if value), *additions]))


def _merge_note(existing: str | None, note: str) -> str:
    current = (existing or "").strip()
    if not current:
        return note
    return current if note in current else f"{current}\n{note}"


__all__ = [
    "VERIFIED_SOURCE_PROFILES", "VerifiedSourceProfile",
    "match_verified_profile", "reconcile_verified_source_profiles",
]
