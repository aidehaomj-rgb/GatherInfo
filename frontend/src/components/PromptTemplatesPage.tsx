import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpenText, Download, Edit3, FileText, Plus, Trash2, Upload } from "lucide-react";

import {
  createPromptTemplate,
  deletePromptTemplate,
  exportPromptTemplates,
  fetchPromptTemplates,
  importPromptTemplates,
  updatePromptTemplate,
} from "../api";
import type { PromptTemplate } from "../types";

type Kind = "prompt" | "playbook";
type EditorState = Pick<PromptTemplate, "name" | "description" | "content" | "is_active" | "kind">;
type PasswordAction = { action: "edit" | "delete"; target: PromptTemplate };

const EMPTY_EDITOR: EditorState = { name: "", description: "", content: "", is_active: true, kind: "prompt" };

function compactPromptPreview(content: string) {
  return content.replace(/\s+/g, " ").trim();
}

export function PromptTemplatesPage() {
  const [tab, setTab] = useState<Kind>("prompt");
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<PromptTemplate | null | undefined>(undefined);
  const [form, setForm] = useState<EditorState>(EMPTY_EDITOR);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [passwordGate, setPasswordGate] = useState<PasswordAction | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (kind: Kind) => {
    setLoading(true);
    try {
      setPrompts(await fetchPromptTemplates(kind));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(tab); }, [tab, load]);

  const openEditor = (prompt: PromptTemplate | null) => {
    setEditing(prompt);
    setForm(prompt ? {
      name: prompt.name,
      description: prompt.description ?? "",
      content: prompt.content,
      is_active: prompt.is_active,
      kind: prompt.kind,
    } : { ...EMPTY_EDITOR, kind: tab });
  };

  const save = async () => {
    if (!form.name.trim() || !form.content.trim()) return;
    setSaving(true);
    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        content: form.content.trim(),
        description: form.description?.trim() || null,
      };
      if (editing) await updatePromptTemplate(editing.id, payload);
      else await createPromptTemplate(payload);
      setEditing(undefined);
      await load(tab);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    try {
      const data = await exportPromptTemplates(tab);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `prompt-templates-${tab}-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(`已导出 ${data.count} 套到备份文件。`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "导出失败");
    }
  };

  const doImport = async (text: string) => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      setError("导入失败：不是有效的 JSON 文件。");
      return;
    }
    const list = Array.isArray(parsed)
      ? (parsed as Partial<PromptTemplate>[])
      : ((parsed as { prompts?: Partial<PromptTemplate>[] }).prompts ?? []);
    if (!Array.isArray(list) || list.length === 0) {
      setError("导入失败：文件中没有可导入的提示词数据。");
      return;
    }
    try {
      const result = await importPromptTemplates(list);
      setNotice(`导入完成：新建 ${result.created} 套，更新 ${result.updated} 套。`);
      await load(tab);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "导入失败");
    }
  };

  const onFileSelected = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => void doImport(String(reader.result ?? ""));
    reader.readAsText(file);
  };

  // 口令门控：编辑需输入 "edit"，删除需输入 "delete"
  const requestEdit = (prompt: PromptTemplate) => setPasswordGate({ action: "edit", target: prompt });
  const requestDelete = (prompt: PromptTemplate) => setPasswordGate({ action: "delete", target: prompt });

  const onPasswordConfirm = async (raw: string) => {
    if (!passwordGate) return;
    const { action, target } = passwordGate;
    setPasswordGate(null);
    const input = raw.trim();
    if (action === "edit") {
      if (input === "edit") openEditor(target);
      else setError("口令错误，无法进入编辑。");
      return;
    }
    if (input === "delete") {
      try {
        await deletePromptTemplate(target.id);
        await load(tab);
        setNotice(`已删除“${target.name}”。`);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "删除失败");
      }
    } else {
      setError("口令错误，无法删除。");
    }
  };

  const isPlaybook = tab === "playbook";
  const tabTitle = isPlaybook ? "采集处理宝典" : "提示词库";
  const tabDesc = isPlaybook
    ? "采集方法指引：发现、核验、编排与合规采集方法论，不直接参与信息采集。"
    : "采集信息时使用的提示词，可挂载到主题并并入采集语义指令。";

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>{tabTitle}</h2>
          <p className="text-muted">{tabDesc}</p>
        </div>
        <div className="page-header-actions">
          <input ref={fileInputRef} type="file" accept=".json,application/json" style={{ display: "none" }} onChange={onFileSelected} />
          <button type="button" className="btn btn-ghost" onClick={() => fileInputRef.current?.click()}><Upload size={14} /> 导入</button>
          <button type="button" className="btn btn-ghost" onClick={() => void handleExport()}><Download size={14} /> 导出</button>
          <button type="button" className="btn btn-primary" onClick={() => openEditor(null)}><Plus size={14} /> 新建</button>
        </div>
      </div>

      {/* 板块切换：提示词库 / 采集处理宝典 */}
      <div className="segmented-control" style={{ marginBottom: 16 }}>
        <button type="button" className={`seg-btn${tab === "prompt" ? " seg-btn--active" : ""}`} onClick={() => setTab("prompt")}>
          <FileText size={14} /> 提示词库
        </button>
        <button type="button" className={`seg-btn${tab === "playbook" ? " seg-btn--active" : ""}`} onClick={() => setTab("playbook")}>
          <BookOpenText size={14} /> 采集处理宝典
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {notice && <div className="notice-banner">{notice}</div>}

      {loading ? (
        <div className="loading">加载中...</div>
      ) : (
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
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => requestEdit(prompt)}><Edit3 size={12} /> 编辑</button>
                <button type="button" className="btn btn-sm btn-danger" onClick={() => requestDelete(prompt)}><Trash2 size={12} /> 删除</button>
              </div>
            </article>
          ))}
          {prompts.length === 0 && <div className="empty">暂无{isPlaybook ? "采集处理宝典" : "提示词"}。</div>}
        </div>
      )}

      {editing !== undefined && (
        <div className="modal-overlay" onClick={() => setEditing(undefined)}>
          <div className="modal modal--config" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header-with-actions">
              <h3>{editing ? "编辑" : "新建"}{tabTitle}</h3>
              <span className="text-muted small">正文会在采集时并入主题语义指令。</span>
            </div>
            <div className="form-grid">
              <label><span className="field-label-row">名称 <span className="required-mark">*</span></span><input required value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></label>
              <label>板块<select value={form.kind} onChange={(event) => setForm((current) => ({ ...current, kind: event.target.value as Kind }))}><option value="prompt">提示词库</option><option value="playbook">采集处理宝典</option></select></label>
              <label>状态<select value={form.is_active ? "1" : "0"} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.value === "1" }))}><option value="1">启用</option><option value="0">停用</option></select></label>
              <label className="span-2">说明<input value={form.description ?? ""} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} /></label>
              <label className="span-2"><span className="field-label-row">正文 <span className="required-mark">*</span></span><textarea required rows={18} value={form.content} onChange={(event) => setForm((current) => ({ ...current, content: event.target.value }))} /></label>
            </div>
            <div className="modal-actions"><button type="button" className="btn btn-ghost" onClick={() => setEditing(undefined)}>取消</button><button type="button" className="btn btn-primary" disabled={saving || !form.name.trim() || !form.content.trim()} onClick={() => void save()}>{saving ? "保存中..." : "保存"}</button></div>
          </div>
        </div>
      )}

      {passwordGate && (
        <PasswordGateDialog
          action={passwordGate.action}
          name={passwordGate.target.name}
          onClose={() => setPasswordGate(null)}
          onConfirm={(input) => void onPasswordConfirm(input)}
        />
      )}
    </div>
  );
}

function PasswordGateDialog({
  action,
  name,
  onClose,
  onConfirm,
}: {
  action: "edit" | "delete";
  name: string;
  onClose: () => void;
  onConfirm: (input: string) => void;
}) {
  const [input, setInput] = useState("");
  const isDelete = action === "delete";
  const expected = isDelete ? "delete" : "edit";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--config" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header-with-actions">
          <h3>{isDelete ? "删除确认" : "编辑确认"}</h3>
        </div>
        <p className="text-muted small" style={{ margin: "0 0 12px" }}>
          {isDelete ? `即将删除“${name}”，此操作不可撤销。` : `即将编辑“${name}”。`}
          请输入口令 <code>{expected}</code> 以继续。
        </p>
        <input
          autoFocus
          type="text"
          autoComplete="off"
          placeholder={`输入口令：${expected}`}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => { if (event.key === "Enter") onConfirm(input); }}
        />
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className={`btn ${isDelete ? "btn-danger" : "btn-primary"}`} disabled={!input} onClick={() => onConfirm(input)}>
            {isDelete ? "确认删除" : "确认编辑"}
          </button>
        </div>
      </div>
    </div>
  );
}
