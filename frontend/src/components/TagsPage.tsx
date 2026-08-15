import { useEffect, useMemo, useState, useCallback } from "react";
import { fetchTags, updateTag, deleteTag, mergeTags, fetchItems } from "../api";
import type { Tag, CollectedItem } from "../types";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { Trash2, Edit3, GitMerge, List, Search, Tags } from "lucide-react";
import { formatBeijingDateTime, formatBeijingDate } from "../utils/date";

/** Namespace → 中文显示名 (回退到原始 namespace)。 */
const NS_LABELS: Record<string, string> = {
  category: "类别",
  region: "区域",
  commodity: "商品",
  country: "国家",
  product: "产品",
  event: "事件",
  regulation: "法规",
  sector: "行业",
};
const nsLabel = (ns: string): string => NS_LABELS[ns] ?? ns;
/** 标签显示名：优先中文 label，回退英文 value。 */
const tagLabel = (t: { label?: string | null; value: string }): string => t.label || t.value;

export function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ns, setNs] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<"count" | "name" | "recent">("count");
  const [editing, setEditing] = useState<Tag | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  // Merge controls
  const [mergeSource, setMergeSource] = useState("");
  const [mergeTarget, setMergeTarget] = useState("");
  const [merging, setMerging] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; value: string} | null>(null);
  const [confirmMerge, setConfirmMerge] = useState(false);
  const [mergeMsg, setMergeMsg] = useState<string | null>(null);
  // Tag detail (last items)
  const [detailTag, setDetailTag] = useState<Tag | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const t = await fetchTags(undefined, 1000);
      setTags(t);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleMerge = async () => {
    if (!mergeSource || !mergeTarget) { alert("请选择源标签和目标标签"); return; }
    if (mergeSource === mergeTarget) { alert("源标签和目标标签不能相同"); return; }
    const srcTag = tags.find((t) => t.id === mergeSource);
    const tgtTag = tags.find((t) => t.id === mergeTarget);
    setConfirmMerge(true);
    return;
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

  const handleDelete = (tagId: string, tagValue: string) => {
    setConfirmDelete({ id: tagId, value: tagValue });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const { id: tagId, value: tagValue } = confirmDelete;
    setDeleting(tagId);
    try {
      await deleteTag(tagId);
      setTags((prev) => prev.filter((t) => t.id !== tagId));
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
    setDeleting(null);
    setConfirmDelete(null);
  };

  const handleUpdate = async (tagId: string, data: Partial<Tag>) => {
    try {
      const updated = await updateTag(tagId, data);
      setTags((prev) => prev.map((t) => t.id === tagId ? updated : t));
      setEditing(null);
    } catch (e) {
      alert(e instanceof Error ? e.message : "更新失败");
    }
  };

  const namespaceCounts = useMemo(() => tags.reduce<Record<string, number>>((counts, tag) => ({
    ...counts, [tag.namespace]: (counts[tag.namespace] || 0) + 1,
  }), {}), [tags]);
  const namespaces = useMemo(() => Object.keys(namespaceCounts).sort((a, b) => namespaceCounts[b] - namespaceCounts[a]), [namespaceCounts]);
  const visibleTags = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    const rows = tags.filter((tag) => (!ns || tag.namespace === ns)
      && (!needle || `${tagLabel(tag)} ${tag.value} ${nsLabel(tag.namespace)}`.toLocaleLowerCase().includes(needle)));
    return [...rows].sort((a, b) => sort === "count"
      ? b.item_count - a.item_count || tagLabel(a).localeCompare(tagLabel(b), "zh-CN")
      : sort === "recent"
        ? String(b.last_seen_at || "").localeCompare(String(a.last_seen_at || ""))
        : tagLabel(a).localeCompare(tagLabel(b), "zh-CN"));
  }, [tags, ns, query, sort]);

  if (loading) return <div className="loading">加载标签...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page tags-page">
      <div className="page-header tags-page-header">
        <div>
          <h2>标签系统</h2>
          <p className="text-muted">统一查看、整理和合并信息标签</p>
        </div>
        <div className="tags-page-summary"><Tags size={16} /><strong>{tags.length}</strong><span>个标签</span></div>
      </div>

      <section className="tags-workspace">
        <nav className="tags-namespaces" aria-label="标签分类">
          <button type="button" className={!ns ? "active" : ""} onClick={() => setNs("")}><span>全部标签</span><strong>{tags.length}</strong></button>
          {namespaces.map((name) => <button type="button" key={name} className={ns === name ? "active" : ""} onClick={() => setNs(name)}><span>{nsLabel(name)}</span><strong>{namespaceCounts[name]}</strong></button>)}
        </nav>

        <div className="tags-main">
          <div className="tags-toolbar">
            <label className="tags-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索标签" /></label>
            <select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} aria-label="标签排序">
              <option value="count">按使用量</option><option value="recent">按最近出现</option><option value="name">按名称</option>
            </select>
            <span>{visibleTags.length} 项</span>
          </div>

          <div className="tag-stats-table tags-table">
            <table><thead><tr><th>标签</th><th>分类</th><th>使用量</th><th>最近出现</th><th aria-label="操作" /></tr></thead>
            <tbody>{visibleTags.map((tag) => <tr key={tag.id}>
              <td><div className="tag-name-cell"><i style={{ background: tag.color || "var(--accent)" }} /><button type="button" onClick={() => setDetailTag(tag)}>{tagLabel(tag)}</button>{tag.label && tag.label !== tag.value && <small>{tag.value}</small>}</div></td>
              <td><span className="tag-namespace-badge">{nsLabel(tag.namespace)}</span></td>
              <td><strong>{tag.item_count}</strong></td>
              <td className="text-muted small">{tag.last_seen_at ? formatBeijingDateTime(tag.last_seen_at) : "-"}</td>
              <td><div className="tag-table-actions"><button type="button" className="btn-icon" onClick={() => setDetailTag(tag)} title="查看条目"><List size={13} /></button><button type="button" className="btn-icon" onClick={() => setEditing(tag)} title="编辑"><Edit3 size={13} /></button><button type="button" className="btn-icon tag-delete-action" onClick={() => handleDelete(tag.id, tag.value)} disabled={deleting === tag.id} title="删除"><Trash2 size={13} /></button></div></td>
            </tr>)}</tbody></table>
            {!visibleTags.length && <div className="tags-empty">没有符合条件的标签</div>}
          </div>

          <details className="tags-merge-panel">
            <summary><span><GitMerge size={14} />合并重复标签</span><small>将源标签关系转移到目标标签</small></summary>
            <div className="tags-merge-controls">
          <div className="gen-field">
            <label className="gen-label" htmlFor="merge-src">源标签 (将被删除)</label>
            <select id="merge-src" value={mergeSource} onChange={(e) => setMergeSource(e.target.value)}>
              <option value="">-- 请选择 --</option>
              {visibleTags.map((t) => (
                <option key={t.id} value={t.id}>{nsLabel(t.namespace)}:{tagLabel(t)} ({t.item_count})</option>
              ))}
            </select>
          </div>
          <div className="gen-field">
            <label className="gen-label" htmlFor="merge-tgt">目标标签 (保留)</label>
            <select id="merge-tgt" value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)}>
              <option value="">-- 请选择 --</option>
              {visibleTags.map((t) => (
                <option key={t.id} value={t.id}>{nsLabel(t.namespace)}:{tagLabel(t)} ({t.item_count})</option>
              ))}
            </select>
          </div>
          <button type="button" className="btn btn-secondary" onClick={handleMerge} disabled={merging || !mergeSource || !mergeTarget}>
            <GitMerge size={14} className={merging ? "spin" : ""} />
            {merging ? "合并中..." : "合并"}
          </button>
            </div>
            {mergeMsg && <div className="toast" onClick={() => setMergeMsg(null)}>{mergeMsg}</div>}
          </details>
        </div>
      </section>

      {/* Tag Edit Modal */}
      {editing && (
        <TagEditModal
          tag={editing}
          onSave={handleUpdate}
          onClose={() => setEditing(null)}
        />
      )}

      {/* Tag Detail Modal (last 10 items) */}
      {detailTag && (
        <TagDetailModal
          tag={detailTag}
          onClose={() => setDetailTag(null)}
        />
      )}
    </div>
  );
}
// ── Tag Detail Modal ──────────────────────────────────────────────────

