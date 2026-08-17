import { useEffect, useMemo, useState, useCallback } from "react";
import { fetchTags, updateTag, deleteTag, mergeTags, fetchItems } from "../api";
import { requestTagFilter } from "./ItemsPage";
import type { Tag } from "../types";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { Trash2, Edit3, GitMerge, List, Search, Tags, X, Filter } from "lucide-react";
import { formatBeijingDateTime } from "../utils/date";

/**
 * 受控多维标签体系：维度 slug → 中文名。
 * 与后端 tag_taxonomy.TAXONOMY_DIMENSIONS 对齐；未在受控维度内的标签
 * （如 weekly/source/system 等历史遗留 namespace）归入「其他」。
 */
const DIMENSION_META: { dim: string; label: string }[] = [
  { dim: "policy", label: "政策工具" },
  { dim: "impact", label: "影响渠道" },
  { dim: "category", label: "业务主题" },
  { dim: "region", label: "涉华与区域" },
  { dim: "evidence", label: "证据强度" },
];
const CONTROLLED_DIMS = new Set(DIMENSION_META.map((d) => d.dim));

/** 标签显示名：优先中文 label，回退英文 value。 */
const tagLabel = (t: { label?: string | null; value: string }): string => t.label || t.value;

const DIM_COLORS: Record<string, string> = {
  policy: "#3b82f6",
  impact: "#22c55e",
  category: "#f59e0b",
  region: "#8b5cf6",
  evidence: "#06b6d4",
};

