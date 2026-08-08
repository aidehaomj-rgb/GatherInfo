import { Check, ChevronDown, ChevronsDownUp, ChevronsUpDown, Search, X, Globe, Rss, FileText, Zap, Filter } from "lucide-react";
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import type { ModelConfig, Source } from "../types";

interface SourceSelectorProps {
  sources: Source[];
  selected: string[];
  onChange: (selected: string[]) => void;
  models: ModelConfig[];
  selectedModelIds: string[];
  onModelChange: (selected: string[]) => void;
}

// ── Constants ──────────────────────────────────────────────────────────

const MODELS_GROUP_ID = "__models__";
const PAGE_SIZE = 50;

const CHANNEL_LABELS: Record<string, string> = {
  ai_research: "AI 提示采集",
  api_search: "搜索采集",
  commercial: "商业数据",
  deepweb: "深度网页",
  json_api: "数据接口",
  manual: "手工录入",
  official: "官方渠道",
  rss: "RSS 订阅",
  social: "社交媒体",
  web_scrape: "网页抓取",
};

const CHANNEL_ICONS: Record<string, typeof Globe> = {
  rss: Rss,
  web_scrape: Globe,
  official: FileText,
  api_search: Zap,
  json_api: FileText,
  ai_research: Zap,
  social: Globe,
  commercial: FileText,
  deepweb: Globe,
  manual: FileText,
};

const HEALTH_META: Record<string, { label: string; color: string }> = {
  healthy: { label: "●", color: "#22c55e" },
  degraded: { label: "●", color: "#f59e0b" },
  failed: { label: "●", color: "#ef4444" },
  unreachable: { label: "●", color: "#ef4444" },
  unknown: { label: "○", color: "#6b7280" },
};

const PRIMARY_CATEGORY_LABELS: Record<string, string> = {
  defense_procurement: "政府与军方采购",
  commodity: "商品与大宗商品",
  customs: "海关监管",
  enforcement: "执法风险",
  export_control: "出口管制",
  fta: "自由贸易协定",
  general: "综合信息",
  ip: "知识产权",
  market: "市场与产业",
  policy: "政策法规",
  price: "价格与行情",
  regulation: "监管规则",
  risk: "风险情报",
  sanction: "制裁与合规",
  search: "搜索与信息聚合",
  tbt_sps: "技术贸易措施",
  trade: "国际贸易",
  trade_remedy: "贸易救济",
  "网页·执法信息": "网页执法信息",
  "网页·热点信息": "网页热点信息",
  "社交媒体·微信公众号": "社交媒体：微信公众号",
  "社交媒体·微博": "社交媒体：微博",
  "社交媒体·今日头条": "社交媒体：今日头条",
  "未分类": "其他信息源",
  "official-policy": "官方政策法规",
  "customs-enforcement": "海关执法查发",
  "export-control-sanctions": "出口管制与制裁",
  "tbt-sps-regulation": "技术性贸易措施",
  "critical-minerals-commodities": "关键矿产与大宗商品",
  "trade-remedy-tariff": "关税税则与贸易救济",
  "search-ai": "搜索与AI检索",
  "commercial-data": "商业/API数据",
  "news-enforcement": "新闻媒体-执法线索",
  "news-hotspots": "新闻媒体-时政热点",
  "social-osint": "社交媒体/公众号",
  "manual-standby": "备用未配置",
  "uncategorized": "其他未分类",
};

const PRIMARY_CATEGORY_ORDER = [
  "defense_procurement", "official-policy", "customs-enforcement",
  "export-control-sanctions", "tbt-sps-regulation",
  "critical-minerals-commodities", "trade-remedy-tariff",
  "search-ai", "commercial-data", "news-enforcement",
  "news-hotspots", "social-osint", "manual-standby", "uncategorized",
];

// ── Helpers ───────────────────────────────────────────────────────────

function primaryCategory(source: Source): string {
  return source.default_categories?.[0] || "未分类";
}

function primaryLabel(category: string): string {
  return PRIMARY_CATEGORY_LABELS[category] || "其他信息源";
}

function primaryRank(category: string): number {
  const index = PRIMARY_CATEGORY_ORDER.indexOf(category);
  return index >= 0 ? index : PRIMARY_CATEGORY_ORDER.length;
}

function sourceUrl(source: Source): string {
  return source.homepage_url || source.base_url || source.api_endpoint || "";
}

function channelLabel(channel: string): string {
  return CHANNEL_LABELS[channel] || channel;
}

