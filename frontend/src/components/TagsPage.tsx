import { useEffect, useState, useCallback } from "react";
import { fetchTags, fetchTagStats, updateTag, deleteTag, mergeTags, fetchItems } from "../api";
import type { Tag, TagStats, CollectedItem } from "../types";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { EChart } from "./EChart";
import { Trash2, Edit3, GitMerge, List } from "lucide-react";
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
  const [stats, setStats] = useState<TagStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ns, setNs] = useState("");
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
      const [t, s] = await Promise.all([
        fetchTags(ns || undefined, 200),
        fetchTagStats(),
      ]);
      setTags(t);
      setStats(s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, [ns]);

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
      setStats((prev) => prev.filter((s) => s.tag_id !== tagId));
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

  const namespaces = [...new Set(tags.map((t) => t.namespace))].sort();

  const bubbleData = stats.slice(0, 30).map((s, i) => ({
    name: s.value,
    value: [i % 5, s.item_count, s.tag_id, s.item_count],
    symbolSize: Math.max(8, Math.min(60, Math.sqrt(s.item_count) * 6)),
    itemStyle: { color: COLORS[i % COLORS.length] },
  }));

  if (loading) return <div className="loading">加载标签...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>标签系统</h2>
          <p className="text-muted">标签是信息的核心结构化维度。每条信息自动打标签后可按标签过滤和统计。</p>
        </div>
      </div>

      <div className="chip-row">
        <button type="button" className={`chip ${!ns ? "chip--blue" : ""}`} onClick={() => setNs("")}>全部 ({tags.length})</button>
        {namespaces.map((n) => (
          <button type="button" key={n} className={`chip ${ns === n ? "chip--blue" : ""}`} onClick={() => setNs(n)}>
            {nsLabel(n)}
          </button>
        ))}
      </div>

      <div className="panel">
        <h3>标签云</h3>
        <div className="tag-cloud">
          {tags.map((t) => (
            <div key={t.id} className="tag-chip-group">
              {t.color && <span className="tag-dot" style={{ background: t.color }} />}
              <span
                className="tag-chip"
                title={`${nsLabel(t.namespace)} · ${t.value} — ${t.item_count} 条 | 点击编辑`}
                onClick={() => setEditing(t)}
                style={{ cursor: "pointer" }}
              >
                {tagLabel(t)}
                <em>{t.item_count}</em>
              </span>
              <button type="button" className="tag-chip-action" onClick={() => setEditing(t)} title="编辑标签">
                <Edit3 size={10} />
              </button>
              <button type="button" className="tag-chip-action" onClick={() => handleDelete(t.id, t.value)} disabled={deleting === t.id} title="删除标签">
                <Trash2 size={10} />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <h3><GitMerge size={14} /> 合并标签</h3>
        <p className="text-muted small">将源标签的所有条目关系转移到目标标签，随后删除源标签。常用于消除重复或近义标签。</p>
        <div className="gen-controls-row">
          <div className="gen-field">
            <label className="gen-label" htmlFor="merge-src">源标签 (将被删除)</label>
            <select id="merge-src" value={mergeSource} onChange={(e) => setMergeSource(e.target.value)}>
              <option value="">-- 请选择 --</option>
              {tags.map((t) => (
                <option key={t.id} value={t.id}>{nsLabel(t.namespace)}:{tagLabel(t)} ({t.item_count})</option>
              ))}
            </select>
          </div>
          <div className="gen-field">
            <label className="gen-label" htmlFor="merge-tgt">目标标签 (保留)</label>
            <select id="merge-tgt" value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)}>
              <option value="">-- 请选择 --</option>
              {tags.map((t) => (
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
      </div>

      <div className="panel">
        <h3>标签管理 ({tags.length})</h3>
        <div className="tag-stats-table">
          <table>
            <thead>
              <tr>
                <th>标签</th>
                <th>命名空间</th>
                <th>条目数</th>
                <th>颜色</th>
                <th>最后出现</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {tags.map((t) => (
                <tr key={t.id}>
                  <td><strong>{tagLabel(t)}</strong>{t.label && t.label !== t.value && <span className="text-muted small"> ({t.value})</span>}</td>
                  <td><span className="chip">{nsLabel(t.namespace)}</span></td>
                  <td>{t.item_count}</td>
                  <td>
                    {t.color ? (
                      <span className="tag-dot" style={{ background: t.color, display: "inline-block", width: 16, height: 16, borderRadius: 4, verticalAlign: "middle" }} />
                    ) : <span className="text-muted">-</span>}
                  </td>
                  <td className="text-muted small">
                    {t.last_seen_at ? formatBeijingDateTime(t.last_seen_at) : "-"}
                  </td>
                  <td>
                    <div className="tag-table-actions">
                      <button type="button" className="btn-icon" onClick={() => setDetailTag(t)} title="查看最近条目">
                        <List size={12} />
                      </button>
                      <button type="button" className="btn-icon" onClick={() => setEditing(t)} title="编辑">
                        <Edit3 size={12} />
                      </button>
                      <button type="button" className="btn-icon" onClick={() => handleDelete(t.id, t.value)} disabled={deleting === t.id} title="删除" style={{ color: "var(--red)" }}>
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

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
      {confirmDelete && (
        <ConfirmDialog
          open={true}
          title="删除标签"
          message={`确认删除标签 "${confirmDelete.value}"？关联的条目将移除该标签。`}
          variant="danger"
          confirmLabel="删除"
          cancelLabel="取消"
          onConfirm={() => void executeDelete()}
          onClose={() => setConfirmDelete(null)}
        />
      )}
      {confirmMerge && (
        <ConfirmDialog
          open={true}
          title="合并标签"
          message={`确认将源标签合并到目标标签？合并后源标签将被删除，其关联条目转移到目标标签。`}
          variant="default"
          confirmLabel="合并"
          cancelLabel="取消"
          onConfirm={() => void executeMerge()}
          onClose={() => setConfirmMerge(false)}
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

const COLORS = [
  "#3b82f6","#22c55e","#f59e0b","#8b5cf6","#ec4899",
  "#06b6d4","#f97316","#14b8a6","#e11d48","#8b5cf6",
];
