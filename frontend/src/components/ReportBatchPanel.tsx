import { useState } from "react";
import { BrainCircuit } from "lucide-react";
import { fetchBatches, generateReport, batchGenerateReports } from "../api";
import type { Report, Topic, ModelConfig } from "../types";

interface Props {
  topics: Topic[];
  models: ModelConfig[];
  ollamaModels: Record<string, string[]>;
  generating: boolean;
  onGeneratingChange: (v: boolean) => void;
  onGenerated: () => void;
  genMsg: string | null;
  onGenMsg: (msg: string | null) => void;
}

/** Multi-topic batch mode. */
type MultiMode = "allItems" | "perBatch";

interface BatchMeta { label: string; run_id: string; }

export function ReportBatchPanel({
  topics, models, ollamaModels, generating,
  onGeneratingChange, onGenerated, genMsg, onGenMsg,
}: Props) {
  const [topicIds, setTopicIds] = useState<string[]>([]);
  const [mode, setMode] = useState<MultiMode>("allItems");
  const [topicBatchMeta, setTopicBatchMeta] = useState<Record<string, Record<string, BatchMeta>>>({});
  const [topicBatchSelections, setTopicBatchSelections] = useState<Record<string, string[]>>({});
  const [batchModel, setBatchModel] = useState("");

  const parseModel = (v: string) => {
    if (!v) return { modelId: undefined, modelNameOverride: undefined };
    const idx = v.indexOf("@@");
    return idx !== -1
      ? { modelId: v.slice(0, idx) as string | undefined, modelNameOverride: v.slice(idx + 2) as string | undefined }
      : { modelId: v as string | undefined, modelNameOverride: undefined };
  };

  const toggleTopic = (id: string) =>
    setTopicIds((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  const ensureMeta = (tid: string) =>
    fetchBatches(tid, 10).then((bs) => {
      const map: Record<string, BatchMeta> = {};
      for (const b of bs) {
        const lid = b.runs?.[0]?.id || "";
        if (lid) map[b.batch_id] = { label: b.batch_label || tid, run_id: lid };
      }
      setTopicBatchMeta((prev) => ({ ...prev, [tid]: map }));
    }).catch(() => { /* ignore */ });

  const toggleBatchSel = (tid: string, bid: string) =>
    setTopicBatchSelections((prev) => {
      const cur = prev[tid] || [];
      return { ...prev, [tid]: cur.includes(bid) ? cur.filter((x) => x !== bid) : [...cur, bid] };
    });

  const runIdsFor = (tid: string) =>
    (topicBatchSelections[tid] || [])
      .map((bid) => topicBatchMeta[tid]?.[bid]?.run_id)
      .filter(Boolean) as string[];

  const handleGenerate = async () => {
    if (!topicIds.length) return;
    onGeneratingChange(true);
    onGenMsg(null);
    try {
      const { modelId, modelNameOverride } = parseModel(batchModel);
      if (mode === "allItems") {
        const results = await Promise.all(topicIds.map((tid) => generateReport(tid, { modelId, modelNameOverride })));
        const ok = results.filter((r: Report) => r.status !== "failed").length;
        onGenMsg(`每个主题全量报告生成完成：成功 ${ok} 份，失败 ${results.length - ok} 份`);
      } else {
        const tasks: Promise<Report>[] = [];
        for (const tid of topicIds) {
          for (const rid of runIdsFor(tid)) {
            tasks.push(generateReport(tid, { modelId, modelNameOverride, collectionRunId: rid }));
          }
        }
        if (!tasks.length) { onGenMsg("按批次生成需至少选择一个批次"); onGeneratingChange(false); return; }
        const results = await Promise.all(tasks);
        const ok = results.filter((r) => r.status !== "failed").length;
        onGenMsg(`按批次独立报告生成完成：成功 ${ok} 份，失败 ${results.length - ok} 份`);
      }
      setTopicIds([]);
      setTopicBatchSelections({});
      onGenerated();
    } catch (e) {
      onGenMsg(`生成失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    onGeneratingChange(false);
  };

  const activeModels = models.filter((m) => m.is_active);

  const s = {
    section: { marginTop: 0 },
    radio: { display: "flex", alignItems: "center", gap: 4, cursor: "pointer" } as React.CSSProperties,
    accent: { accentColor: "var(--accent)" },
    h3: { fontSize: "0.85rem", fontWeight: 600, marginBottom: 12 },
    list: { display: "flex", flexDirection: "column" as const, gap: 8 },
  };

  const needsBatch = mode === "perBatch";
  const canGenerate = topicIds.length > 0 && !generating;

  return (
    <div style={s.section}>
      <h3 style={s.h3}>多主题批量处理</h3>

      {/* mode radios */}
      <div style={{ marginBottom: 12, display: "flex", gap: 16, alignItems: "center", fontSize: "0.82rem", flexWrap: "wrap" }}>
        <span className="text-muted">生成模式：</span>
        {(["allItems", "perBatch"] as const).map((m) => (
          <label key={m} style={s.radio}>
            <input type="radio" name="multiMode" checked={mode === m} onChange={() => setMode(m)} style={s.accent} />
            {m === "allItems" ? "每个主题所有信息生成报告" : "每个主题按信息批次生成独立报告"}
          </label>
        ))}
        <span className="text-muted small">
          {mode === "allItems" ? "每个主题用全量信息各生成一份" : "每个主题按其选中批次各生成一份"}
        </span>
      </div>

      {/* topic list */}
      <div style={s.list}>
        {topics.map((t) => {
          const checked = topicIds.includes(t.id);
          return (
            <div key={t.id}>
              <label style={{ ...s.radio, fontSize: "0.85rem", padding: "4px 0" }}>
                <input type="checkbox" checked={checked} onChange={() => {
                  toggleTopic(t.id);
                  if (needsBatch && !checked) void ensureMeta(t.id);
                }} style={s.accent} />
                <span>{t.name}<span className="text-muted small" style={{ marginLeft: 6 }}>({t.total_items_collected} 条)</span></span>
              </label>
              {needsBatch && checked && topicBatchMeta[t.id] && (
                <div style={{ marginLeft: 24, marginBottom: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {Object.entries(topicBatchMeta[t.id]).map(([bid, meta]) => {
                    const sel = (topicBatchSelections[t.id] || []).includes(bid);
                    return (
                      <label key={bid} style={{
                        display: "flex", alignItems: "center", gap: 3, fontSize: "0.75rem", cursor: "pointer",
                        padding: "2px 6px", borderRadius: 4,
                        background: sel ? "var(--accent-bg)" : "var(--surface)",
                        border: "1px solid var(--line)",
                      }}>
                        <input type="checkbox" checked={sel} onChange={() => toggleBatchSel(t.id, bid)}
                          style={{ accentColor: "var(--accent)", width: 12, height: 12 }} />
                        {meta.label}
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* model + generate */}
      <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
        {activeModels.length > 0 && (
          <div className="gen-field" style={{ minWidth: 200 }}>
            <label className="gen-label">AI 模型</label>
            <select value={batchModel} onChange={(e) => setBatchModel(e.target.value)} style={{ flex: 1 }}>
              <option value="">默认模型</option>
              {activeModels.flatMap((m) => {
                const avail = ollamaModels[m.id];
                if (m.provider === "ollama" && avail?.length) {
                  return avail.map((mn) => <option key={`${m.id}@@${mn}`} value={`${m.id}@@${mn}`}>{m.name} / {mn}</option>);
                }
                return <option key={m.id} value={m.id}>{m.name} ({m.provider}/{m.model_name})</option>;
              })}
            </select>
          </div>
        )}
        <button type="button" className="btn btn-primary" onClick={handleGenerate} disabled={!canGenerate}>
          <BrainCircuit size={14} className={generating ? "spin" : ""} />
          {generating ? "生成中..." : `批量生成 (${topicIds.length})`}
        </button>
      </div>

      {genMsg && <div className="toast" style={{ marginTop: 12 }} onClick={() => onGenMsg(null)}>{genMsg}</div>}
      {!models.length && <div className="text-red small" style={{ marginTop: 8 }}>尚未配置 AI 模型。请先在"模型配置"页面添加一个模型。</div>}
    </div>
  );
}