// ── Sub-components ────────────────────────────────────────────────────

function HealthDot({ status }: { status?: string }) {
  const meta = HEALTH_META[status ?? "unknown"] ?? HEALTH_META.unknown;
  return (
    <span
      className="source-health-dot"
      title={status ?? "unknown"}
      style={{ color: meta.color }}
    >
      {meta.label}
    </span>
  );
}

function SourceRow({
  source,
  isSelected,
  onToggle,
}: {
  source: Source;
  isSelected: boolean;
  onToggle: () => void;
}) {
  const Icon = CHANNEL_ICONS[source.channel] ?? Globe;
  return (
    <label
      className={`source-row ${isSelected ? "source-row--selected" : ""}`}
    >
      <input
        type="checkbox"
        checked={isSelected}
        onChange={onToggle}
        onClick={(e) => e.stopPropagation()}
      />
      <HealthDot status={source.health_status} />
      <Icon size={14} className="source-row-icon" />
      <span className="source-row-name" title={source.name}>{source.name}</span>
      <span className="source-row-channel">{channelLabel(source.channel)}</span>
    </label>
  );
}

function GroupHeader({
  label,
  expanded,
  selectedCount,
  totalCount,
  onToggleExpand,
  onToggleSelect,
}: {
  label: string;
  expanded: boolean;
  selectedCount: number;
  totalCount: number;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
}) {
  const allSelected = selectedCount === totalCount && totalCount > 0;
  return (
    <div
      className="source-group-header"
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      onClick={onToggleExpand}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggleExpand();
        }
      }}
    >
      <input
        type="checkbox"
        checked={allSelected}
        ref={(el) => {
          if (el) el.indeterminate = selectedCount > 0 && !allSelected;
        }}
        onChange={onToggleSelect}
        onClick={(e) => e.stopPropagation()}
      />
      <ChevronDown
        size={16}
        className={`source-group-chevron ${expanded ? "" : "source-group-chevron--closed"}`}
      />
      <span className="source-group-label">{label}</span>
      <span className="source-group-count">{selectedCount}/{totalCount}</span>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────

