import { Check, ChevronDown, ChevronsDownUp, ChevronsUpDown, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
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

/** 受控树：一层 = 信息源分类，二层 = 该分类下的信息源条目 */
type SourceTreeGroup = {
  id: string;
  label: string;
  sources: Source[];
};

const MODELS_GROUP_ID = "__models__";

const PRIMARY_CATEGORY_LABELS: Record<string, string> = {
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
  "official-policy",
  "customs-enforcement",
  "export-control-sanctions",
  "tbt-sps-regulation",
  "critical-minerals-commodities",
  "trade-remedy-tariff",
  "search-ai",
  "commercial-data",
  "news-enforcement",
  "news-hotspots",
  "social-osint",
  "manual-standby",
  "uncategorized",
];

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

function sourceMeta(source: Source): string {
  const tags = source.default_categories?.slice(1).join(" · ") || "";
  const url = sourceUrl(source);
  return [tags, url].filter(Boolean).join(" · ") || channelLabel(source.channel);
}

function channelLabel(channel: string): string {
  return CHANNEL_LABELS[channel] || channel;
}

function TreeCheckbox({
  checked,
  mixed = false,
  onChange,
  label,
}: {
  checked: boolean;
  mixed?: boolean;
  onChange: () => void;
  label: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = mixed;
  }, [mixed]);

  return (
    <input
      ref={inputRef}
      type="checkbox"
      checked={checked}
      aria-label={label}
      onClick={(event) => event.stopPropagation()}
      onChange={onChange}
    />
  );
}

function SourceLeaf({
  source,
  selected,
  onToggle,
}: {
  source: Source;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <label className={`source-tree-leaf ${selected ? "source-tree-leaf--selected" : ""}`}>
      <TreeCheckbox checked={selected} label={`选择信息源：${source.name}`} onChange={onToggle} />
      <span className="source-tree-leaf-copy">
        <strong>{source.name}</strong>
        <span title={sourceMeta(source)}>{sourceMeta(source)}</span>
      </span>
      <span className="source-tree-channel">{channelLabel(source.channel)}</span>
    </label>
  );
}