export function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Tag | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; value: string } | null>(null);

  // 组合筛选：每个维度最多选中一个标签（AND 组合）
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [filteredItems, setFilteredItems] = useState<{ total: number } | null>(null);
  const [filtering, setFiltering] = useState(false);

  // Merge controls
  const [mergeSource, setMergeSource] = useState("");
  const [mergeTarget, setMergeTarget] = useState("");
  const [merging, setMerging] = useState(false);
  const [confirmMerge, setConfirmMerge] = useState(false);
  const [mergeMsg, setMergeMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const t = await fetchTags(undefined, 2000);
      setTags(t);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  // 选中标签变化时，实时计算命中条目数（组合 AND 筛选）
  const selectedTagIds = useMemo(
    () => Object.values(selected).filter(Boolean),
    [selected],
  );
  useEffect(() => {
    if (selectedTagIds.length === 0) {
      setFilteredItems(null);
      return;
    }
    let cancelled = false;
    setFiltering(true);
    const tagParam = selectedTagIds.join(",");
    fetchItems({ tag: tagParam, page: 1, page_size: 1 })
      .then((r) => { if (!cancelled) setFilteredItems({ total: r.total }); })
      .catch(() => { if (!cancelled) setFilteredItems({ total: 0 }); })
      .finally(() => { if (!cancelled) setFiltering(false); });
    return () => { cancelled = true; };
  }, [selectedTagIds]);

  // 点击标签：切换选中状态；点击「查看信息」跳到采集条目并按组合标签筛选
  const toggleTag = useCallback((dim: string, tagId: string) => {
    setSelected((prev) => ({
      ...prev,
      [dim]: prev[dim] === tagId ? "" : tagId,
    }));
  }, []);

  const clearSelection = useCallback(() => setSelected({}), []);

  const goToItems = useCallback(() => {
    if (selectedTagIds.length === 0) return;
    // 1) 先切视图（ItemsPage 挂载并消费持久化筛选）
    // 2) 再用 requestTagFilter 写入组合标签（逗号分隔 AND）
    const tag = selectedTagIds.join(",");
    requestTagFilter(tag);
    window.dispatchEvent(new CustomEvent("navigate-view", { detail: { view: "items" } }));
  }, [selectedTagIds]);

  // 按维度分组（仅受控维度；其余归「其他」）
  const grouped = useMemo(() => {
    const result: { dim: string; label: string; tags: Tag[] }[] = [];
    for (const { dim, label } of DIMENSION_META) {
      const dimTags = tags
        .filter((t) => t.namespace === dim)
        .sort((a, b) => (b.item_count || 0) - (a.item_count || 0));
      result.push({ dim, label, tags: dimTags });
    }
    const others = tags.filter((t) => !CONTROLLED_DIMS.has(t.namespace));
    if (others.length) {
      result.push({
        dim: "other", label: "其他",
        tags: [...others].sort((a, b) => (b.item_count || 0) - (a.item_count || 0)),
      });
    }
    return result;
  }, [tags]);

  // 搜索过滤后的分组
  const visibleGroups = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return grouped;
    return grouped.map((g) => ({
      ...g,
      tags: g.tags.filter((t) =>
        `${tagLabel(t)} ${t.value} ${g.label}`.toLocaleLowerCase().includes(needle)),
    })).filter((g) => g.tags.length > 0);
  }, [grouped, query]);

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const { id: tagId } = confirmDelete;
    setDeleting(tagId);
    try {
      await deleteTag(tagId);
      setTags((prev) => prev.filter((t) => t.id !== tagId));
      // 若删除的是已选中标签，清掉该维度选择
      setSelected((prev) => {
        const next = { ...prev };
        for (const d of Object.keys(next)) if (next[d] === tagId) next[d] = "";
        return next;
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
    setDeleting(null);
    setConfirmDelete(null);
  };

  const executeMerge = async () => {
    setConfirmMerge(false);
    setMerging(true);
    setMergeMsg(null);
    try {
      const res = await mergeTags(mergeSource, mergeTarget);
      setMergeMsg(`合并完成：转移 ${res.moved_items} 条，已删除源标签`);
      setMergeSource("");
      setMergeTarget("");
      await load();
    } catch (e) {
      setMergeMsg(`合并失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setMerging(false);
  };

  const handleUpdate = async (tagId: string, data: Partial<Tag>) => {
    try {
      const updated = await updateTag(tagId, data);
      setTags((prev) => prev.map((t) => (t.id === tagId ? updated : t)));
      setEditing(null);
    } catch (e) {
      alert(e instanceof Error ? e.message : "更新失败");
    }
  };

  if (loading) return <div className="loading">加载标签...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page tags-page">
      <div className="page-header tags-page-header">
        <div>
          <h2>标签系统</h2>
          <p className="text-muted">按维度分行浏览，点击标签组合筛选信息</p>
        </div>
        <div className="tags-page-summary"><Tags size={16} /><strong>{tags.length}</strong><span>个标签 · {DIMENSION_META.length} 个维度</span></div>
      </div>

      {/* 组合筛选栏 */}
      <div className="tags-filter-bar">
        <div className="tags-filter-chips">
          <Filter size={14} />
          {selectedTagIds.length === 0 ? (
            <span className="text-muted">尚未选择标签，点击下方任意标签开始组合筛选</span>
          ) : (
            selectedTagIds.map((id) => {
              const t = tags.find((x) => x.id === id);
              const dim = t?.namespace ?? "";
              return (
                <button
                  key={id}
                  type="button"
                  className="tag-filter-chip"
                  style={{ borderColor: DIM_COLORS[dim] ?? "var(--line)" }}
                  onClick={() => t && toggleTag(t.namespace, id)}
                  title="点击取消该标签"
                >
                  {t ? tagLabel(t) : id}
                  <X size={12} />
                </button>
              );
            })
          )}
          {selectedTagIds.length > 0 && (
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={clearSelection}>清空</button>
              <button type="button" className="btn btn-primary btn-sm" onClick={goToItems} disabled={filtering}>
                <List size={13} />
                查看信息 {filteredItems ? `(${filteredItems.total})` : ""}
              </button>
            </>
          )}
        </div>
      </div>

      <section className="tags-workspace">
        <div className="tags-main" style={{ width: "100%" }}>
          <div className="tags-toolbar">
            <label className="tags-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索标签" /></label>
            <span>{tags.length} 项</span>
          </div>

          {/* 多维分组：每维度一行，标签横向排列可点击 */}
          <div className="tags-dimension-board">
            {visibleGroups.map((group) => (
              <div key={group.dim} className="tags-dimension-row">
                <div className="tags-dimension-head" style={{ borderLeftColor: DIM_COLORS[group.dim] ?? "var(--accent)" }}>
                  <span className="tags-dimension-label">{group.label}</span>
                  <span className="tags-dimension-count">{group.tags.length}</span>
                </div>
                <div className="tags-dimension-tags">
                  {group.tags.map((tag) => {
                    const active = selected[group.dim] === tag.id;
                    return (
                      <button
                        key={tag.id}
                        type="button"
                        className={`tag-pill ${active ? "tag-pill--active" : ""}`}
                        style={active ? { borderColor: DIM_COLORS[group.dim] ?? "var(--accent)", background: `${DIM_COLORS[group.dim] ?? "var(--accent)"}1a` } : undefined}
                        onClick={() => toggleTag(group.dim, tag.id)}
                        title={`点击${active ? "取消" : "选择"}「${tagLabel(tag)}」筛选`}
                      >
                        <i className="tag-pill-dot" style={{ background: tag.color || DIM_COLORS[group.dim] || "var(--accent)" }} />
                        <span className="tag-pill-label">{tagLabel(tag)}</span>
                        {tag.item_count > 0 && <span className="tag-pill-count">{tag.item_count}</span>}
                      </button>
                    );
                  })}
                  {group.tags.length === 0 && <span className="text-muted" style={{ fontSize: 13 }}>暂无标签</span>}
                </div>
              </div>
            ))}
          </div>

          {/* 标签明细表（管理用：编辑/删除/合并） */}
          <details className="tags-merge-panel" style={{ marginTop: 16 }}>
            <summary><span><GitMerge size={14} />标签明细与管理</span><small>编辑、删除、合并标签</small></summary>
            <div className="tag-stats-table tags-table">
              <table>
                <thead><tr><th>标签</th><th>维度</th><th>使用量</th><th>最近出现</th><th aria-label="操作" /></tr></thead>
                <tbody>{tags.filter((t) => {
                  const needle = query.trim().toLocaleLowerCase();
                  return !needle || `${tagLabel(t)} ${t.value} ${t.namespace}`.toLocaleLowerCase().includes(needle);
                }).map((tag) => (
                  <tr key={tag.id}>
                    <td><div className="tag-name-cell"><i style={{ background: tag.color || "var(--accent)" }} /><span>{tagLabel(tag)}</span>{tag.label && tag.label !== tag.value && <small>{tag.value}</small>}</div></td>
                    <td><span className="tag-namespace-badge">{DIMENSION_META.find((d) => d.dim === tag.namespace)?.label ?? tag.namespace}</span></td>
                    <td><strong>{tag.item_count}</strong></td>
                    <td className="text-muted small">{tag.last_seen_at ? formatBeijingDateTime(tag.last_seen_at) : "-"}</td>
                    <td><div className="tag-table-actions"><button type="button" className="btn-icon" onClick={() => setEditing(tag)} title="编辑"><Edit3 size={13} /></button><button type="button" className="btn-icon tag-delete-action" onClick={() => setConfirmDelete({ id: tag.id, value: tag.value })} disabled={deleting === tag.id} title="删除"><Trash2 size={13} /></button></div></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>

            <div className="tags-merge-controls" style={{ padding: 12 }}>
              <div className="gen-field">
                <label className="gen-label" htmlFor="merge-src">源标签 (将被删除)</label>
                <select id="merge-src" value={mergeSource} onChange={(e) => setMergeSource(e.target.value)}>
                  <option value="">-- 请选择 --</option>
                  {tags.map((t) => <option key={t.id} value={t.id}>{t.namespace}:{tagLabel(t)} ({t.item_count})</option>)}
                </select>
              </div>
              <div className="gen-field">
                <label className="gen-label" htmlFor="merge-tgt">目标标签 (保留)</label>
                <select id="merge-tgt" value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)}>
                  <option value="">-- 请选择 --</option>
                  {tags.map((t) => <option key={t.id} value={t.id}>{t.namespace}:{tagLabel(t)} ({t.item_count})</option>)}
                </select>
              </div>
              <button type="button" className="btn btn-secondary" onClick={() => { if (!mergeSource || !mergeTarget) { alert("请选择源标签和目标标签"); return; } if (mergeSource === mergeTarget) { alert("源标签和目标标签不能相同"); return; } setConfirmMerge(true); }} disabled={merging || !mergeSource || !mergeTarget}>
                <GitMerge size={14} className={merging ? "spin" : ""} />
                {merging ? "合并中..." : "合并"}
              </button>
            </div>
            {mergeMsg && <div className="toast" onClick={() => setMergeMsg(null)}>{mergeMsg}</div>}
          </details>
        </div>
      </section>

      <ConfirmDialog
        open={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={() => void executeDelete()}
        title="删除标签"
        message={`确定删除标签「${confirmDelete?.value ?? ""}」吗？`}
        variant="danger"
        confirmLabel="删除"
      />
      <ConfirmDialog
        open={confirmMerge}
        onClose={() => setConfirmMerge(false)}
        onConfirm={() => void executeMerge()}
        title="合并标签"
        message="确定合并吗？源标签的所有信息关联将转移到目标标签，源标签将被删除。"
        variant="danger"
        confirmLabel="合并"
      />

      {editing && (
        <TagEditModal tag={editing} onSave={handleUpdate} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}

// ── Tag Edit Modal ────────────────────────────────────────────────────

function TagEditModal({
  tag, onSave, onClose,
}: {
  tag: Tag;
  onSave: (id: string, data: Partial<Tag>) => Promise<void>;
  onClose: () => void;
}) {
  const [value, setValue] = useState(tag.value);
  const [namespace, setNamespace] = useState(tag.namespace);
  const [label, setLabel] = useState(tag.label ?? "");
  const [color, setColor] = useState(tag.color ?? "#3b82f6");
  const [saving, setSaving] = useState(false);

  const colors = ["#3b82f6", "#22c55e", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#e11d48", "#ffffff"];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--config" onClick={(e) => e.stopPropagation()}>
        <h3>编辑标签</h3>
        <p className="text-muted small" style={{ marginBottom: 16 }}>ID: {tag.id}</p>
        <div className="form-grid">
          <label>标签值 <input value={value} onChange={(e) => setValue(e.target.value)} /></label>
          <label>命名空间 <input value={namespace} onChange={(e) => setNamespace(e.target.value)} /></label>
          <label className="span-2">显示名称 <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={tag.value} /></label>
          <label className="span-2">颜色
            <div className="color-picker-row">
              {colors.map((c) => (
                <button key={c} type="button" className={`color-swatch ${color === c ? "color-swatch--active" : ""}`} style={{ background: c, border: c === "#ffffff" ? "1px solid var(--line)" : undefined }} onClick={() => setColor(c)} />
              ))}
              <input type="color" value={color} onChange={(e) => setColor(e.target.value)} style={{ width: 32, height: 32, padding: 0, border: "none", cursor: "pointer" }} />
            </div>
          </label>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" disabled={saving || !value} onClick={async () => { setSaving(true); await onSave(tag.id, { value, namespace, label: label || null, color: color === "#ffffff" ? null : color }); setSaving(false); }}>{saving ? "保存中..." : "保存"}</button>
        </div>
      </div>
    </div>
  );
}
