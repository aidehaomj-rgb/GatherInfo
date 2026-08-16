import { useEffect, useMemo, useState } from "react";
import {
  Bot, Braces, Database, FileSearch, Globe2, Images, Languages,
  Network, RefreshCw, Search, Workflow, Wrench,
} from "lucide-react";
import { fetchMCPToolCatalog } from "../api";
import type { MCPToolCatalog, MCPToolCatalogItem } from "../types";

const categoryIcons: Record<string, typeof Wrench> = {
  "任务管理": Workflow, "任务编排": Workflow, "数据读取": Database,
  "实体研究": Network, "多模态解析": FileSearch, "智能研究": Bot,
  "案件图谱": Network, "广泛搜索": Globe2, "多语种搜索": Languages,
  "多模态搜索": Images, "附件搜索": FileSearch,
  "供应链核验": Network,
};

function ToolCard({ tool }: { tool: MCPToolCatalogItem }) {
  const Icon = categoryIcons[tool.category] || Wrench;
  const capabilities = Array.isArray(tool.config?.capabilities)
    ? tool.config?.capabilities as string[] : [];
  const languages = Array.isArray(tool.config?.languages)
    ? tool.config?.languages as string[] : [];
  return (
    <article className="mcp-tool-card">
      <header className="mcp-tool-card__header">
        <span className="mcp-tool-card__icon"><Icon size={20} /></span>
        <span className={`mcp-tool-card__status ${tool.is_active ? "is-active" : ""}`}>
          {tool.is_active ? "已启用" : "已停用"}
        </span>
      </header>
      <div className="mcp-tool-card__body">
        <span className="mcp-tool-card__category">{tool.category}</span>
        <h3>{tool.kind === "mcp" ? tool.id : tool.name}</h3>
        <p>{tool.description}</p>
      </div>
      <footer className="mcp-tool-card__footer">
        <span><Braces size={14} />{tool.kind === "mcp" ? `${tool.parameter_count || 0} 个参数` : tool.tool_type}</span>
        <span>{tool.requires_api_key ? "需密钥" : "无需密钥"}</span>
      </footer>
      {(capabilities.length > 0 || languages.length > 0) && (
        <div className="mcp-tool-card__tags">
          {capabilities.slice(0, 3).map((value) => <span key={value}>{value}</span>)}
          {languages.length > 0 && <span>{languages.length}种语言</span>}
        </div>
      )}
    </article>
  );
}

export function MCPToolsPage() {
  const [data, setData] = useState<MCPToolCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const load = () => {
    setLoading(true);
    fetchMCPToolCatalog().then(setData).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const items = useMemo(() => {
    const source = data?.mcp_tools || [];
    const needle = query.trim().toLowerCase();
    return needle ? source.filter((item) => `${item.name} ${item.id} ${item.description} ${item.category}`.toLowerCase().includes(needle)) : source;
  }, [data, query]);

  return (
    <div className="mcp-tools-page">
      <div className="page-header mcp-tools-heading">
        <div><h2>工具</h2></div>
        <button className="icon-btn" type="button" onClick={load} title="刷新工具目录"><RefreshCw size={17} /></button>
      </div>
      <div className="mcp-tools-toolbar">
        <strong>MCP工具 <span>{items.length}</span></strong>
        <label className="mcp-tool-search"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索工具" /></label>
      </div>
      {loading ? <div className="empty-state">正在读取工具目录...</div> : (
        <div className="mcp-tool-grid">{items.map((tool) => <ToolCard key={`${tool.kind}-${tool.id}`} tool={tool} />)}</div>
      )}
    </div>
  );
}
