import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Edit3, Zap, Cpu, List, Radar, CheckCircle2, AlertTriangle } from "lucide-react";
import { fetchModels, createModel, updateModel, deleteModel, testModel, listAvailableModels, autoDiscoverModels } from "../api";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { ModelForm } from "./ModelForm";
import type { ModelConfig, ModelTestResult, ListModelsResult } from "../types";

export function ModelConfigPage() {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ModelTestResult>>({});
  const [listResults, setListResults] = useState<Record<string, ListModelsResult>>({});
  const [listing, setListing] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoverMsg, setDiscoverMsg] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);
  const [tab, setTab] = useState<"usable" | "pending">("usable");

  const isUsable = (m: ModelConfig) =>
    m.is_active && (typeof m.is_configured === "boolean" ? m.is_configured : Boolean(m.model_name));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setModels(await fetchModels());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: `删除模型 "${id}"？` });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try { await deleteModel(id); setModels((p) => p.filter((m) => m.id !== id)); }
    catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
    setConfirmDelete(null);
  };

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      const result = await testModel(id);
      setTestResults((p) => ({ ...p, [id]: result }));
    } catch (e) {
      setTestResults((p) => ({ ...p, [id]: { success: false, message: String(e), response_preview: null, duration_ms: null } }));
    }
    setTesting(null);
  };

  const handleListModels = async (id: string) => {
    setListing(id);
    try {
      const result = await listAvailableModels(id);
      setListResults((p) => ({ ...p, [id]: result }));
    } catch (e) {
      setListResults((p) => ({ ...p, [id]: { success: false, message: String(e), models: [], provider_type: "", current_model: "" } }));
    }
    setListing(null);
  };

  const handleAutoDiscover = async () => {
    setDiscovering(true);
    setDiscoverMsg(null);
    try {
      const res = await autoDiscoverModels();
      const reachable = res.providers.filter((p) => p.reachable);
      if (reachable.length === 0) {
        setDiscoverMsg("未发现本地可用的模型服务 (Ollama / LM Studio / CC Switch)。");
      } else {
        const parts = reachable.map((p) => `${p.provider} (${p.models.length} 个模型)`);
        setDiscoverMsg(`发现可用服务：${parts.join("、")}。可点击"添加模型"手动配置。`);
      }
    } catch (e) {
      setDiscoverMsg(`自动发现失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setDiscovering(false);
  };

  if (loading) return <div className="loading">加载模型配置...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const providerIcons: Record<string, string> = {
    ollama: "🦙",
    ollama_cloud: "☁️",
    openai: "🤖",
    lmstudio: "💻",
    cc_switch: "🔀",
    custom: "🔧",
  };
  const providerNames: Record<string, string> = {
    ollama: "Ollama",
    ollama_cloud: "Ollama Cloud",
    openai: "OpenAI 兼容",
    lmstudio: "LM Studio",
    cc_switch: "CC Switch",
    custom: "自定义",
  };

  const usableModels = models.filter(isUsable);
  const pendingModels = models.filter((m) => !isUsable(m));
  const shown = tab === "usable" ? usableModels : pendingModels;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>模型配置</h2>
          <p className="text-muted">
            配置 AI 模型用于信息处理、报告自动生成和摘要。支持本地模型和云端 API。
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> 添加模型
        </button>
      </div>

      <div className="toolbar-row">
        <button type="button" className="btn btn-secondary" onClick={handleAutoDiscover} disabled={discovering}>
          <Radar size={14} className={discovering ? "spin" : ""} />
          {discovering ? "发现中..." : "自动发现"}
        </button>
        {discoverMsg && <div className="toast" onClick={() => setDiscoverMsg(null)}>{discoverMsg}</div>}
      </div>

      {models.length > 0 && (
        <div className="toolbar-row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div className="segmented-control">
            <button type="button" className={`seg-btn ${tab === "usable" ? "seg-btn--active" : ""}`} onClick={() => setTab("usable")}>
              可用模型 · {usableModels.length}
            </button>
            <button type="button" className={`seg-btn ${tab === "pending" ? "seg-btn--active" : ""}`} onClick={() => setTab("pending")}>
              未配置 · {pendingModels.length}
            </button>
          </div>
          <span className="text-muted small">共 {models.length} 个 · 可用 {usableModels.length} / 未配置 {pendingModels.length}</span>
        </div>
      )}

      {models.length === 0 && (
        <div className="card-item" style={{ padding: 32, textAlign: "center" }}>
          <Cpu size={32} className="text-muted" style={{ marginBottom: 8 }} />
          <p>尚未配置任何 AI 模型。</p>
          <p className="text-muted small">点击"添加模型"连接本地 Ollama、OpenAI 兼容 API 或云端模型服务。</p>
          <p className="text-muted small">也可以点击"自动发现"扫描本地正在运行的模型服务。</p>
        </div>
      )}

      <div className="card-list">
        {shown.length === 0 ? (
          <div className="card-item" style={{ padding: 24, textAlign: "center" }}>
            <p>{tab === "usable" ? "暂无可用模型。" : "暂无未配置模型。"}</p>
            <p className="text-muted small">
              {tab === "usable" ? "可切换到“未配置”完成配置，或点击“添加模型”。" : "所有模型均已配置完成。"}
            </p>
          </div>
        ) : shown.map((m) => {
          const test = testResults[m.id];
          const usable = tab === "usable";
          return (
            <article key={m.id} className={`card-item ${!usable ? "card-item--muted" : ""}`}>
              <div className="card-item-header">
                <div>
                  <div className="card-item-title">
                    <span style={{ marginRight: 8 }}>{providerIcons[m.provider] || "🔧"}</span>
                    <h4 style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      {m.name}
                      {m.is_default && <span className="chip chip--green">默认</span>}
                    </h4>
                    <span className="text-muted small">
                      {providerNames[m.provider] || m.provider} · {m.model_name || m.id}
                    </span>
                  </div>
                </div>
                <div className="card-item-actions">
                  {usable ? (
                    <span className="badge badge--green">
                      <CheckCircle2 size={11} style={{ verticalAlign: -1, marginRight: 3 }} />可用
                    </span>
                  ) : (
                    <span className="badge" style={{ background: "var(--amber-soft)", color: "var(--amber)" }}>
                      <AlertTriangle size={11} style={{ verticalAlign: -1, marginRight: 3 }} />待配置
                    </span>
                  )}
                  <span className="chip">{m.provider}</span>
                </div>
              </div>

              <div className="card-item-meta">
                <div className="model-params">
                  <span className="param-chip">温度 {m.temperature}</span>
                  <span className="param-chip">最大令牌 {m.max_tokens}</span>
                  <span className="param-chip">Top-P {m.top_p}</span>
                </div>
                <div className="text-muted small">
                  <strong>地址:</strong> {m.base_url || "(默认)"}
                  {m.api_key ? <span> · <strong>API Key:</strong> 已配置</span> : null}
                </div>
                {!usable && (
                  <div className="text-muted small" style={{ color: "var(--amber)" }}>
                    <AlertTriangle size={11} style={{ verticalAlign: -1, marginRight: 3 }} />
                    {!m.is_active ? "模型未启用" : "缺少 API Key 或未完成配置"}，编辑后可移入“可用模型”。
                  </div>
                )}
                {m.description && <div className="text-muted small">{m.description}</div>}

                {test && (
                  <div className={`model-test-result ${test.success ? "test-pass" : "test-fail"}`}>
                    <span>{test.success ? "✅" : "❌"}</span>
                    <span>{test.message}</span>
                    {test.response_preview && <span className="text-muted small"> · 响应: {test.response_preview}</span>}
                    {test.duration_ms != null && <span className="text-muted small"> · {test.duration_ms}ms</span>}
                  </div>
                )}
                {listResults[m.id] && listResults[m.id].models.length > 0 && (
                  <div className="available-models" style={{ marginTop: 8 }}>
                    <strong className="text-muted small" style={{ display: "block", marginBottom: 6 }}>{listResults[m.id].message}</strong>
                    <div className="chip-row" style={{ marginBottom: 0 }}>
                      {listResults[m.id].models.map((mod) => (
                        <button key={mod} type="button" className={`chip ${m.model_name === mod ? "chip--blue" : ""}`}
                          onClick={async () => {
                            try {
                              await updateModel(m.id, { model_name: mod });
                              await load();
                            } catch (e) {
                              alert(e instanceof Error ? e.message : "选择模型失败");
                            }
                          }}
                          title="点击选择此模型">
                          {mod}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="card-item-footer">
                <button type="button" className="btn btn-sm btn-secondary" onClick={() => handleTest(m.id)} disabled={testing === m.id}>
                  <Zap size={12} /> {testing === m.id ? "测试中..." : "测试连接"}
                </button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => handleListModels(m.id)} disabled={listing === m.id}>
                  <List size={12} /> {listing === m.id ? "查询中..." : "查询模型"}
                </button>
                {!m.is_default && (
                  <button type="button" className="btn btn-sm btn-ghost" onClick={async () => {
                    try { await updateModel(m.id, { is_default: true }); await load(); }
                    catch(e) { alert(e instanceof Error ? e.message : "失败"); }
                  }}>
                    <Edit3 size={12} /> 设为默认
                  </button>
                )}
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(m)}>
                  <Edit3 size={12} /> 编辑
                </button>
                <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(m.id)}>
                  <Trash2 size={12} /> 删除
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {(showCreate || editing) && (
        <ModelForm
          model={editing}
          onSave={async (data) => {
            if (editing) { await updateModel(editing.id, data); }
            else { await createModel(data as ModelConfig); }
            setShowCreate(false); setEditing(null); await load();
          }}
          onClose={() => { setShowCreate(false); setEditing(null); }}
        />
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        onConfirm={executeDelete}
        title="删除模型"
        message={confirmDelete?.message || ""}
        variant="danger"
      />
    </div>
  );
}
