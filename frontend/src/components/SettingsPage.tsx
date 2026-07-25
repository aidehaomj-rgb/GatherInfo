import { useState, useRef, useEffect, useCallback } from "react";
import { Download, Upload, AlertTriangle, CheckCircle, X, Save, FolderOpen, Folder, Check } from "lucide-react";
import { exportConfig, importConfig, fetchSettings, updateSettings } from "../api";
import type { SystemConfig } from "../types";
import { Modal } from "./shared/Modal";

const ALL_FORMATS = ["docx", "pdf"];

const DIR_PRESETS = [
  { label: "默认 (data/reports)", value: "data/reports", hint: "项目内置报告目录" },
  { label: "桌面", value: "~/Desktop", hint: "用户桌面文件夹" },
  { label: "文档", value: "~/Documents", hint: "用户文档文件夹" },
  { label: "下载", value: "~/Downloads", hint: "用户下载文件夹" },
];

const DEFAULT_DIR = "data/reports";

export function SettingsPage() {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [resultMsg, setResultMsg] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [importMode, setImportMode] = useState("skip");
  const [showConflictDetail, setShowConflictDetail] = useState<any | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);



  const [dirPickerOpen, setDirPickerOpen] = useState(false);
  const [dirCustom, setDirCustom] = useState("");
  const [dirSelected, setDirSelected] = useState<string | null>(null);

  // Report settings
  const [settings, setSettings] = useState<SystemConfig | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    try {
      const s = await fetchSettings();
      setSettings(s);
    } catch {
      /* ignore */
    }
  }, []);
  useEffect(() => { void loadSettings(); }, [loadSettings]);



  const openDirPicker = () => {
    setDirCustom(settings?.report_output_dir ?? "");
    setDirSelected(settings?.report_output_dir ?? DEFAULT_DIR);
    setDirPickerOpen(true);
  };

  const confirmDirPicker = () => {
    const value = (dirSelected ?? dirCustom.trim()) || null;
    setSettings((p) => (p ? { ...p, report_output_dir: value } : p));
    setDirPickerOpen(false);
  };

  const toggleFormat = (fmt: string) => {
    setSettings((prev) => {
      if (!prev) return prev;
      const has = prev.report_formats.includes(fmt);
      const next = has ? prev.report_formats.filter((f) => f !== fmt) : [...prev.report_formats, fmt];
      return { ...prev, report_formats: next };
    });
  };

  const handleSaveSettings = async () => {
    if (!settings) return;
    setSavingSettings(true);
    setSettingsMsg(null);
    try {
      const saved = await updateSettings(settings);
      setSettings(saved);
      setSettingsMsg("报告设置已保存");
    } catch (e) {
      setSettingsMsg(`保存失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setSavingSettings(false);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const config = await exportConfig();
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `gatherinfo-config-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setResultMsg(`Configuration exported: ${Object.values(config).reduce((s: number, v: any) => s + (Array.isArray(v) ? v.length : 0), 0)} items`);
    } catch (e) {
      setResultMsg(`Export failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    }
    setExporting(false);
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      data.mode = importMode;
      const result = await importConfig(data);
      const total = Object.values(result.imported).reduce((s: number, v: any) => s + (v as number), 0);
      setResultMsg(`Imported: ${total} items. Conflicts: ${result.conflict_count}`);
      setConflicts(result.conflicts || []);
    } catch (e) {
      setResultMsg(`Import failed: ${e instanceof Error ? e.message : "Invalid JSON"}`);
    }
    setImporting(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>系统配置</h2>
          <p className="text-muted">导出当前配置备份，或从备份文件导入配置。</p>
        </div>
      </div>

      {resultMsg && (
        <div className="toast" onClick={() => setResultMsg(null)} style={{ marginBottom: 16 }}>
          {resultMsg}
        </div>
      )}

<div className="toolbar-row" style={{ marginBottom: 16, padding: "10px 14px", background: "var(--surface-card)", border: "1px solid var(--line)", borderRadius: "var(--radius)" }}>
        <input ref={fileRef} type="file" accept=".json" onChange={handleImport} style={{ display: "none" }} />
        <button type="button" className="btn btn-primary" onClick={handleExport} disabled={exporting}>
          <Download size={14} /> {exporting ? "导出中..." : "导出配置"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => fileRef.current?.click()} disabled={importing}>
          <Upload size={14} /> {importing ? "导入中..." : "导入配置"}
        </button>
        <label className="text-muted small" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          冲突:
          <select value={importMode} onChange={(e) => setImportMode(e.target.value)} style={{ background: "var(--surface-elevated)", border: "1px solid var(--line)", borderRadius: "var(--radius)", padding: "4px 8px", fontSize: "0.8rem" }}>
            <option value="skip">跳过</option>
            <option value="overwrite">覆盖</option>
            <option value="append">追加</option>
          </select>
        </label>
      </div>

      {/* Report settings */}
      {settings && (
        <div className="panel" style={{ marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: 2 }}>报告设置</h3>
              <p style={{ fontSize: "0.78rem", color: "var(--ink-muted)" }}>
                配置生成报告的标题格式、输出目录与导出格式。标题可用 {"{topic}"} 与 {"{date}"} 占位符。
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <button type="button" className="btn btn-primary" onClick={handleSaveSettings} disabled={savingSettings} style={{ whiteSpace: "nowrap" }}>
                <Save size={13} /> {savingSettings ? "保存中..." : "保存设置"}
              </button>
              {settingsMsg && <span style={{ fontSize: "0.78rem", color: "var(--ink)" }}>{settingsMsg}</span>}
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--ink)" }}>标题格式</label>
              <input type="text" value={settings.report_title_format}
                onChange={(e) => setSettings((p) => (p ? { ...p, report_title_format: e.target.value } : p))}
                style={{ padding: "9px 11px", borderRadius: "var(--radius)", border: "1px solid var(--line)", background: "var(--surface-elevated)", color: "var(--ink)", fontSize: "0.85rem", outline: "none" }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--ink)" }}>输出目录</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input type="text" value={settings.report_output_dir ?? ""} placeholder="data/reports" readOnly
                  style={{ flex: 1, padding: "9px 11px", borderRadius: "var(--radius)", border: "1px solid var(--line)", background: "var(--surface-elevated)", color: "var(--ink)", fontSize: "0.85rem", outline: "none" }} />
                <button type="button" className="btn btn-secondary" onClick={openDirPicker} style={{ whiteSpace: "nowrap" }}>
                  <FolderOpen size={14} /> 选择目录
                </button>
              </div>
              <span style={{ fontSize: "0.72rem", color: "var(--ink-muted)" }}>点击「选择目录」浏览预设路径，留空使用默认 data/reports</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--ink)" }}>目录日期模式</label>
              <input type="text" value={settings.report_dir_pattern} placeholder="%Y-%m-%d"
                onChange={(e) => setSettings((p) => (p ? { ...p, report_dir_pattern: e.target.value } : p))}
                style={{ padding: "9px 11px", borderRadius: "var(--radius)", border: "1px solid var(--line)", background: "var(--surface-elevated)", color: "var(--ink)", fontSize: "0.85rem", outline: "none" }} />
              <span style={{ fontSize: "0.72rem", color: "var(--ink-muted)" }}>strftime 格式，如 %Y-%m-%d</span>
            </div>
            <div>
              <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--ink)", display: "block", marginBottom: 6 }}>导出格式</label>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {ALL_FORMATS.map((fmt) => (
                  <label key={fmt} style={{ display: "flex", alignItems: "center", gap: 5, cursor: "pointer", fontSize: "0.83rem", color: "var(--ink)", padding: "5px 10px", borderRadius: "var(--radius)", border: "1px solid " + (settings.report_formats.includes(fmt) ? "var(--accent)" : "var(--line)"), background: settings.report_formats.includes(fmt) ? "var(--accent-soft)" : "transparent", transition: "all 0.12s" }}>
                    <input type="checkbox" checked={settings.report_formats.includes(fmt)} onChange={() => toggleFormat(fmt)}
                      style={{ accentColor: "var(--accent)", width: 14, height: 14 }} />
                    {fmt.toUpperCase()}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Conflicts */}
      {conflicts.length > 0 && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>冲突项目 ({conflicts.length})</h3>
          <div className="tag-stats-table">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>名称</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {conflicts.slice(0, 20).map((c) => (
                  <tr key={c.id}>
                    <td><code>{c.id}</code></td>
                    <td>{c.name}</td>
                    <td>{c.identical ? <span className="chip chip--green">完全相同</span> : <span className="chip chip--blue">不同</span>}</td>
                    <td>
                      <button type="button" className="btn btn-sm btn-ghost" onClick={() => setShowConflictDetail(c)}>
                        <AlertTriangle size={12} /> 查看差异
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Conflict detail modal */}
      {showConflictDetail && (
        <div className="modal-overlay" onClick={() => setShowConflictDetail(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 600 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3>冲突详情: {showConflictDetail.name}</h3>
              <button type="button" className="btn-icon" onClick={() => setShowConflictDetail(null)}>
                <X size={16} />
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, fontSize: "0.82rem" }}>
              <div>
                <strong className="text-muted">现有配置</strong>
                <pre style={{ background: "var(--surface-elevated)", padding: 12, borderRadius: "var(--radius)", marginTop: 4, fontSize: "0.75rem", maxHeight: 300, overflow: "auto" }}>
                  {JSON.stringify(showConflictDetail.existing || {}, null, 2)}
                </pre>
              </div>
              <div>
                <strong className="text-muted">导入配置</strong>
                <pre style={{ background: "var(--surface-elevated)", padding: 12, borderRadius: "var(--radius)", marginTop: 4, fontSize: "0.75rem", maxHeight: 300, overflow: "auto" }}>
                  {JSON.stringify(showConflictDetail.incoming, null, 2)}
                </pre>
              </div>
            </div>
            <div style={{ marginTop: 16, textAlign: "center" }}>
              <span className={`chip ${showConflictDetail.identical ? "chip--green" : "chip--blue"}`}>
                {showConflictDetail.identical ? "完全相同" : "配置不同"}
              </span>
            </div>
          </div>
        </div>
      )}

      <Modal open={dirPickerOpen} title="选择输出目录" onClose={() => setDirPickerOpen(false)} width={480}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--ink)", display: "block", marginBottom: 8 }}>常用目录预设</label>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {DIR_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  className="dir-preset-row"
                  style={{
                    display: "flex", alignItems: "center", gap: 10, width: "100%",
                    padding: "10px 12px", borderRadius: "var(--radius)",
                    border: "1px solid " + (dirSelected === preset.value ? "var(--accent)" : "var(--line)"),
                    background: dirSelected === preset.value ? "var(--accent-soft)" : "var(--surface-elevated)",
                    cursor: "pointer", textAlign: "left", transition: "all 0.15s ease-out",
                  }}
                  onClick={() => { setDirSelected(preset.value); setDirCustom(preset.value); }}
                >
                  <Folder size={16} style={{ color: "var(--accent)", flexShrink: 0 }} />
                  <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--ink)" }}>{preset.label}</span>
                    <span style={{ fontSize: "0.72rem", color: "var(--ink-muted)" }}>{preset.hint}</span>
                  </span>
                  {dirSelected === preset.value && <Check size={16} style={{ color: "var(--accent)" }} />}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--ink)", display: "block", marginBottom: 6 }}>自定义路径</label>
            <input
              type="text"
              className="input"
              placeholder="粘贴或输入绝对/相对路径"
              value={dirCustom}
              onChange={(e) => { setDirCustom(e.target.value); setDirSelected(e.target.value || null); }}
              style={{ width: "100%" }}
            />
            <span style={{ fontSize: "0.72rem", color: "var(--ink-muted)" }}>支持 ~ 开头的家目录路径，如 ~/Desktop/reports</span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
            <button type="button" className="btn btn-ghost" onClick={() => { setDirSelected(null); setDirCustom(""); }}>
              使用当前默认
            </button>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn btn-ghost" onClick={() => setDirPickerOpen(false)}>取消</button>
              <button type="button" className="btn btn-primary" onClick={confirmDirPicker}>
                <Check size={14} /> 确定
              </button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
