"""GatherInfo local MCP server (stdio transport, MCP 2024-11-05)."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = os.getenv("GATHERINFO_API_URL", "http://127.0.0.1:8110/api/v1").rstrip("/")

TOOLS = [
    {"name": "list_topics", "description": "列出GatherInfo采集主题", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "start_research", "description": "启动多轮公开互联网研究任务，自动搜索、读取、审核并入库", "inputSchema": {"type": "object", "required": ["topic_id", "objective"], "properties": {"topic_id": {"type": "string"}, "objective": {"type": "string"}, "model_id": {"type": "string"}, "max_rounds": {"type": "integer", "minimum": 1, "maximum": 6, "default": 3}, "target_items": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10}}}},
    {"name": "get_research", "description": "查询研究任务进度、轮次和结果数量", "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}}},
    {"name": "get_research_items", "description": "读取研究任务审核入库后的证据条目", "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}}},
    {"name": "resume_research", "description": "恢复失败任务或对未通过验收的任务追加轮次", "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}}},
    {"name": "search_items", "description": "查询GatherInfo已有信息条目", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "topic_id": {"type": "string"}, "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}}},
    {"name": "open_item", "description": "读取单条信息的完整正文、来源和审核元数据", "inputSchema": {"type": "object", "required": ["item_id"], "properties": {"item_id": {"type": "string"}}}},
    {"name": "research_entity", "description": "提取案件中的企业、人员、集装箱、船舶、航班、案号和提单号，并生成深挖查询", "inputSchema": {"type": "object", "required": ["item_id"], "properties": {"item_id": {"type": "string"}}}},
    {"name": "read_document", "description": "读取HTML、动态网页、PDF或图片OCR；支持点击、填表、按键、等待、下载、截图和页面内查找", "inputSchema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}, "render": {"type": "boolean", "default": False}, "follow_links": {"type": "integer", "minimum": 0, "maximum": 3, "default": 0}, "actions": {"type": "array", "items": {"type": "object"}}, "find_text": {"type": "string"}}}},
    {"name": "extract_document_entities", "description": "使用规则和大模型从已入库案件提取结构化实体", "inputSchema": {"type": "object", "required": ["item_id"], "properties": {"item_id": {"type": "string"}, "model_id": {"type": "string"}}}},
    {"name": "run_tool_research", "description": "运行有步数上限的模型工具研究循环，读取网页、PDF、图片并形成有URL依据的结论", "inputSchema": {"type": "object", "required": ["objective"], "properties": {"objective": {"type": "string"}, "model_id": {"type": "string"}, "max_steps": {"type": "integer", "minimum": 1, "maximum": 10, "default": 6}}}},
    {"name": "list_research_cases", "description": "查询规范化案件图谱及实体、来源统计", "inputSchema": {"type": "object", "properties": {"topic_id": {"type": "string"}, "limit": {"type": "integer", "default": 100}}}},
    {"name": "open_research_case", "description": "读取案件图谱中的实体关系和独立证据来源", "inputSchema": {"type": "object", "required": ["case_id"], "properties": {"case_id": {"type": "string"}}}},
    {"name": "broad_web_search", "description": "免密钥广泛搜索公开网页，补充Tavily和百度未覆盖的页面", "inputSchema": {"type": "object", "required": ["queries"], "properties": {"queries": {"type": "array", "items": {"type": "string"}, "maxItems": 20}, "max_items": {"type": "integer", "default": 30, "maximum": 100}}}},
    {"name": "multilingual_news_search", "description": "并行搜索Google News与Bing News RSS；输入不同语种查询以发现地方媒体和官方公告", "inputSchema": {"type": "object", "required": ["queries"], "properties": {"queries": {"type": "array", "items": {"type": "string"}, "maxItems": 20}, "max_items": {"type": "integer", "default": 30, "maximum": 100}}}},
    {"name": "case_image_search", "description": "搜索案件图片及来源页，返回原图和缩略图地址，可用于查找集装箱号、车牌和运输工具", "inputSchema": {"type": "object", "required": ["queries"], "properties": {"queries": {"type": "array", "items": {"type": "string"}, "maxItems": 20}, "max_items": {"type": "integer", "default": 20, "maximum": 100}}}},
    {"name": "official_pdf_search", "description": "定向发现PDF公告、扣押清单、司法文书和执法附件", "inputSchema": {"type": "object", "required": ["queries"], "properties": {"queries": {"type": "array", "items": {"type": "string"}, "maxItems": 20}, "max_items": {"type": "integer", "default": 30, "maximum": 100}}}},
    {"name": "resolve_supply_chain_entity", "description": "核验供应链候选中的进口主体与军工供应商是否为同一或关联法定主体", "inputSchema": {"type": "object", "required": ["case_id", "shipment_id"], "properties": {"case_id": {"type": "string"}, "shipment_id": {"type": "string"}}}},
    {"name": "search_supply_chain_contracts", "description": "定向搜索军工合同号、采购机关、承包商与官方PDF原始来源", "inputSchema": {"type": "object", "required": ["company"], "properties": {"company": {"type": "string"}, "program": {"type": "string"}, "reference": {"type": "string"}, "max_items": {"type": "integer", "default": 20, "maximum": 50}}}},
    {"name": "search_supply_chain_trade_records", "description": "搜索出口商、进口商、产品、提单号和贸易批次证据", "inputSchema": {"type": "object", "required": ["importer"], "properties": {"importer": {"type": "string"}, "exporter": {"type": "string"}, "product": {"type": "string"}, "bill_no": {"type": "string"}, "max_items": {"type": "integer", "default": 20, "maximum": 50}}}},
    {"name": "deep_search_china_trade_records", "description": "深度检索目标企业从中国进口的提单、供应商、产品、地址与贸易批次，优先检索2026年及专业贸易数据索引", "inputSchema": {"type": "object", "required": ["importer"], "properties": {"importer": {"type": "string"}, "aliases": {"type": "array", "items": {"type": "string"}}, "addresses": {"type": "array", "items": {"type": "string"}}, "products": {"type": "array", "items": {"type": "string"}}, "year": {"type": "integer", "default": 2026}, "max_items": {"type": "integer", "default": 40, "maximum": 100}}}},
    {"name": "search_supply_chain_part_numbers", "description": "搜索并核对P/N、NSN、图号、型号及替代料号", "inputSchema": {"type": "object", "required": ["part_numbers"], "properties": {"part_numbers": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 20}, "company": {"type": "string"}, "max_items": {"type": "integer", "default": 20, "maximum": 50}}}},
    {"name": "verify_supply_chain_end_use", "description": "检索军售案、BOM、交付文件和最终用户，核验候选链最终用途", "inputSchema": {"type": "object", "required": ["company", "program"], "properties": {"company": {"type": "string"}, "program": {"type": "string"}, "product": {"type": "string"}, "max_items": {"type": "integer", "default": 20, "maximum": 50}}}},
]


def request(method: str, path: str, body: dict | None = None) -> Any:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8", "replace")) from exc


def call_tool(name: str, args: dict) -> Any:
    if name == "list_topics": return request("GET", "/topics")
    if name == "start_research":
        return request("POST", "/research/jobs", {"topic_id": args["topic_id"], "objective": args["objective"], "model_id": args.get("model_id"), "max_rounds": args.get("max_rounds", 3), "target_items": args.get("target_items", 10)})
    if name == "get_research": return request("GET", f"/research/jobs/{args['job_id']}")
    if name == "get_research_items": return request("GET", f"/research/jobs/{args['job_id']}/items")
    if name == "resume_research": return request("POST", f"/research/jobs/{args['job_id']}/resume", {})
    if name == "open_item": return request("GET", f"/items/{args['item_id']}")
    if name == "research_entity": return request("POST", f"/research/items/{args['item_id']}/entities", {})
    if name == "read_document": return request("POST", "/research/documents/read", {"url": args["url"], "render": args.get("render", False), "follow_links": args.get("follow_links", 0), "actions": args.get("actions", []), "find_text": args.get("find_text")})
    if name == "extract_document_entities":
        suffix = urllib.parse.urlencode({"model_id": args.get("model_id")}) if args.get("model_id") else ""
        return request("POST", f"/research/items/{args['item_id']}/entities/llm" + ("?" + suffix if suffix else ""), {})
    if name == "run_tool_research": return request("POST", "/research/agent/run", {"objective": args["objective"], "model_id": args.get("model_id"), "max_steps": args.get("max_steps", 6)})
    if name == "list_research_cases":
        params = urllib.parse.urlencode({k: v for k, v in {"topic_id": args.get("topic_id"), "limit": args.get("limit", 100)}.items() if v})
        return request("GET", "/research/graph/cases?" + params)
    if name == "open_research_case": return request("GET", f"/research/graph/cases/{args['case_id']}")
    if name in {"broad_web_search", "multilingual_news_search", "case_image_search", "official_pdf_search"}:
        mode = {"broad_web_search": "web", "multilingual_news_search": "news", "case_image_search": "images", "official_pdf_search": "pdf"}[name]
        return request("POST", "/research/discovery/search", {"queries": args["queries"], "mode": mode, "max_items": args.get("max_items", 30)})
    if name == "resolve_supply_chain_entity":
        return request("POST", "/supply-chain/mcp/evaluate", {"case_id": args["case_id"], "shipment_id": args["shipment_id"], "tools": [name]})
    if name == "search_supply_chain_contracts":
        query = " ".join(filter(None, [args["company"], args.get("program"), args.get("reference"), "contract award official filetype:pdf"]))
        return request("POST", "/research/discovery/search", {"queries": [query], "mode": "pdf", "max_items": args.get("max_items", 20)})
    if name == "search_supply_chain_trade_records":
        query = " ".join(filter(None, [args.get("exporter"), args["importer"], args.get("product"), args.get("bill_no"), "shipment bill of lading import"]))
        return request("POST", "/research/discovery/search", {"queries": [query], "mode": "web", "max_items": args.get("max_items", 20)})
    if name == "deep_search_china_trade_records":
        importer = args["importer"]
        year = args.get("year", 2026)
        names = [importer, *(args.get("aliases") or [])][:5]
        products = (args.get("products") or [""])[:5]
        addresses = (args.get("addresses") or [])[:3]
        queries = []
        for company in names:
            queries.extend([
                f'"{company}" {year} China supplier shipment bill of lading',
                f'"{company}" imports from China customs trade data',
                f'site:importyeti.com "{company}" supplier',
                f'site:panjiva.com "{company}" shipment',
                f'site:importgenius.com "{company}" imports',
                f'site:volza.com "{company}" import',
            ])
            queries.extend(f'"{company}" "{product}" China shipment' for product in products if product)
        queries.extend(f'"{address}" importer China shipment' for address in addresses)
        limit = args.get("max_items", 40)
        web = request("POST", "/research/discovery/search", {"queries": queries[:30], "mode": "web", "max_items": limit})
        news = request("POST", "/research/discovery/search", {"queries": queries[:30], "mode": "news", "max_items": limit})
        raw_items = {item.get("url"): item for item in [*(web.get("items") or []), *(news.get("items") or [])] if item.get("url")}
        name_tokens = {
            token.casefold() for company in names
            for token in re.findall(r"[A-Za-z0-9]{4,}", company)
        }
        trade_terms = ("import", "shipment", "bill of lading", "supplier", "customs", "export")
        trade_hosts = ("importyeti.", "panjiva.", "importgenius.", "volza.")
        verified = []
        for item in raw_items.values():
            text = f"{item.get('title', '')} {item.get('summary', '')}".casefold()
            url = str(item.get("url") or "").casefold()
            company_match = any(token in text or token in url for token in name_tokens)
            trade_match = any(term in text for term in trade_terms) or any(host in url for host in trade_hosts)
            if company_match and trade_match:
                verified.append({**item, "match_basis": {"company": True, "trade_signal": True}})
        return {"tool": name, "queries": queries[:30], "raw_count": len(raw_items), "count": len(verified), "items": verified, "errors": [*(web.get("errors") or []), *(news.get("errors") or [])]}
    if name == "search_supply_chain_part_numbers":
        queries = [" ".join(filter(None, [part, args.get("company"), "part number NSN application"])) for part in args["part_numbers"]]
        return request("POST", "/research/discovery/search", {"queries": queries, "mode": "web", "max_items": args.get("max_items", 20)})
    if name == "verify_supply_chain_end_use":
        query = " ".join(filter(None, [args["company"], args["program"], args.get("product"), "end user delivery contract BOM filetype:pdf"]))
        return request("POST", "/research/discovery/search", {"queries": [query], "mode": "pdf", "max_items": args.get("max_items", 20)})
    if name == "search_items":
        params = urllib.parse.urlencode({k: v for k, v in {"q": args.get("query"), "topic_id": args.get("topic_id"), "page_size": args.get("page_size", 20)}.items() if v})
        return request("GET", "/items?" + params)
    raise ValueError(f"Unknown tool: {name}")


def reply(message: dict) -> None:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
    sys.stdout.buffer.flush()


def read_message() -> dict | None:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line: return None
        if line in (b"\r\n", b"\n"): break
        key, value = line.decode().split(":", 1); headers[key.lower()] = value.strip()
    return json.loads(sys.stdin.buffer.read(int(headers.get("content-length", "0"))))


def main() -> None:
    while (msg := read_message()) is not None:
        if "id" not in msg:
            continue
        req_id, method = msg["id"], msg.get("method")
        try:
            if method == "initialize": result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "gatherinfo", "version": "0.9.0"}}
            elif method == "tools/list": result = {"tools": TOOLS}
            elif method == "tools/call":
                value = call_tool(msg["params"]["name"], msg["params"].get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}]}
            elif method == "ping": result = {}
            else: raise ValueError(f"Unsupported method: {method}")
            reply({"jsonrpc": "2.0", "id": req_id, "result": result})
        except Exception as exc:
            reply({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}})


if __name__ == "__main__":
    main()