function TreeGroupHeader({
  label,
  expanded,
  selectedCount,
  totalCount,
  checkboxLabel,
  onToggleExpand,
  onToggleSelect,
}: {
  label: string;
  expanded: boolean;
  selectedCount: number;
  totalCount: number;
  checkboxLabel: string;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
}) {
  const allSelected = selectedCount === totalCount && totalCount > 0;
  return (
    <div
      className="source-tree-root"
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      onClick={onToggleExpand}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggleExpand();
        }
      }}
    >
      <TreeCheckbox
        checked={allSelected}
        mixed={selectedCount > 0 && !allSelected}
        label={checkboxLabel}
        onChange={onToggleSelect}
      />
      <span className="source-tree-toggle">
        <ChevronDown size={16} className={`source-tree-chevron ${expanded ? "" : "source-tree-chevron--closed"}`} />
        <span>{label}</span>
      </span>
      <span className="source-tree-count">{selectedCount}/{totalCount}</span>
    </div>
  );
}

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
  /** 收起状态的分类 id 集合；默认全部展开，二层信息源立即可见 */
  const [collapsedIds, setCollapsedIds] = useState<string[]>([]);

  const tree = useMemo<SourceTreeGroup[]>(() => {
    const query = search.trim().toLowerCase();
    const buckets: Record<string, Source[]> = {};
    for (const source of sources) {
      const category = primaryCategory(source);
      const searchable = [
        source.name,
        source.id,
        source.channel,
        sourceUrl(source),
        source.default_categories?.join(" ") || "",
        primaryLabel(category),
      ].join(" ").toLowerCase();
      if (query && !searchable.includes(query)) continue;
      buckets[category] = [...(buckets[category] || []), source];
    }
    return Object.entries(buckets)
      .map(([id, groupedSources]) => ({
        id,
        label: primaryLabel(id),
        sources: [...groupedSources].sort((left, right) => left.name.localeCompare(right.name, "zh-CN")),
      }))
      .sort((left, right) => primaryRank(left.id) - primaryRank(right.id) || left.label.localeCompare(right.label, "zh-CN"));
  }, [search, sources]);

  const configuredModels = models.filter((model) => model.is_active && model.is_configured && Boolean(model.model_name));
  const configuredModelIds = configuredModels.map((model) => model.id);
  const allGroupIds = useMemo(
    () => (configuredModels.length > 0 ? [MODELS_GROUP_ID, ...tree.map((group) => group.id)] : tree.map((group) => group.id)),
    [configuredModels.length, tree],
  );

  /** 搜索时强制展开，保证匹配的二层条目直接可见 */
  const isSearching = search.trim().length > 0;
  const isGroupExpanded = (id: string) => isSearching || !collapsedIds.includes(id);
  const toggleExpanded = (id: string) => {
    setCollapsedIds((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  };
  const setAllExpanded = (expanded: boolean) => setCollapsedIds(expanded ? [] : allGroupIds);

  const openPicker = () => {
    setDraft([...selected]);
    setModelDraft([...selectedModelIds]);
    setSearch("");
    setCollapsedIds([]);
    setOpen(true);
  };
  const closePicker = () => setOpen(false);
  const saveSelection = () => {
    onChange(draft);
    onModelChange(modelDraft);
    setOpen(false);
  };
  const toggleSource = (id: string) => {
    setDraft((current) => current.includes(id)
      ? current.filter((value) => value !== id)
      : [...current, id]);
  };
  const toggleIds = (ids: string[]) => {
    setDraft((current) => {
      const allSelected = ids.length > 0 && ids.every((id) => current.includes(id));
      return allSelected
        ? current.filter((id) => !ids.includes(id))
        : Array.from(new Set([...current, ...ids]));
    });
  };
  const toggleModel = (id: string) => {
    setModelDraft((current) => current.includes(id)
      ? current.filter((value) => value !== id)
      : [...current, id]);
  };
  const toggleModelIds = (ids: string[]) => {
    setModelDraft((current) => {
      const allSelected = ids.length > 0 && ids.every((id) => current.includes(id));
      return allSelected
        ? current.filter((id) => !ids.includes(id))
        : Array.from(new Set([...current, ...ids]));
    });
  };
  const selectVisibleSources = () => {
    const visibleIds = tree.flatMap((group) => group.sources.map((source) => source.id));
    setDraft((current) => Array.from(new Set([...current, ...visibleIds])));
  };

  return (
    <>
      <div className="topic-source-picker-trigger">
        <span className="text-muted small">已选 {selected.length} 个信息源、{selectedModelIds.length} 个 AI 模型</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={openPicker}>
          选择信息源
        </button>
      </div>

      {open && createPortal(
        <div
          className="modal-overlay source-picker-overlay"
          onClick={(event) => {
            if (event.target === event.currentTarget) closePicker();
          }}
        >
          <section
            className="modal source-picker-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-picker-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="source-picker-header">
              <div>
                <h3 id="source-picker-title">关联信息源</h3>
                <p className="text-muted small">网站与 RSS 是原始证据渠道；AI 模型复用已生效配置，用于生成语义检索计划、中文转译和审核，不需要再次录入密钥。</p>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" onClick={closePicker} title="关闭">
                <X size={16} />
              </button>
            </header>

            <div className="source-picker-toolbar">
              <label className="source-selector-search">
                <Search size={16} />
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="搜索来源名称、URL、渠道或分类"
                />
              </label>
              <button type="button" className="btn btn-ghost btn-sm" onClick={selectVisibleSources}>
                选择当前结果
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAllExpanded(true)}>
                <ChevronsUpDown size={14} /> 展开分类
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAllExpanded(false)}>
                <ChevronsDownUp size={14} /> 收起分类
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setDraft([]); setModelDraft([]); }}>
                清空选择
              </button>
            </div>

            <div className="source-tree" role="tree" aria-label="信息源分类树">
              {configuredModels.length > 0 && (
                <section
                  className="source-tree-group source-tree-group--models"
                  role="treeitem"
                  aria-expanded={isGroupExpanded(MODELS_GROUP_ID)}
                >
                  <TreeGroupHeader
                    label="AI 模型信息源"
                    expanded={isGroupExpanded(MODELS_GROUP_ID)}
                    selectedCount={configuredModelIds.filter((id) => modelDraft.includes(id)).length}
                    totalCount={configuredModelIds.length}
                    checkboxLabel="选择全部 AI 模型"
                    onToggleExpand={() => toggleExpanded(MODELS_GROUP_ID)}
                    onToggleSelect={() => toggleModelIds(configuredModelIds)}
                  />
                  {isGroupExpanded(MODELS_GROUP_ID) && (
                    <div className="source-tree-children" role="group">
                      {configuredModels.map((model) => {
                        const isSelected = modelDraft.includes(model.id);
                        return (
                          <label key={model.id} className={`source-tree-leaf ${isSelected ? "source-tree-leaf--selected" : ""}`}>
                            <TreeCheckbox checked={isSelected} label={`选择 AI 模型：${model.name}`} onChange={() => toggleModel(model.id)} />
                            <span className="source-tree-leaf-copy">
                              <strong>{model.name}</strong>
                              <span>{model.provider} · {model.model_name}</span>
                            </span>
                            <span className="source-tree-channel">已配置</span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </section>
              )}
              {tree.length === 0 && <div className="text-muted small">无匹配信息源</div>}
              {tree.map((group) => {
                const groupIds = group.sources.map((source) => source.id);
                const groupSelected = groupIds.filter((id) => draft.includes(id)).length;
                const expanded = isGroupExpanded(group.id);
                return (
                  <section key={group.id} className="source-tree-group" role="treeitem" aria-expanded={expanded}>
                    <TreeGroupHeader
                      label={group.label}
                      expanded={expanded}
                      selectedCount={groupSelected}
                      totalCount={groupIds.length}
                      checkboxLabel={`选择分类：${group.label}`}
                      onToggleExpand={() => toggleExpanded(group.id)}
                      onToggleSelect={() => toggleIds(groupIds)}
                    />
                    {expanded && (
                      <div className="source-tree-children" role="group">
                        {group.sources.map((source) => (
                          <SourceLeaf
                            key={source.id}
                            source={source}
                            selected={draft.includes(source.id)}
                            onToggle={() => toggleSource(source.id)}
                          />
                        ))}
                      </div>
                    )}
                  </section>
                );
              })}
            </div>

            <footer className="source-picker-footer">
              <span className="text-muted small">当前选择 {draft.length} 个信息源、{modelDraft.length} 个 AI 模型</span>
              <div className="modal-actions source-picker-actions">
                <button type="button" className="btn btn-ghost" onClick={closePicker}>取消</button>
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
