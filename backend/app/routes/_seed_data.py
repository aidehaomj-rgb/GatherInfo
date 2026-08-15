
_DEFAULT_CATEGORIES = [
    {"id": "trade", "name": "贸易政策"},
    {"id": "regulation", "name": "法规与合规"},
    {"id": "security", "name": "出口管制"},
    {"id": "logistics", "name": "供应链与物流"},
    {"id": "enforcement", "name": "执法与缉私"},
    {"id": "market", "name": "市场与商品"},
]

def _default_keyword_tags(topic_id: str) -> list[dict] | None:
    mapping = {
        "global-trade": [
            {"keyword": "关税", "weight": 1.0},
            {"keyword": "贸易政策", "weight": 0.9},
            {"keyword": "tarrif", "weight": 0.9},
            {"keyword": "trade", "weight": 0.8},
            {"keyword": "RCEP", "weight": 0.7},
            {"keyword": "FTA", "weight": 0.7},
        ],
        "tech-regulations": [
            {"keyword": "电池", "weight": 1.0, "tag_id": "product:battery"},
            {"keyword": "光伏", "weight": 0.9, "tag_id": "product:solar"},
            {"keyword": "碳足迹", "weight": 0.9},
            {"keyword": "TBT", "weight": 0.8},
            {"keyword": "SPS", "weight": 0.8},
            {"keyword": "新能源汽车", "weight": 0.8},
        ],
    }
    return mapping.get(topic_id)


def _default_description_prompt(topic_id: str) -> str | None:
    mapping = {
        "global-trade": "监控全球主要经济体的贸易政策变化、关税调整和贸易协定进展。重点关注影响中国出口的措施，包括美国对华关税政策、欧盟贸易防御工具、RCEP实施进展和CPTPP扩员动向。需要采集来自官方公告、权威媒体和贸易分析机构的信息。",
        "tech-regulations": "跟踪全球技术性贸易措施的最新动态，包括TBT/SPS通报、产品标准更新、合格评定要求、碳足迹和可持续发展法规。重点关注电池、光伏、新能源汽车、半导体等战略性行业，覆盖欧盟、美国、东盟和中国等主要市场。",
    }
    return mapping.get(topic_id)


def _default_tags() -> list[dict]:
    raw = [
        ("category", "trade_policy", "贸易政策", "#2563eb"),
        ("category", "tariff", "关税税则", "#1d4ed8"),
        ("category", "smuggling", "走私缉私", "#dc2626"),
        ("category", "enforcement", "海关执法", "#b91c1c"),
        ("category", "commodity_price", "大宗价格", "#f59e0b"),
        ("category", "trade_remedy", "贸易救济", "#7c3aed"),
        ("category", "export_control", "出口管制", "#9333ea"),
        ("category", "supply_chain", "供应链", "#0891b2"),
        ("category", "compliance", "海关合规", "#0d9488"),
        ("category", "ip_protection", "知识产权", "#db2777"),
        ("region", "china", "中国", "#ef4444"),
        ("region", "usa", "美国", "#3b82f6"),
        ("region", "eu", "欧盟", "#6366f1"),
        ("region", "asean", "东盟", "#10b981"),
        ("region", "global", "全球", "#64748b"),
        ("commodity", "crude_oil", "原油", "#78350f"),
        ("commodity", "metals", "金属", "#92400e"),
        ("commodity", "grain", "粮食", "#ca8a04"),
        ("commodity", "precious_metals", "贵金属", "#eab308"),
    ]
    return [
        {"id": f"{ns}:{val}", "namespace": ns, "value": val, "label": label, "color": color}
        for (ns, val, label, color) in raw
    ]


def _default_models() -> list[dict]:
    return [
        {"id": "ollama-default", "name": "本地 Ollama", "provider": "ollama",
         "base_url": "http://localhost:11434", "model_name": "qwen3-coder-next:latest",
         "temperature": 0.7, "max_tokens": 4096, "top_p": 0.9,
         "is_default": False, "is_active": True,
         "description": "本地运行的 Ollama 模型，无需 API Key，完全离线"},
        {"id": "cc-switch-deepseek", "name": "CC Switch (DeepSeek V4 Flash)",
         "provider": "cc_switch", "base_url": "http://127.0.0.1:15721",
         "model_name": "deepseek-v4-flash", "temperature": 0.7, "max_tokens": 8192,
         "top_p": 0.9, "is_default": True, "is_active": True,
         "description": "CC Switch 代理 → DeepSeek V4 Flash，高效的中英文推理模型"},
        {"id": "deepseek-api", "name": "DeepSeek 深度求索", "provider": "openai",
         "base_url": "https://api.deepseek.com/v1", "api_key": "",
         "model_name": "deepseek-chat", "temperature": 0.7, "max_tokens": 8192,
         "top_p": 0.9, "is_default": False, "is_active": True,
         "description": "DeepSeek API，性价比极高的国产大模型，支持中英文"},
        {"id": "qwen-api", "name": "通义千问 (Qwen)", "provider": "openai",
         "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "",
         "model_name": "qwen-plus", "temperature": 0.7, "max_tokens": 8192,
         "top_p": 0.9, "is_default": False, "is_active": True,
         "description": "阿里云通义千问 API"},
        {"id": "openai-fallback", "name": "OpenAI 兼容 API", "provider": "openai",
         "base_url": "https://api.openai.com/v1", "api_key": "",
         "model_name": "gpt-4o-mini", "temperature": 0.7, "max_tokens": 4096,
         "top_p": 0.9, "is_default": False, "is_active": False,
         "description": "OpenAI 兼容 API（备用）"},
    ]


