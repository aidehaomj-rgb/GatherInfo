import { Check, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { Source } from "../types";

interface SourceSelectorProps {
  sources: Source[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function SourceSelector({ sources, selected, onChange }: SourceSelectorProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<string[]>(selected);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return sources;
    return sources.filter((source) =>
      `${source.name} ${source.id} ${source.channel} ${(source.default_categories ?? []).join(" ")}`
        .toLowerCase()
        .includes(query),
    );
  }, [sources, search]);

  const groups = useMemo(() => {
    const tree: Record<string, Record<string, Source[]>> = {};
    for (const source of filtered) {
      const categories = source.default_categories ?? [];
      const primary = categories[0] || "未分类";
      const secondary = categories[1] || "其他";
      const primaryGroup = tree[primary] ?? {};
      tree[primary] = primaryGroup;
      primaryGroup[secondary] = [...(primaryGroup[secondary] ?? []), source];
    }
    return tree;
  }, [filtered]);

  const openPicker = () => {
    setDraft([...selected]);
    setSearch("");
    setOpen(true);
  };
  const closePicker = () => setOpen(false);
  const saveSelection = () => {
    onChange(draft);
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

  return (
    <>
      <div className="topic-source-picker-trigger">
        <span className="text-muted small">已选 {selected.length} 个可采集信息源</span>
        <button type="button" className="btn btn-secondary btn-sm" onClick={openPicker}>
          选择信息源
        </button>
      </div>

      {open && (
        <div className="modal-overlay" onClick={closePicker}>
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
                <p className="text-muted small">按分类选择本主题参与采集的信息源。</p>
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
                  placeholder="搜索名称、ID、渠道或分类"
                />
              </label>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDraft(filtered.map((source) => source.id))}>
                全选当前结果
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDraft([])}>
                清空选择
              </button>
            </div>

            <div className="source-selector source-picker-list">
              {Object.keys(groups).length === 0 && <div className="text-muted small">无匹配信息源</div>}
              {Object.entries(groups).map(([primary, secondaryGroups]) => {
                const primaryIds = Object.values(secondaryGroups).flat().map((source) => source.id);
                const primarySelected = primaryIds.length > 0 && primaryIds.every((id) => draft.includes(id));
                return (
                  <section key={primary} className="source-selector-group">
                    <div className="source-selector-l1">
                      <label className="source-selector-checkbox">
                        <input type="checkbox" checked={primarySelected} onChange={() => toggleIds(primaryIds)} />
                        <strong>{primary}</strong>
                      </label>
                      <span className="text-muted small">{primaryIds.length} 个</span>
                    </div>
                    {Object.entries(secondaryGroups).map(([secondary, groupSources]) => {
                      const ids = groupSources.map((source) => source.id);
                      const allSelected = ids.length > 0 && ids.every((id) => draft.includes(id));
                      return (
                        <div key={`${primary}::${secondary}`} className="source-selector-subgroup">
                          <label className="source-selector-checkbox">
                            <input type="checkbox" checked={allSelected} onChange={() => toggleIds(ids)} />
                            <span>{secondary}</span>
                            <span className="text-muted small">({ids.length})</span>
                          </label>
                          <div className="source-selector-items">
                            {groupSources.map((source) => (
                              <label key={source.id} className="source-selector-row">
                                <input
                                  type="checkbox"
                                  checked={draft.includes(source.id)}
                                  onChange={() => toggleSource(source.id)}
                                />
                                <span className="source-selector-name" title={`${source.name} (${source.id})`}>
                                  {source.name}
                                </span>
                                <span className="source-selector-channel">{source.channel}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </section>
                );
              })}
            </div>

            <footer className="source-picker-footer">
              <span className="text-muted small">当前选择 {draft.length} 个信息源</span>
              <div className="modal-actions source-picker-actions">
                <button type="button" className="btn btn-ghost" onClick={closePicker}>取消</button>
                <button type="button" className="btn btn-primary" onClick={saveSelection}>
                  <Check size={16} /> 保存选择
                </button>
              </div>
            </footer>
          </section>
        </div>
      )}
    </>
  );
}
