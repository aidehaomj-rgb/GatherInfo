import { useCallback, useEffect, useState } from "react";
import { Edit3, Plus, Trash2 } from "lucide-react";

import { createPromptTemplate, deletePromptTemplate, fetchPromptTemplates, updatePromptTemplate } from "../api";
import type { PromptTemplate } from "../types";
import { ConfirmDialog } from "./shared/ConfirmDialog";

type EditorState = Pick<PromptTemplate, "name" | "description" | "content" | "is_active">;

const EMPTY_EDITOR: EditorState = { name: "", description: "", content: "", is_active: true };

function compactPromptPreview(content: string) {
  return content.replace(/\s+/g, " ").trim();
}

export function PromptTemplatesPage() {
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<PromptTemplate | null | undefined>(undefined);
  const [form, setForm] = useState<EditorState>(EMPTY_EDITOR);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<PromptTemplate | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPrompts(await fetchPromptTemplates());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提示词加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const openEditor = (prompt: PromptTemplate | null) => {
    setEditing(prompt);
    setForm(prompt ? {
      name: prompt.name,
      description: prompt.description ?? "",
      content: prompt.content,
      is_active: prompt.is_active,
    } : EMPTY_EDITOR);
  };

  const save = async () => {
    if (!form.name.trim() || !form.content.trim()) return;
    setSaving(true);
    try {
      const payload = { ...form, name: form.name.trim(), content: form.content.trim(), description: form.description?.trim() || null };
      if (editing) await updatePromptTemplate(editing.id, payload);
      else await createPromptTemplate(payload);
      setEditing(undefined);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提示词保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="loading">加载提示词...</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div><h2>提示词库</h2><p className="text-muted">集中维护主题和专家流程使用的采集指令。</p></div>
        <button type="button" className="btn btn-primary" onClick={() => openEditor(null)}><Plus size={14} /> 新建提示词</button>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="prompt-template-grid">
        {prompts.map((prompt) => (
          <article className="card-item prompt-template-card" key={prompt.id}>
            <div className="card-item-header">
              <h4 title={prompt.name}>{prompt.name}</h4>
              <div className="card-item-actions">
                <span className={`badge ${prompt.is_active ? "badge--green" : "badge--gray"}`}>{prompt.is_active ? "启用" : "停用"}</span>
                {(prompt.linked_experts ?? []).map((expert) => <span className="badge badge--blue" key={expert}>关联 {expert}</span>)}
              </div>
            </div>
            <p className="prompt-template-card__description">{prompt.description || "暂无说明"}</p>
            <p className="prompt-template-card__preview">{compactPromptPreview(prompt.content)}</p>
            <div className="card-item-footer">
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => openEditor(prompt)}><Edit3 size={12} /> 编辑</button>
              <button type="button" className="btn btn-sm btn-danger" onClick={() => setDeleting(prompt)}><Trash2 size={12} /> 删除</button>
            </div>
          </article>
        ))}
        {prompts.length === 0 && <div className="empty">暂无提示词。</div>}
      </div>
      {editing !== undefined && (
        <div className="modal-overlay" onClick={() => setEditing(undefined)}>
          <div className="modal modal--config" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header-with-actions"><h3>{editing ? "编辑提示词" : "新建提示词"}</h3><span className="text-muted small">正文会在采集时并入主题语义指令。</span></div>
            <div className="form-grid">
              <label><span className="field-label-row">名称 <span className="required-mark">*</span></span><input required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></label>
              <label>状态<select value={form.is_active ? "1" : "0"} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.value === "1" }))}><option value="1">启用</option><option value="0">停用</option></select></label>
              <label className="span-2">说明<input value={form.description ?? ""} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} /></label>
              <label className="span-2"><span className="field-label-row">提示词正文 <span className="required-mark">*</span></span><textarea required rows={18} value={form.content} onChange={(event) => setForm((current) => ({ ...current, content: event.target.value }))} /></label>
            </div>
            <div className="modal-actions"><button type="button" className="btn btn-ghost" onClick={() => setEditing(undefined)}>取消</button><button type="button" className="btn btn-primary" disabled={saving || !form.name.trim() || !form.content.trim()} onClick={() => void save()}>{saving ? "保存中..." : "保存"}</button></div>
          </div>
        </div>
      )}
      <ConfirmDialog open={!!deleting} title="删除提示词" message={`删除“${deleting?.name ?? ""}”？已挂载的主题会自动解绑。`} confirmLabel="删除" variant="danger" onClose={() => setDeleting(null)} onConfirm={async () => { if (!deleting) return; await deletePromptTemplate(deleting.id); setDeleting(null); await load(); }} />
    </div>
  );
}