def _default_search_tools() -> list[dict]:
    return [
        {"id": "tavily-search", "name": "Tavily Web Search", "tool_type": "tavily",
         "is_active": True,
         "config_json": {"rate_limit": 0.5, "max_results": 10, "include_answer": True,
                         "languages": ["zh", "en"]},
         "api_key_ref": "TAVILY_API_KEY", "is_default": True},
        {"id": "rss-feeds", "name": "RSS 新闻订阅", "tool_type": "rss",
         "is_active": True,
         "config_json": {"timeout": 30, "max_items_per_feed": 20, "feeds": []}},
        {"id": "broad-web-search", "name": "广泛网页发现", "tool_type": "broad_web",
         "is_active": True, "config_json": {"provider": "bing_public", "max_results": 30,
         "requires_api_key": False, "capabilities": ["web", "multilingual", "official_domains"]}},
        {"id": "multilingual-news-search", "name": "多语种新闻聚合", "tool_type": "news_rss",
         "is_active": True, "config_json": {"providers": ["google_news_rss"],
         "languages": ["zh", "en", "es", "pt", "ja", "ko", "fr", "de", "it", "th", "id"],
         "requires_api_key": False}},
        {"id": "case-image-search", "name": "案件图片与图像证据搜索", "tool_type": "image_search",
         "is_active": True, "config_json": {"provider": "bing_images", "max_results": 20,
         "return_source_page": True, "return_original_image": True, "ocr_when_available": True,
         "requires_api_key": False}},
        {"id": "official-pdf-search", "name": "官方PDF与执法附件搜索", "tool_type": "pdf_search",
         "is_active": True, "config_json": {"provider": "bing_public", "filetype": "pdf",
         "targets": ["seizure_notice", "court_document", "cargo_manifest", "enforcement_attachment"],
         "requires_api_key": False}},
        {"id": "official-enforcement-index", "name": "境外官方执法站点索引", "tool_type": "official_enforcement",
         "is_active": True, "config_json": {"requires_api_key": False, "priority": "high",
         "regions": ["US", "EU", "UK", "CA", "AU", "JP", "KR", "ASEAN", "LATAM"]}},
        {"id": "gdelt-global-news", "name": "GDELT全球新闻检索", "tool_type": "gdelt",
         "is_active": True, "config_json": {"requires_api_key": False, "multilingual": True,
         "max_results": 50}},
    ]


def _default_topics() -> list[dict]:
    return [
        {"id": "global-trade", "name": "全球贸易政策", "is_active": True,
         "keywords": ["关税", "贸易政策", "贸易协定", "RCEP", "CPTPP", "FTA",
                      "tariff", "trade policy", "trade agreement"],
         "source_ids": ["wco", "ustr", "eu-eurlex", "cn-customs", "cn-mofcom",
                        "wto-eping", "fao-food-price-index", "tavily-search"],
         "schedule_cron": "0 8 * * *", "is_scheduled": True, "auto_report": True,
         "collect_window_days": 7},
        {"id": "tech-regulations", "name": "技术性贸易措施", "is_active": True,
         "keywords": ["TBT", "SPS", "技术壁垒", "电池", "光伏", "碳足迹", "新能源汽车",
                      "technical barriers", "battery regulation", "carbon footprint"],
         "source_ids": ["wto-eping", "eu-eurlex", "cn-customs",
                        "cbp-newsroom", "tavily-search"],
         "schedule_cron": "0 9 * * 1,4", "is_scheduled": True, "auto_report": True,
         "collect_window_days": 14},
        {"id": "us-defense-procurement", "name": "美国军工采购与供应链",
         "description": "监测美国国防部及下属机构的采购机会、已授合同和重要合同公告，识别军工供应商、采购产品、合同金额、履约周期及关键材料供应链线索。",
         "is_active": True,
         "keywords": [
             "rare earth", "critical mineral", "permanent magnet",
             "lithium battery", "battery cell", "defense supply chain",
             "unmanned system", "naval component", "ship pump",
             "aerospace material", "semiconductor", "tungsten",
             "gallium", "germanium",
         ],
         "synonyms": [
             "strategic materials", "defense industrial base",
             "military procurement", "contract award", "solicitation",
             "request for information", "sources sought",
         ],
         "categories": ["defense_procurement", "supply_chain"],
         "focus_countries": ["US"], "focus_languages": ["en"],
         "source_ids": [
             "usaspending-dod-awards", "sam-dod-opportunities",
             "dod-contract-announcements",
         ],
         "auto_tag_rules": [
             {"keyword": "rare earth", "tag": "关键矿产"},
             {"keyword": "critical mineral", "tag": "关键矿产"},
             {"keyword": "battery", "tag": "军用电池"},
             {"keyword": "magnet", "tag": "稀土永磁"},
             {"keyword": "unmanned", "tag": "无人系统"},
             {"keyword": "ship", "tag": "舰船装备"},
         ],
         "description_prompt": "重点提取采购机关、合同号、供应商、采购产品、合同金额、开始和结束日期、军事项目或用途。区分采购机会与已授合同，并将供应商作为后续自华进口记录反查对象。",
         "schedule_cron": "30 7 * * *", "is_scheduled": True,
         "auto_report": False, "collect_window_days": 365},
    ]


