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

type SourceTreeLeaf = Source;
type SourceTreeGroup = {
  id: string;
  label: string;
  sources: SourceTreeLeaf[];
};

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
};

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

function secondaryCategory(source: Source): string {
  return source.default_categories?.[1] || "—";
}

function primaryLabel(category: string): string {
  return PRIMARY_CATEGORY_LABELS[category] || "其他信息源";
}

const SECONDARY_CATEGORY_LABELS: Record<string, string> = {
  trade: "贸易",
  enforcement: "执法",
  regulation: "法规",
  crime: "犯罪",
  customs: "海关",
  fraud: "欺诈",
  sanction: "制裁",
  commodity: "商品",
  policy: "政策",
  export_control: "出口管制",
  market: "市场",
  tariff: "关税",
  economy: "经济",
  logistics: "物流",
  compliance: "合规",
  energy: "能源",
  food: "食品",
  futures: "期货",
  metal: "金属",
  shipping: "航运",
  price: "价格行情",
  fta: "自贸协定",
  ip: "知识产权",
  risk: "风险情报",
  tbt_sps: "技术贸易措施",
  social: "社交媒体",
  web: "网页信息",
  专业类网站: "专业类网站",
  政府官网: "政府官网",
  新闻媒体: "新闻媒体",
  其他: "其他",
  "—": "未细分",
};

function secondaryLabel(category: string): string {
  if (!category || category === "—") return "未细分";
  return SECONDARY_CATEGORY_LABELS[category] || category;
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
      onChange={onChange}
    />
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
  const [expandedGroups, setExpandedGroups] = useState<string[]>([]);

  const tree = useMemo<SourceTreeGroup[]>(() => {
    const query = search.trim().toLowerCase();
    const buckets: Record<string, Source[]> = {};
    for (const source of sources) {
      const category = primaryCategory(source);
      const sub = secondaryCategory(source);
      const searchable = [
        source.name,
        source.id,
        source.channel,
        sourceUrl(source),
        source.default_categories?.join(" ") || "",
        primaryLabel(category),
        secondaryLabel(sub),
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
      .sort((left, right) => left.label.localeCompare(right.label, "zh-CN"));
  }, [search, sources]);

  const openPicker = () => {
    setDraft([...selected]);
    setModelDraft([...selectedModelIds]);
    setSearch("");
    // Keep the first level visible when the dialog opens. Each second-level
    // branch still has its own explicit toggle, so source selection never
    // depends on event bubbling through nested rows.
    setExpandedGroups(Array.from(new Set(sources.map(primaryCategory))));
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
  const toggleExpanded = (id: string) => {
    setExpandedGroups((current) => current.includes(id)
      ? current.filter((value) => value !== id)
      : [...current, id]);
  };
  const selectVisibleSources = () => {
    const visibleIds = tree.flatMap((group) => group.sources.map((source) => source.id));
    setDraft((current) => Array.from(new Set([...current, ...visibleIds])));
  };
  const configuredModels = models.filter((model) => model.is_active && model.is_configured && Boolean(model.model_name));
  const configuredModelIds = configuredModels.map((model) => model.id);
  const allGroupIds = [
    ...(configuredModels.length > 0 ? ["__ai_models__"] : []),
    ...tree.map((group) => group.id),
  ];
  const expandedAll = allGroupIds.length > 0 && allGroupIds.every((id) => expandedGroups.includes(id));
  const setAllExpanded = (expanded: boolean) => setExpandedGroups(expanded ? allGroupIds : []);

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
            event.stopPropagation();
            closePicker();
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
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAllExpanded(!expandedAll)}>
                {expandedAll ? <ChevronsDownUp size={14} /> : <ChevronsUpDown size={14} />}
                {expandedAll ? "收起分类" : "展开分类"}
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setDraft([]); setModelDraft([]); }}>
                清空选择
              </button>
            </div>

            <div className="source-tree" role="tree" aria-label="信息源分类树">
              {configuredModels.length > 0 && (() => {
                const selectedCount = configuredModelIds.filter((id) => modelDraft.includes(id)).length;
                const allSelected = selectedCount === configuredModelIds.length;
                const isExpanded = expandedGroups.includes("__ai_models__");
                return (
                  <section className="source-tree-group source-tree-group--models" role="treeitem" aria-expanded={isExpanded}>
                    <div className="source-tree-root">
                      <TreeCheckbox
                        checked={allSelected}
                        mixed={selectedCount > 0 && !allSelected}
                        label="选择全部 AI 模型"
                        onChange={() => toggleModelIds(configuredModelIds)}
                      />
                      <button
                        type="button"
                        className="source-tree-toggle"
                        aria-expanded={isExpanded}
                        aria-controls="source-tree-ai-children"
                        onClick={() => toggleExpanded("__ai_models__")}
                      >
                        <ChevronDown size={16} className={isExpanded ? "" : "source-tree-chevron--closed"} />
                        <span>AI 模型信息源</span>
                      </button>
                      <span className="source-tree-count">{selectedCount}/{configuredModelIds.length}</span>
                    </div>
                      {isExpanded && <div
                        id="source-tree-ai-children"
                        className="source-tree-children"
                        role="group"
                      >
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
                      </div>}
                  </section>
                );
              })()}
              {tree.length === 0 && <div className="text-muted small">无匹配信息源</div>}
              {tree.map((group) => {
                const groupIds = group.sources.map((source) => source.id);
                const groupSelected = groupIds.filter((id) => draft.includes(id)).length;
                const groupAll = groupSelected === groupIds.length && groupIds.length > 0;
                const groupExpanded = expandedGroups.includes(group.id);
                return (
                  <section key={group.id} className="source-tree-group" role="treeitem" aria-expanded={groupExpanded}>
                    <div className="source-tree-root">
                      <TreeCheckbox
                        checked={groupAll}
                        mixed={groupSelected > 0 && !groupAll}
                        label={`选择分类：${group.label}`}
                        onChange={() => toggleIds(groupIds)}
                      />
                      <button
                        type="button"
                        className="source-tree-toggle"
                        aria-expanded={groupExpanded}
                        aria-controls={`source-tree-${encodeURIComponent(group.id)}-children`}
                        onClick={() => toggleExpanded(group.id)}
                      >
                        <ChevronDown size={16} className={groupExpanded ? "" : "source-tree-chevron--closed"} />
                        <span>{group.label}</span>
                      </button>
                      <span className="source-tree-count">{groupSelected}/{groupIds.length}</span>
                    </div>

                      {groupExpanded && <div
                        id={`source-tree-${encodeURIComponent(group.id)}-children`}
                        className="source-tree-children"
                        role="group"
                      >
                        {group.sources.map((source) => {
                          const isSelected = draft.includes(source.id);
                          return (
                            <label key={source.id} className={`source-tree-leaf ${isSelected ? "source-tree-leaf--selected" : ""}`}>
                              <TreeCheckbox
                                checked={isSelected}
                                label={`选择信息源：${source.name}`}
                                onChange={() => toggleSource(source.id)}
                              />
                              <span className="source-tree-leaf-copy">
                                <strong>{source.name}</strong>
                                <span title={sourceMeta(source)}>{sourceMeta(source)}</span>
                              </span>
                              <span className="source-tree-channel">{channelLabel(source.channel)}</span>
                            </label>
                          );
                        })}
                      </div>}
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
