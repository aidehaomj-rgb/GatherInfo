import { ConfirmDialog } from "./shared/ConfirmDialog";
import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Edit3, CheckCircle, Eye, ExternalLink, Settings, Zap, Search, X, ChevronRight, ChevronDown, FolderTree, List } from "lucide-react";
import { fetchSources, createSource, deleteSource, updateSource, validateSource, fetchConnectors } from "../api";
import type { Source, ConnectorInfo } from "../types";

export function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Source | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [initialLoad, setInitialLoad] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);
  const [sourceTab, setSourceTab] = useState<"configured" | "standby">("configured");
  const [sourceSearch, setSourceSearch] = useState("");
  const [groupView, setGroupView] = useState<"grouped" | "flat">("grouped");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const [srcs, cs] = await Promise.all([fetchSources(), fetchConnectors()]);
      setSources(srcs);
      setConnectors(cs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
      setInitialLoad(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: `删除信息源 "${id}"？这将同时删除其采集的所有条目。` });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try { await deleteSource(id); setSources((p) => p.filter((s) => s.id !== id)); }
    catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
    setConfirmDelete(null);
  };

  const handleValidate = async (id: string) => {
    try {
      const r = await validateSource(id);
      alert(r.valid ? "连接成功" : `连接失败: ${r.error ?? "未知错误"}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "验证失败");
    }
  };

  const visibleSources = sources
    .filter((s) => sourceTab === "configured" ? s.is_configured : !s.is_configured)
    .filter((s) => matchesSourceSearch(s, sourceSearch));

  const renderSourceCard = (s: Source) => (
    <article key={s.id} className="card-item card-item--compact">
      <div className="card-item-header">
        <div className="card-item-title">
          <h4>
            {s.name}
            {s.homepage_url && (
              <a href={s.homepage_url} target="_blank" rel="noreferrer" className="source-home-link" title={`打开官网 / 购买服务: ${s.homepage_url}`}>
                <ExternalLink size={12} /> 官网
              </a>
            )}
          </h4>
          <span className="text-muted small">{s.id} · {s.channel}</span>
        </div>
        <div className="card-item-actions">
          <span className={`badge ${s.is_configured ? (s.is_active ? "badge--green" : "badge--gray") : "badge--yellow"}`}>
            {s.is_configured ? (s.is_active ? "活跃" : "停用") : "待配置"}
          </span>
          {!s.is_configured && s.api_key && <span className="badge badge--blue" style={{ marginLeft: 4 }}>已填Key</span>}
        </div>
      </div>
      <div className="card-item-meta card-item-meta--compact">
        <span className="meta-inline"><strong>地址:</strong> <code>{s.base_url || s.api_endpoint || "-"}</code></span>
        <span className="meta-inline"><strong>语言:</strong> {(s.languages ?? []).join(", ") || "any"}</span>
        <span className="meta-inline"><strong>关键词:</strong> {(s.default_keywords ?? []).join(", ") || "无"}</span>
        <span className="meta-inline text-muted">采集 {s.items_collected} 条{s.last_error && <span className="text-red"> · 错误: {s.last_error}</span>}</span>
      </div>
      <div className="card-item-footer">
        {s.is_configured ? (
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => handleValidate(s.id)}>
            <CheckCircle size={12} /> 验证连接
          </button>
        ) : (
          <button type="button" className="btn btn-sm btn-accent" onClick={() => setEditing(s)}>
            <Settings size={12} /> 配置并启用
          </button>
        )}
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(s)}>
          <Edit3 size={12} /> 编辑
        </button>
        <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(s.id)}>
          <Trash2 size={12} /> 删除
        </button>
      </div>
    </article>
  );

  const toggleGroup = (key: string) =>
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });

  // Build hierarchical grouping: L1 (default_categories[0]) -> L2 (default_categories[1])
  type GroupNode = { l1: string; l2: string; sources: Source[] };
  const groupByHierarchy = (srcs: Source[]) => {
    const tree: Record<string, Record<string, Source[]>> = {};
    for (const s of srcs) {
      const cats = s.default_categories ?? [];
      const l1 = cats[0] || "未分类";
      const l2 = cats[1] || "—";
      if (!tree[l1]) tree[l1] = {};
      if (!tree[l1][l2]) tree[l1][l2] = [];
      tree[l1][l2].push(s);
    }
    return tree;
  };
  const groupedTree = groupByHierarchy(visibleSources);

  if (initialLoad) return <div className="loading">加载信息源...</div>;
  if (loading) return null;

  return (
    <div className="page">
      {error && <div className="error-banner">{error} <button type="button" className="btn btn-sm btn-ghost" onClick={() => setError(null)} style={{ marginLeft: 8 }}>×</button></div>}
      <div className="page-header">
        <div>
          <h2>信息源管理</h2>
          <p className="text-muted">管理采集渠道：搜索API、网页抓取、RSS、官方API、通用JSON API等</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> 新建信息源
        </button>
      </div>

      <div className="connector-list">
        <h4>可用连接器</h4>
        <div className="chip-row">
          {connectors.map((c) => (
            <span key={c.channel} className="chip chip--blue" title={c.description}>{c.channel}</span>
          ))}
        </div>
      </div>

      {/* Source classification tabs */}
      <div className="segmented-control" style={{ marginBottom: 16 }}>
        <button
          type="button"
          className={`seg-btn ${sourceTab === "configured" ? "seg-btn--active" : ""}`}
          onClick={() => setSourceTab("configured")}
        >
          <Zap size={12} /> 已配置可用 ({sources.filter(s => s.is_configured).length})
        </button>
        <button
          type="button"
          className={`seg-btn ${sourceTab === "standby" ? "seg-btn--active" : ""}`}
          onClick={() => setSourceTab("standby")}
        >
          <Settings size={12} /> 备用未配置 ({sources.filter(s => !s.is_configured).length})
        </button>
      </div>

      <div className="search-bar source-search-bar">
        <div className="search-input-wrapper">
          <Search size={14} className="search-icon" />
          <input
            className="search-input"
            value={sourceSearch}
            onChange={(e) => setSourceSearch(e.target.value)}
            placeholder="搜索信息源名称、ID、渠道、地址、关键词"
          />
          {sourceSearch && (
            <button
              type="button"
              className="btn-icon"
              title="清空搜索"
              onClick={() => setSourceSearch("")}
            >
              <X size={14} />
            </button>
          )}
        </div>
        <span className="text-muted small source-search-count">
          {sourceSearch.trim() ? `匹配 ${visibleSources.length} / ${sources.length}` : `当前 ${visibleSources.length} 个`}
        </span>
      </div>

      {/* View mode toggle */}
      <div className="segmented-control" style={{ marginBottom: 12 }}>
        <button type="button" className={`seg-btn ${groupView === "grouped" ? "seg-btn--active" : ""}`} onClick={() => setGroupView("grouped")}>
          <FolderTree size={12} /> 分层分组
        </button>
        <button type="button" className={`seg-btn ${groupView === "flat" ? "seg-btn--active" : ""}`} onClick={() => setGroupView("flat")}>
          <List size={12} /> 平铺列表
        </button>
      </div>

      <div className="card-list">
        {groupView === "flat" && visibleSources.map((s) => renderSourceCard(s))}
        {groupView === "grouped" && Object.entries(groupedTree).map(([l1, l2map]) => {
          const l1Count = Object.values(l2map).reduce((n, arr) => n + arr.length, 0);
          const l1Collapsed = collapsedGroups.has(`L1:${l1}`);
          return (
            <div key={`L1:${l1}`} className="source-group-l1" style={{ marginBottom: 16 }}>
              <div
                className="source-group-header"
                onClick={() => toggleGroup(`L1:${l1}`)}
                style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", padding: "8px 10px", background: "var(--surface-elevated)", border: "1px solid var(--line)", borderRadius: "var(--radius)", marginBottom: 8 }}
              >
                {l1Collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                <strong style={{ fontSize: "0.9rem" }}>{l1}</strong>
                <span className="text-muted small">({l1Count})</span>
              </div>
              {!l1Collapsed && Object.entries(l2map).map(([l2, arr]) => {
                const l2Key = `L1:${l1}|L2:${l2}`;
                const l2Collapsed = collapsedGroups.has(l2Key);
                return (
                  <div key={l2Key} style={{ marginLeft: 16, marginBottom: 10 }}>
                    <div
                      className="source-group-header"
                      onClick={() => toggleGroup(l2Key)}
                      style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", padding: "6px 8px", borderBottom: "1px solid var(--line-light)", marginBottom: 6 }}
                    >
                      {l2Collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
                      <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>{l2}</span>
                      <span className="text-muted small">({arr.length})</span>
                    </div>
                    {!l2Collapsed && arr.map((s) => renderSourceCard(s))}
                  </div>
                );
              })}
            </div>
          );
        })}
        {visibleSources.length === 0 && (
          <div className="empty-state">没有找到匹配的信息源</div>
        )}
      </div>

      {(showCreate || editing) && (
        <SourceForm
          key={editing?.id ?? "create"}
          source={editing}
          connectors={connectors}
          onSave={async (data) => {
            if (editing) { await updateSource(editing.id, data); }
            else { await createSource(data as Source); }
            setShowCreate(false); setEditing(null); await load();
          }}
          onClose={() => { setShowCreate(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

function matchesSourceSearch(source: Source, query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    source.id,
    source.name,
    source.description,
    source.channel,
    source.base_url,
    source.api_endpoint,
    source.homepage_url,
    ...(source.default_keywords ?? []),
    ...(source.default_categories ?? []),
    ...(source.languages ?? []),
    ...(source.country_focus ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return q.split(/\s+/).every((part) => haystack.includes(part));
}

// ── Source form ──────────────────────────────────────────────────────────────

type SourceFormProps = {
  source: Source | null;
  connectors: ConnectorInfo[];
  onSave: (data: Partial<Source>) => Promise<void>;
  onClose: () => void;
};

function SourceForm({ source, connectors, onSave, onClose }: SourceFormProps) {
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState(source?.name ?? "");
  const [desc, setDesc] = useState(source?.description ?? "");
  const [channel, setChannel] = useState(source?.channel ?? connectors[0]?.channel ?? "api_search");
  const [baseUrl, setBaseUrl] = useState(source?.base_url ?? "");
  const [apiEndpoint, setApiEndpoint] = useState(source?.api_endpoint ?? "");
  const [homepageUrl, setHomepageUrl] = useState(source?.homepage_url ?? "");
  const [kw, setKw] = useState((source?.default_keywords ?? []).join(", "));
  const [langs, setLangs] = useState((source?.languages ?? []).join(", "));
  const [rps, setRps] = useState(source?.rate_limit_rps != null ? String(source.rate_limit_rps) : "1.0");
  const [showKey, setShowKey] = useState(false);
  const [apiKey, setApiKey] = useState(source?.api_key ?? "");
  const [authConfig, setAuthConfig] = useState(
    source?.auth_config ? JSON.stringify(source.auth_config, null, 2) : ""
  );
  const [authConfigError, setAuthConfigError] = useState<string | null>(null);

  const meta = connectors.find((c) => c.channel === channel);
  const required = meta?.required_fields ?? [];
  const optional = meta?.optional_fields ?? [];
  const isUsed = (f: string) => required.includes(f) || optional.includes(f);
  // Placeholder: required→提示填写, optional→可留空, otherwise→不需填写
  const ph = (f: string, hint: string) =>
    required.includes(f) ? hint : optional.includes(f) ? `(可选) ${hint}` : "不需填写";

  // Auto-fill connection defaults when the channel changes (only for empty/new sources).
  const handleChannelChange = (next: string) => {
    setChannel(next);
    const m = connectors.find((c) => c.channel === next);
    if (!m) return;
    if (!source) {
      if (m.default_base_url != null) setBaseUrl(m.default_base_url || "");
      if (m.default_api_endpoint != null) setApiEndpoint(m.default_api_endpoint || "");
      if (m.homepage_hint && !homepageUrl) setHomepageUrl(m.homepage_hint);
    }
  };

  // Tolerant split: accept both English/Chinese commas
  const splitList = (v: string) => v.split(/[,，]/).map((s) => s.trim()).filter(Boolean);

  const handleSave = async () => {
    let parsedAuth: Record<string, unknown> | null = null;
    if (authConfig.trim()) {
      try { parsedAuth = JSON.parse(authConfig); setAuthConfigError(null); }
      catch { setAuthConfigError("auth_config 不是合法 JSON"); return; }
    }
    setSaving(true);
    try {
      await onSave({
        name, description: desc || null,
        channel, is_active: true,
        base_url: baseUrl || null,
        api_endpoint: apiEndpoint || null,
        homepage_url: homepageUrl || null,
        default_keywords: kw ? splitList(kw) : null,
        api_key: apiKey || null,
        auth_config: parsedAuth,
        languages: langs ? splitList(langs) : null,
        rate_limit_rps: parseFloat(rps) || 1,
      });
    } catch (e) { alert(e instanceof Error ? e.message : "保存失败"); }
    setSaving(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--source" onClick={(e) => e.stopPropagation()}>
        <h3>{source ? "编辑信息源" : "新建信息源"}</h3>
        <div className="form-grid">
          {source && (
            <label>ID <span className="chip chip--inline">{source.id}</span></label>
          )}
          <label>名称 <input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>渠道
            <select value={channel} onChange={(e) => handleChannelChange(e.target.value)}>
              {connectors.map((c) => <option key={c.channel} value={c.channel}>{c.channel} — {c.description}</option>)}
            </select>
            {meta && (
              <span className="text-muted small">
                必填: {required.length ? required.join(", ") : "无"}
                {optional.length > 0 && <> · 可选: {optional.join(", ")}</>}
              </span>
            )}
          </label>
          <label>速率 (req/s) <input type="number" step="0.1" value={rps} onChange={(e) => setRps(e.target.value)} /></label>
          <label>API Key
            <div className="input-with-icon">
              <input type={showKey ? "text" : "password"} value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                placeholder={ph("api_key", "sk-...")} disabled={!isUsed("api_key")} />
              <button type="button" className="btn-icon" onClick={() => setShowKey(!showKey)}><Eye size={14} /></button>
            </div>
            <span className="text-muted small">{isUsed("api_key") ? "留空则使用环境变量" : "该渠道不需要 API Key"}</span>
          </label>
          <label className="span-2">描述 <input value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
          <label>Base URL <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={ph("base_url", "http://...")} disabled={!isUsed("base_url")} /></label>
          <label>API Endpoint <input value={apiEndpoint} onChange={(e) => setApiEndpoint(e.target.value)}
            placeholder={ph("api_endpoint", "/search")} disabled={!isUsed("api_endpoint")} /></label>
          <label className="span-2">官网主页 (方便购买/订阅服务)
            <input value={homepageUrl} onChange={(e) => setHomepageUrl(e.target.value)} placeholder="https://..." />
          </label>
          <label>关键词 (逗号分隔，中英文逗号均可) <input value={kw} onChange={(e) => setKw(e.target.value)} /></label>
          <label>语言 (逗号分隔) <input value={langs} onChange={(e) => setLangs(e.target.value)} placeholder="zh, en" /></label>
          {isUsed("auth_config") && (
            <label className="span-2">高级配置 auth_config (JSON：认证方式、字段映射等)
              <textarea className="auth-config-editor" value={authConfig} rows={8}
                onChange={(e) => setAuthConfig(e.target.value)}
                placeholder={'{\n  "method": "GET",\n  "auth": "query",\n  "auth_param": "apiKey",\n  "keyword_param": "q",\n  "items_path": "articles",\n  "fields": { "title": "title", "url": "url" }\n}'} />
              {authConfigError && <span className="text-red small">{authConfigError}</span>}
            </label>
          )}
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving || !name}>
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