export function SourceSelector({
  sources,
  selected,
  onChange,
  models,
  selectedModelIds,
  onModelChange,
}: SourceSelectorProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<string[]>(selected);
  const [modelDraft, setModelDraft] = useState<string[]>(selectedModelIds);
  const [search, setSearch] = useState("");
  const [channelFilter, setChannelFilter] = useState<string>("");
  const [healthFilter, setHealthFilter] = useState<string>("");
  const [collapsedIds, setCollapsedIds] = useState<string[]>([]);
  const [page, setPage] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  // ── Filter + group sources ──────────────────────────────────────────
  const tree = useMemo(() => {
    const query = search.trim().toLowerCase();
    const buckets: Record<string, Source[]> = {};
    for (const source of sources) {
      const category = primaryCategory(source);
      // Channel filter
      if (channelFilter && source.channel !== channelFilter) continue;
      // Health filter
      if (healthFilter && (source.health_status ?? "unknown") !== healthFilter) continue;
      // Search filter
      if (query) {
        const searchable = [
          source.name, source.id, source.channel,
          sourceUrl(source),
          source.default_categories?.join(" ") || "",
          primaryLabel(category),
        ].join(" ").toLowerCase();
        if (!searchable.includes(query)) continue;
      }
      buckets[category] = [...(buckets[category] || []), source];
    }
    return Object.entries(buckets)
      .map(([id, groupedSources]) => ({
        id,
        label: primaryLabel(id),
        sources: [...groupedSources].sort((a, b) => a.name.localeCompare(b.name, "zh-CN")),
      }))
      .sort((a, b) => primaryRank(a.id) - primaryRank(b.id) || a.label.localeCompare(b.label, "zh-CN"));
  }, [search, sources, channelFilter, healthFilter]);

  const configuredModels = models.filter(
    (m) => m.is_active && m.is_configured && Boolean(m.model_name),
  );
  const configuredModelIds = configuredModels.map((m) => m.id);

  // ── Expand/collapse ─────────────────────────────────────────────────
  const isSearching = search.trim().length > 0;
  const isGroupExpanded = useCallback(
    (id: string) => isSearching || !collapsedIds.includes(id),
    [isSearching, collapsedIds],
  );
  const toggleExpanded = useCallback(
    (id: string) =>
      setCollapsedIds((cur) =>
        cur.includes(id) ? cur.filter((v) => v !== id) : [...cur, id],
      ),
    [],
  );
  const allGroupIds = useMemo(
    () => tree.map((g) => g.id),
    [tree],
  );
  const setAllExpanded = (expanded: boolean) =>
    setCollapsedIds(expanded ? [] : allGroupIds);

  // ── Flatten for pagination ──────────────────────────────────────────
  const flatSources = useMemo(() => {
    const result: { group: string; source: Source }[] = [];
    for (const group of tree) {
      if (!isGroupExpanded(group.id)) continue;
      for (const source of group.sources) {
        result.push({ group: group.id, source });
      }
    }
    return result;
  }, [tree, isGroupExpanded]);

  const visibleSources = useMemo(
    () => flatSources.slice(0, (page + 1) * PAGE_SIZE),
    [flatSources, page],
  );

  // ── Selection ───────────────────────────────────────────────────────
  const openPicker = () => {
    setDraft([...selected]);
    setModelDraft([...selectedModelIds]);
    setSearch("");
    setChannelFilter("");
    setHealthFilter("");
    setCollapsedIds([]);
    setPage(0);
    setOpen(true);
  };
  const closePicker = () => setOpen(false);
  const saveSelection = () => {
    onChange(draft);
    onModelChange(modelDraft);
    setOpen(false);
  };

  const toggleSource = useCallback((id: string) => {
    setDraft((cur) =>
      cur.includes(id) ? cur.filter((v) => v !== id) : [...cur, id],
    );
  }, []);

  const toggleIds = (ids: string[]) => {
    setDraft((cur) => {
      const all = ids.length > 0 && ids.every((id) => cur.includes(id));
      return all
        ? cur.filter((id) => !ids.includes(id))
        : Array.from(new Set([...cur, ...ids]));
    });
  };

  const toggleModel = (id: string) => {
    setModelDraft((cur) =>
      cur.includes(id) ? cur.filter((v) => v !== id) : [...cur, id],
    );
  };
  const toggleModelIds = (ids: string[]) => {
    setModelDraft((cur) => {
      const all = ids.length > 0 && ids.every((id) => cur.includes(id));
      return all
        ? cur.filter((id) => !ids.includes(id))
        : Array.from(new Set([...cur, ...ids]));
    });
  };

  const selectAllVisible = () => {
    const visibleIds = tree.flatMap((g) => g.sources.map((s) => s.id));
    setDraft((cur) => Array.from(new Set([...cur, ...visibleIds])));
  };

  const selectAll = () => {
    const allIds = sources.map((s) => s.id);
    setDraft(allIds);
  };

  const clearAll = () => {
    setDraft([]);
    setModelDraft([]);
  };

  // ── Reset page on filter change ─────────────────────────────────────
  useEffect(() => { setPage(0); }, [search, channelFilter, healthFilter]);

  // ── Infinite scroll ─────────────────────────────────────────────────
  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 100) {
      setPage((p) => {
        const maxPage = Math.ceil(flatSources.length / PAGE_SIZE) - 1;
        return p < maxPage ? p + 1 : p;
      });
    }
  }, [flatSources.length]);

  // ── Available channels ──────────────────────────────────────────────
  const availableChannels = useMemo(() => {
    const set = new Set<string>();
    for (const s of sources) set.add(s.channel);
    return Array.from(set).sort();
  }, [sources]);

  // ── Render ──────────────────────────────────────────────────────────
  return (
    <>
      <div className="topic-source-picker-trigger">
        <span className="text-muted small">
          已选 {selected.length} 个信息源、{selectedModelIds.length} 个 AI 模型
        </span>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={openPicker}
        >
          选择信息源
        </button>
      </div>

      {open && createPortal(
        <div
          className="modal-overlay source-picker-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) closePicker();
          }}
        >
          <section
            className="modal source-picker-modal-v2"
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-picker-title"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <header className="source-picker-header">
              <div>
                <h3 id="source-picker-title">关联信息源</h3>
                <p className="text-muted small">
                  共 {sources.length} 个信息源 · 已选 {draft.length} 个 · {modelDraft.length} 个 AI 模型
                </p>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={closePicker}
                title="关闭"
              >
                <X size={16} />
              </button>
            </header>

            {/* Toolbar */}
            <div className="source-picker-toolbar-v2">
              <label className="source-selector-search">
                <Search size={16} />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索名称、URL、渠道或分类..."
                  autoFocus
                />
              </label>

              <select
                className="source-picker-filter-select"
                value={channelFilter}
                onChange={(e) => setChannelFilter(e.target.value)}
              >
                <option value="">全部渠道</option>
                {availableChannels.map((ch) => (
                  <option key={ch} value={ch}>{channelLabel(ch)}</option>
                ))}
              </select>

              <select
                className="source-picker-filter-select"
                value={healthFilter}
                onChange={(e) => setHealthFilter(e.target.value)}
              >
                <option value="">全部状态</option>
                <option value="healthy">● 健康</option>
                <option value="degraded">● 降级</option>
                <option value="failed">● 失败</option>
                <option value="unreachable">● 不可达</option>
                <option value="unknown">○ 未检查</option>
              </select>

              <div className="source-picker-toolbar-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={selectAll} title="选择所有信息源">
                  全选
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={selectAllVisible} title="选择当前筛选结果">
                  选当前
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAllExpanded(true)}>
                  <ChevronsUpDown size={14} /> 展开
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAllExpanded(false)}>
                  <ChevronsDownUp size={14} /> 收起
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={clearAll}>
                  清空
                </button>
              </div>
            </div>

            {/* Body: scrollable tree */}
            <div
              className="source-picker-body"
              ref={scrollRef}
              onScroll={handleScroll}
            >
              {/* AI Models group */}
              {configuredModels.length > 0 && (
                <section className="source-tree-group source-tree-group--models">
                  <GroupHeader
                    label="AI 模型信息源"
                    expanded={isGroupExpanded(MODELS_GROUP_ID)}
                    selectedCount={configuredModelIds.filter((id) => modelDraft.includes(id)).length}
                    totalCount={configuredModelIds.length}
                    onToggleExpand={() => toggleExpanded(MODELS_GROUP_ID)}
                    onToggleSelect={() => toggleModelIds(configuredModelIds)}
                  />
                  {isGroupExpanded(MODELS_GROUP_ID) && (
                    <div className="source-tree-children">
                      {configuredModels.map((model) => {
                        const isSelected = modelDraft.includes(model.id);
                        return (
                          <label key={model.id} className={`source-row ${isSelected ? "source-row--selected" : ""}`}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleModel(model.id)}
                            />
                            <Zap size={14} className="source-row-icon" />
                            <span className="source-row-name" title={model.name}>{model.name}</span>
                            <span className="source-row-channel">{model.model_name}</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </section>
              )}

              {/* Source groups */}
              {tree.length === 0 && (
                <div className="source-picker-empty">
                  <Filter size={32} className="source-picker-empty-icon" />
                  <p>无匹配信息源</p>
                  <p className="text-muted small">尝试调整搜索条件或筛选器</p>
                </div>
              )}

              {tree.map((group) => {
                const groupIds = group.sources.map((s) => s.id);
                const groupSelected = groupIds.filter((id) => draft.includes(id)).length;
                const expanded = isGroupExpanded(group.id);
                return (
                  <section key={group.id} className="source-tree-group">
                    <GroupHeader
                      label={group.label}
                      expanded={expanded}
                      selectedCount={groupSelected}
                      totalCount={groupIds.length}
                      onToggleExpand={() => toggleExpanded(group.id)}
                      onToggleSelect={() => toggleIds(groupIds)}
                    />
                    {expanded && (
                      <div className="source-tree-children">
                        {group.sources.map((source) => (
                          <SourceRow
                            key={source.id}
                            source={source}
                            isSelected={draft.includes(source.id)}
                            onToggle={() => toggleSource(source.id)}
                          />
                        ))}
                      </div>
                    )}
                  </section>
                );
              })}

              {/* Load more indicator */}
              {visibleSources.length < flatSources.length && (
                <div className="source-picker-load-more">
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => setPage((p) => p + 1)}
                  >
                    加载更多 ({flatSources.length - visibleSources.length} 条剩余)
                  </button>
                </div>
              )}
            </div>

            {/* Footer */}
            <footer className="source-picker-footer">
              <span className="text-muted small">
                当前选择 {draft.length} 个信息源、{modelDraft.length} 个 AI 模型
              </span>
              <div className="modal-actions source-picker-actions">
                <button type="button" className="btn btn-ghost" onClick={closePicker}>
                  取消
                </button>
                <button type="button" className="btn btn-primary" onClick={saveSelection}>
                  <Check size={16} /> 保存选择
                </button>
              </div>
            </footer>
          </section>
        </div>,
        document.body,
      )}
    </>
  );
}