function TagDetailModal({ tag, onClose }: { tag: Tag; onClose: () => void }) {
  const [items, setItems] = useState<CollectedItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchItems({ tag: tag.id, page_size: 10, page: 1 })
      .then((res) => { if (active) setItems(res.items); })
      .catch(() => { if (active) setItems([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [tag.id]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 640, maxWidth: "95vw" }}>
        <h3>{tag.namespace}:{tag.value}</h3>
        <p className="text-muted small">共 {tag.item_count} 条 · 显示最近 10 条</p>
        {loading ? (
          <div className="loading">加载中...</div>
        ) : items.length === 0 ? (
          <p className="text-muted">暂无关联条目。</p>
        ) : (
          <ul className="tag-detail-list">
            {items.map((it) => (
              <li key={it.id}>
                {it.url ? (
                  <a href={it.url} target="_blank" rel="noreferrer">{it.title || it.id}</a>
                ) : (
                  <span>{it.title || it.id}</span>
                )}
                <span className="text-muted small">
                  {it.source_id}
                    {it.collected_at && ` · ${formatBeijingDate(it.collected_at)}`}
                </span>
              </li>
            ))}
          </ul>
        )}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>关闭</button>
        </div>
      </div>
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
                <button
                  key={c}
                  type="button"
                  className={`color-swatch ${color === c ? "color-swatch--active" : ""}`}
                  style={{ background: c, border: c === "#ffffff" ? "1px solid var(--line)" : undefined }}
                  onClick={() => setColor(c)}
                />
              ))}
              <input type="color" value={color} onChange={(e) => setColor(e.target.value)} style={{ width: 32, height: 32, padding: 0, border: "none", cursor: "pointer" }} />
            </div>
          </label>
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" disabled={saving || !value} onClick={async () => {
            setSaving(true);
            await onSave(tag.id, {
              value, namespace,
              label: label || null,
              color: color === "#ffffff" ? null : color,
            });
            setSaving(false);
          }}>{saving ? "保存中..." : "保存"}</button>
        </div>
      </div>
    </div>
  );
}

