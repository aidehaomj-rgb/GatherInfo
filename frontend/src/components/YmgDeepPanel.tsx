import { useEffect, useState } from "react";
import { Rocket, ExternalLink, CheckCircle, AlertTriangle, Loader2, FileSearch, Archive } from "lucide-react";
import type { Topic, ModelConfig, Report, MaterialSet, YmgAnalyzeResponse, YmgHealthResponse } from "../types";
import { archiveMaterialSet, fetchMaterialSets, ymgHealth, ymgAnalyze } from "../api";

interface Props {
  topics: Topic[];
  models: ModelConfig[];
  reports: Report[];
}

/**
 * YMG-Deep integration panel.
 * User selects an item set (topic + optional batches via collection_run_ids, or
 * leave batches empty to use all items), then the system generates a <=200 char
 * analysis topic from the local knowledge base and forwards it + the evidence
 * digest to the YMG-Deep backend to start a deep research session.
 */
export function YmgDeepPanel({ topics, models, reports }: Props) {
  const [health, setHealth] = useState<YmgHealthResponse | null>(null);
  const [topicId, setTopicId] = useState("");
  const [materialSetId, setMaterialSetId] = useState("");
  const [materialSets, setMaterialSets] = useState<MaterialSet[]>([]);
  const [reportId, setReportId] = useState("");
  const [modelId, setModelId] = useState("");
  const [depth, setDepth] = useState<"standard" | "deep">("standard");
  const [mode, setMode] = useState<"swarm" | "solo">("swarm");
  const [extra, setExtra] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<YmgAnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    ymgHealth()
      .then((h) => { if (active) setHealth(h); })
      .catch(() => { if (active) setHealth({ reachable: false, base_url: "", message: "无法检查 YMG-Deep 状态" }); });
    return () => { active = false; };
  }, []);

  const loadMaterialSets = () =>
    fetchMaterialSets().then(setMaterialSets).catch(() => setMaterialSets([]));

  useEffect(() => { void loadMaterialSets(); }, []);

  const usableModels = models.filter((m) => m.is_active && (typeof m.is_configured === "boolean" ? m.is_configured : Boolean(m.model_name)));

  const handleAnalyze = async () => {
    if (!topicId && !materialSetId) { setError("请选择主题或复用一个素材集"); return; }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await ymgAnalyze({
        topic_id: topicId || undefined,
        material_set_id: materialSetId || undefined,
        report_id: reportId || undefined,
        model_id: modelId || undefined,
        ymg_depth: depth,
        ymg_mode: mode,
        extra_requirements: extra || undefined,
      });
      setResult(res);
      setMaterialSetId(res.material_set_id);
      void loadMaterialSets();
    } catch (e) {
      setError(e instanceof Error ? e.message : "分析失败");
    }
    setLoading(false);
  };

  const statusIcon = health?.reachable
    ? <CheckCircle size={14} style={{ color: "var(--green)" }} />
    : <AlertTriangle size={14} style={{ color: "var(--orange)" }} />;
  const selectedMaterialSet = materialSets.find((item) => item.id === materialSetId);
  const effectiveTopicId = topicId || selectedMaterialSet?.topic_id || "";
  const availableReports = reports.filter(
    (report) => report.status === "completed" && (!effectiveTopicId || report.topic_id === effectiveTopicId),
  );

  const handleArchive = async () => {
    if (!materialSetId) return;
    await archiveMaterialSet(materialSetId);
    setMaterialSetId("");
    await loadMaterialSets();
  };

  return (
    <div className="panel" style={{ marginTop: 16, padding: 16, border: "1px solid var(--line)", borderRadius: "var(--radius)", background: "var(--surface-card)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <Rocket size={16} style={{ color: "var(--accent)" }} />
        <h3 style={{ fontSize: "0.9rem", fontWeight: 600, margin: 0 }}>YMG-Deep 深度分析</h3>
        <span className="text-muted small" style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {statusIcon} {health?.reachable ? "YMG-Deep 在线" : "YMG-Deep 离线"}
        </span>
      </div>

      <p className="text-muted small" style={{ marginBottom: 12 }}>
        每次发送都会保存为可复用素材集；相同条目不会重复建集，每次深度分析会单独保留交接记录。
      </p>

      <div className="form-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <label className="form-group" style={{ gridColumn: "1 / -1", display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>复用素材集（可选）</span>
          <div style={{ display: "flex", gap: 8 }}>
            <select
              value={materialSetId}
              onChange={(e) => {
                setMaterialSetId(e.target.value);
                const selected = materialSets.find((item) => item.id === e.target.value);
                if (selected?.topic_id) setTopicId(selected.topic_id);
              }}
              style={{ flex: 1, padding: "8px 10px", borderRadius: "var(--radius)", border: "1px solid var(--line)", background: "var(--surface-elevated)", color: "var(--ink)" }}
            >
              <option value="">新建：按下方主题范围生成素材集</option>
              {materialSets.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.item_count} 条 · 已分析 {item.handoff_runs.length} 次
                </option>
              ))}
            </select>
            <button type="button" className="btn btn-ghost" title="归档所选素材集" onClick={handleArchive} disabled={!materialSetId}>
              <Archive size={14} />
            </button>
          </div>
        </label>
        <label className="form-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>主题</span>
          <select value={topicId} onChange={(e) => setTopicId(e.target.value)} style={{ padding: "8px 10px", borderRadius: "var(--radius)", border: "1px solid var(--line)", background: "var(--surface-elevated)", color: "var(--ink)" }}>
            <option value="">选择主题…</option>
            {topics.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.total_items_collected}条)</option>)}
          </select>
        </label>
        <label className="form-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>阶段性报告素材（可选）</span>
          <select value={reportId} onChange={(e) => setReportId(e.target.value)} style={{ padding: "8px 10px", borderRadius: "var(--radius)", border: "1px solid var(--line)", background: "var(--surface-elevated)", color: "var(--ink)" }}>
            <option value="">不附加报告</option>
            {availableReports.map((report) => (
              <option key={report.id} value={report.id}>{report.title}</option>
            ))}
          </select>
        </label>
        <label className="form-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>分析主题生成模型</span>
          <select value={modelId} onChange={(e) => setModelId(e.target.value)} style={{ padding: "8px 10px", borderRadius: "var(--radius)", border: "1px solid var(--line)", background: "var(--surface-elevated)", color: "var(--ink)" }}>
            <option value="">默认模型</option>
            {usableModels.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.provider})</option>)}
          </select>
        </label>
        <label className="form-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>分析深度</span>
          <div className="segmented-control" style={{ display: "flex" }}>
            {(["standard", "deep"] as const).map((d) => (
              <button key={d} type="button" className={`seg-btn ${depth === d ? "seg-btn--active" : ""}`} onClick={() => setDepth(d)}>
                {d === "standard" ? "标准" : "深度"}
              </button>
            ))}
          </div>
        </label>
        <label className="form-group" style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>执行模式</span>
          <div className="segmented-control" style={{ display: "flex" }}>
            {(["swarm", "solo"] as const).map((md) => (
              <button key={md} type="button" className={`seg-btn ${mode === md ? "seg-btn--active" : ""}`} onClick={() => setMode(md)}>
                {md === "swarm" ? "组团并行" : "独立单干"}
              </button>
            ))}
          </div>
        </label>
        <label className="form-group span-2" style={{ gridColumn: "1 / -1", display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 600 }}>附加要求（可选）</span>
          <input value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="补充分析要求…" style={{ padding: "8px 10px", borderRadius: "var(--radius)", border: "1px solid var(--line)", background: "var(--surface-elevated)", color: "var(--ink)" }} />
        </label>
      </div>

      <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
        <button type="button" className="btn btn-primary" onClick={handleAnalyze} disabled={loading || (!topicId && !materialSetId)}>
          {loading ? <Loader2 size={14} className="spin" /> : <FileSearch size={14} />}
          {loading ? "分析中…" : "生成分析主题并发送到 YMG-Deep"}
        </button>
        {!health?.reachable && (
          <span className="text-muted small">⚠ YMG-Deep 未启动时仍可生成分析主题，但无法自动启动深度分析</span>
        )}
      </div>

      {error && <div className="error-banner" style={{ marginTop: 12 }}>{error}</div>}

      {result && (
        <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--line-light)" }}>
          <div style={{ marginBottom: 8 }}>
            <strong style={{ fontSize: "0.82rem" }}>分析主题：</strong>
            <p style={{ background: "var(--surface-elevated)", padding: 12, borderRadius: "var(--radius)", marginTop: 6, lineHeight: 1.6, fontSize: "0.85rem" }}>
              {result.analysis_topic}
            </p>
          </div>
          <div className="text-muted small" style={{ marginBottom: 8 }}>
            基于素材集 {result.material_set_id}，共 {result.evidence_count} 条采集信息
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span className={`badge ${result.ymg_status === "started" ? "badge--green" : result.ymg_status === "unreachable" ? "badge--yellow" : "badge--gray"}`}>
              {result.ymg_status === "started" ? "YMG-Deep 已启动" : result.ymg_status === "unreachable" ? "YMG-Deep 离线" : result.ymg_status}
            </span>
            {result.ymg_session_id && (
              <>
                <span className="text-muted small">会话: {result.ymg_session_id}</span>
                <a href={`${result.ymg_base_url.replace(/\/$/, "")}/?session=${result.ymg_session_id}`} target="_blank" rel="noreferrer" className="btn btn-sm btn-ghost">
                  <ExternalLink size={12} /> 打开 YMG-Deep
                </a>
              </>
            )}
          </div>
          {result.ymg_message && <div className="text-muted small" style={{ marginTop: 6 }}>{result.ymg_message}</div>}
          <details style={{ marginTop: 12 }}>
            <summary className="text-muted small" style={{ cursor: "pointer" }}>信息集摘要（{result.evidence_items.length} 条预览）</summary>
            <div style={{ maxHeight: 240, overflow: "auto", marginTop: 8 }}>
              {result.evidence_items.map((it) => (
                <div key={it.id} style={{ padding: "6px 0", borderBottom: "1px solid var(--line-light)", fontSize: "0.78rem" }}>
                  <strong>{it.title}</strong>
                  {it.summary && <div className="text-muted" style={{ marginTop: 2 }}>{it.summary.slice(0, 150)}</div>}
                </div>
              ))}
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
