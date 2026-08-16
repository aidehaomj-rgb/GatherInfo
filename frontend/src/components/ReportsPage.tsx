import { useEffect, useState, useCallback } from "react";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { FileText, Trash2, Eye, Download, BrainCircuit, Send, Wand2 } from "lucide-react";
import { batchGenerateReports, fetchReports, fetchTopics, fetchModels, fetchSources, generateReport, generateWeeklyReports, deleteReport, fetchBatches, exportReport, downloadReportFile, listAvailableModels, pushReportToHaiSee, reviewItemsInScope } from "../api";
import type { Report, Topic, ModelConfig, Source } from "../types";
import { ReportViewerModal } from "./ReportViewerModal";
import { ReportBatchPanel } from "./ReportBatchPanel";
import { YmgDeepPanel } from "./YmgDeepPanel";
import { formatBeijingDateTime } from "../utils/date";

type GenMode = "single" | "multi" | "weekly";
type SingleSubMode = "merged" | "perBatch";
type ReportType = "analytical" | "archive";

interface BatchOption { batch_id: string; label: string; run_id: string; }

function weeklySourceCoverageSummary(audit: Record<string, unknown>): string {
  const value = audit.source_coverage;
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";
  const coverage = value as Record<string, unknown>;
  const configured = Number(coverage.configured_source_count || 0);
  const ready = Number(coverage.publication_ready_source_count || 0);
  const publishers = Number(coverage.in_period_publisher_count || 0);
  const publisherShortfall = Number(coverage.publisher_shortfall || 0);
  const countries = Array.isArray(coverage.countries) ? coverage.countries.map(String) : [];
  const languages = Array.isArray(coverage.languages) ? coverage.languages.map(String) : [];
  return [
    `正式可出版来源 ${ready}/${configured} 个`,
    `本周独立发布方 ${publishers} 个${publisherShortfall ? `（还缺 ${publisherShortfall} 个）` : ""}`,
    countries.length ? `国家/地区 ${countries.join("、")}` : "",
    languages.length ? `语言 ${languages.join("、")}` : "",
  ].filter(Boolean).join("；");
}

export function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [ollamaModels, setOllamaModels] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mainMode, setMainMode] = useState<"report" | "curate">("report");
  const [genMode, setGenMode] = useState<GenMode>("single");
  const [reportType, setReportType] = useState<ReportType>("analytical");
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Report | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; message: string } | null>(null);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [downloadingKey, setDownloadingKey] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [sendingReportId, setSendingReportId] = useState<string | null>(null);

  // single-topic state
  const [selectedTopic, setSelectedTopic] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [batchOptions, setBatchOptions] = useState<BatchOption[]>([]);
  const [selectedBatchIds, setSelectedBatchIds] = useState<string[]>([]);
  const [singleSubMode, setSingleSubMode] = useState<SingleSubMode>("merged");
  const [weeklyDate, setWeeklyDate] = useState(() => {
    const value = new Date();
    value.setDate(value.getDate() - 7);
    return value.toISOString().slice(0, 10);
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, t, m] = await Promise.all([
        fetchReports(undefined),
        fetchTopics(),
        fetchModels(),
      ]);
      setReports(r.reports);
      setTopics(t);
      setModels(m);
      setError(null);
      setOllamaModels({});
      const ollamaConfigs = m.filter((mdl) => (mdl.provider === "ollama" || mdl.provider === "ollama_cloud") && mdl.is_active);
      if (ollamaConfigs.length > 0) {
        const results: Record<string, string[]> = {};
        await Promise.all(ollamaConfigs.map(async (mdl) => {
          try {
            const res = await listAvailableModels(mdl.id);
            if (res.success && res.models.length > 0) results[mdl.id] = res.models;
          } catch { /* ignore */ }
        }));
        setOllamaModels(results);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const parseModel = (value: string): { modelId?: string; modelNameOverride?: string } => {
    if (!value) return { modelId: undefined, modelNameOverride: undefined };
    const idx = value.indexOf("@@");
    if (idx !== -1) return { modelId: value.slice(0, idx), modelNameOverride: value.slice(idx + 2) };
    return { modelId: value, modelNameOverride: undefined };
  };

  // load batches when single-topic selection changes
  useEffect(() => {
    setSelectedBatchIds([]);
    if (!selectedTopic) { setBatchOptions([]); return; }
    let active = true;
    fetchBatches(selectedTopic, 20)
      .then((bs) => {
        if (!active) return;
        setBatchOptions(bs.map((b): BatchOption => ({
          batch_id: b.batch_id,
          label: b.batch_label || b.topic_name || "采集",
          run_id: b.runs?.[0]?.id || "",
        })));
      })
      .catch(() => { if (active) setBatchOptions([]); });
    return () => { active = false; };
  }, [selectedTopic]);

  const toggleBatch = (id: string) =>
    setSelectedBatchIds((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  const runIdsOf = (ids: string[]) =>
    ids.map((id) => batchOptions.find((b) => b.batch_id === id)?.run_id).filter(Boolean) as string[];

  const handleSingleGenerate = async () => {
    if (!selectedTopic) { setGenMsg("请先选择一个主题"); return; }
    if (singleSubMode === "perBatch" && selectedBatchIds.length === 0) {
      setGenMsg("按批次分别生成需至少选择一个批次"); return;
    }
    setGenerating(true);
    setGenMsg(null);
    try {
      const { modelId, modelNameOverride } = parseModel(selectedModel);
      if (singleSubMode === "merged") {
        const runIds = runIdsOf(selectedBatchIds);
        const report = await generateReport(selectedTopic, {
          reportType, modelId, modelNameOverride,
          collectionRunIds: runIds.length ? runIds : undefined,
        });
        setGenMsg(`报告生成${statusText(report.status)}：${report.title}`);
      } else {
        const runIds = runIdsOf(selectedBatchIds);
        const result = await batchGenerateReports(
          runIds.map(() => selectedTopic),
          modelId,
          runIds,
          modelNameOverride,
          undefined,
          reportType,
        );
        setGenMsg(`按批次分别生成完成：成功 ${result.results.length - result.failed} 份，失败 ${result.failed} 份`);
      }
      await load();
    } catch (e) {
      setGenMsg(`生成失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setGenerating(false);
  };

  const handleWeeklyGenerate = async () => {
    if (!selectedTopic) { setGenMsg("请先选择一个主题"); return; }
    setGenerating(true);
    setGenMsg(null);
    try {
      const { modelId } = parseModel(selectedModel);
      const result = await generateWeeklyReports(selectedTopic, {
        modelId,
        weekStart: weeklyDate,
      });
      const sourceCoverage = weeklySourceCoverageSummary(result.selection_audit);
      setGenMsg(result.documents.length > 0
        ? `${result.period_key} 双卷周刊已生成：${result.documents.map((doc) => `${doc.part_index ?? "?"}/${doc.part_total ?? 2}卷 ${doc.item_count}条`).join("，")}${result.reused ? "（已复用现有文档）" : ""}`
        : `${result.period_key} 暂未发布：${result.warnings.join("；")}${sourceCoverage ? `；${sourceCoverage}` : ""}`);
      await load();
    } catch (e) {
      setGenMsg(`周刊生成失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setGenerating(false);
  };

  const handleDelete = (id: string) => setDeleteTarget({ id, message: "删除此报告？" });

  const executeDelete = async () => {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    try { await deleteReport(id); setReports((p) => p.filter((r) => r.id !== id)); }
    catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
    setDeleteTarget(null);
  };

  const handleExport = async (id: string) => {
    setExportingId(id);
    try {
      const updated = await exportReport(id);
      setReports((p) => p.map((r) => (r.id === id ? updated : r)));
    } catch (e) {
      alert(e instanceof Error ? e.message : "导出失败");
    }
    setExportingId(null);
  };

  const handleDownload = async (reportId: string, format: string) => {
    const key = `${reportId}:${format}`;
    setDownloadingKey(key);
    setDownloadError(null);
    try {
      const { blob, filename } = await downloadReportFile(reportId, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : "下载失败");
    }
    setDownloadingKey(null);
  };

  const handleSendReport = async (report: Report) => {
    setSendingReportId(report.id);
    try {
      const result = await pushReportToHaiSee(report.id);
      setGenMsg(`已拆分为 ${result.task_ids.length} 个 HaiSee 转译分析任务`);
    } catch (e) {
      setGenMsg(`推送失败：${e instanceof Error ? e.message : "未知错误"}`);
    }
    setSendingReportId(null);
  };

  if (loading) return <div className="loading">加载报告列表...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  const defaultModel = models.find((m) => m.is_default);
  const activeModels = models.filter((m) => m.is_active);
  const singleDisabled = generating || !selectedTopic ||
    (singleSubMode === "perBatch" && selectedBatchIds.length === 0);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>智能整理</h2>
          <p className="text-muted">使用 AI 生成综合分析报告，或对设定范围的信息进行全面再整理，清理无效内容。</p>
        </div>
      </div>

      {/* 顶层功能切换：智能报告 / 全面整理 */}
      <div className="segmented-control" style={{ marginBottom: 16 }}>
        <button type="button" className={`seg-btn${mainMode === "report" ? " seg-btn--active" : ""}`} onClick={() => setMainMode("report")}>
          <BrainCircuit size={14} /> 智能报告
        </button>
        <button type="button" className={`seg-btn${mainMode === "curate" ? " seg-btn--active" : ""}`} onClick={() => setMainMode("curate")}>
          <Wand2 size={14} /> 全面整理
        </button>
      </div>

      {mainMode === "curate" ? (
        <CuratePanel topics={topics} models={models} />
      ) : (
      <>
      {/* Mode switch */}
      <div className="segmented-control" style={{ marginBottom: 16 }}>
        <button type="button" className={`seg-btn${genMode === "single" ? " seg-btn--active" : ""}`} onClick={() => setGenMode("single")}>
          单一主题
        </button>
        <button type="button" className={`seg-btn${genMode === "multi" ? " seg-btn--active" : ""}`} onClick={() => setGenMode("multi")}>
          多主题批量
        </button>
        <button type="button" className={`seg-btn${genMode === "weekly" ? " seg-btn--active" : ""}`} onClick={() => setGenMode("weekly")}>
          每周双卷合集
        </button>
      </div>

      <div className="gen-controls" style={{ background: "var(--surface-card)", border: "1px solid var(--line)", borderRadius: "var(--radius)", padding: 20, marginBottom: 16 }}>
        {genMode !== "weekly" && <div style={{ marginBottom: 16 }}>
          <span className="gen-label">报告类型</span>
          <div className="segmented-control" style={{ marginTop: 6 }}>
            <button type="button" className={`seg-btn${reportType === "analytical" ? " seg-btn--active" : ""}`} onClick={() => setReportType("analytical")}>
              总结推理分析型
            </button>
            <button type="button" className={`seg-btn${reportType === "archive" ? " seg-btn--active" : ""}`} onClick={() => setReportType("archive")}>
              逐条信息归档型
            </button>
          </div>
          <p className="text-muted small" style={{ marginTop: 6 }}>
            {reportType === "analytical"
              ? "综合多条证据形成关键发现、趋势研判与行动建议。"
              : "按类别保留每条信息的独立标题、完整正文和原文链接，可批量送至 HaiSee。"}
          </p>
        </div>}
        {genMode === "single" ? (
          <SingleTopicPanel
            topics={topics}
            activeModels={activeModels}
            ollamaModels={ollamaModels}
            defaultModelName={defaultModel?.name}
            selectedTopic={selectedTopic}
            onTopicChange={setSelectedTopic}
            selectedModel={selectedModel}
            onModelChange={setSelectedModel}
            batchOptions={batchOptions}
            selectedBatchIds={selectedBatchIds}
            onToggleBatch={toggleBatch}
            subMode={singleSubMode}
            onSubModeChange={setSingleSubMode}
            generating={generating}
            disabled={singleDisabled}
            onGenerate={handleSingleGenerate}
            reportType={reportType}
          />
        ) : genMode === "multi" ? (
          <ReportBatchPanel
            topics={topics}
            models={models}
            ollamaModels={ollamaModels}
            generating={generating}
            onGeneratingChange={setGenerating}
            onGenerated={load}
            genMsg={genMsg}
            onGenMsg={setGenMsg}
            reportType={reportType}
          />
        ) : (
          <div>
            <h3 style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 12 }}>按北京时间自然周编排</h3>
            <div className="gen-controls-row">
              <div className="gen-field">
                <label className="gen-label" htmlFor="weekly-topic">选择主题</label>
                <select id="weekly-topic" value={selectedTopic} onChange={(event) => setSelectedTopic(event.target.value)}>
                  <option value="">-- 请选择 --</option>
                  {topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
                </select>
              </div>
              <div className="gen-field">
                <label className="gen-label" htmlFor="weekly-date">所属周任意日期</label>
                <input id="weekly-date" type="date" value={weeklyDate} onChange={(event) => setWeeklyDate(event.target.value)} />
              </div>
              <div className="gen-field">
                <label className="gen-label" htmlFor="weekly-model">中文整理模型</label>
                <select id="weekly-model" value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)}>
                  <option value="">{defaultModel?.name ? `默认: ${defaultModel.name}` : "-- 默认模型 --"}</option>
                  {activeModels.map((model) => <option key={model.id} value={model.id}>{model.name} · {model.model_name}</option>)}
                </select>
              </div>
            </div>
            <p className="text-muted small" style={{ marginTop: 8 }}>
              系统按质量、相关性、时效、来源、国家与分类多样性选择最多 80 条，稳定拆成两卷；不足 60 条时只报告缺口，不会凑数发布。
            </p>
            <button type="button" className="btn btn-primary" onClick={() => void handleWeeklyGenerate()} disabled={generating || !selectedTopic} style={{ marginTop: 12 }}>
              <FileText size={14} /> {generating ? "编排中…" : "生成两卷周刊"}
            </button>
          </div>
        )}

        {models.length === 0 && (
          <div className="text-red small" style={{ marginTop: 8 }}>
            尚未配置 AI 模型。请先在"模型配置"页面添加一个模型。
          </div>
        )}
      </div>
      {downloadError && <div className="error-banner" style={{ marginBottom: 16 }}>{downloadError}</div>}

      {/* YMG-Deep panel */}
      <YmgDeepPanel topics={topics} models={models} reports={reports} />

      {/* Report list */}
      <div className="card-list">
        {reports.length === 0 ? (
          <div className="empty">
            <FileText size={24} style={{ opacity: 0.3, margin: "0 auto 8px" }} />
            <p>暂无报告。</p>
            <p className="text-muted small">选择一个主题，点击"立即生成报告"创建第一份智能分析报告。</p>
          </div>
        ) : reports.map((r) => (
          <article key={r.id} className="card-item">
            <div className="card-item-header">
              <div>
                <h4>{r.title}</h4>
                <span className="text-muted small">
                  {topics.find((t) => t.id === r.topic_id)?.name || r.topic_id}
                  {r.model_id && ` · 模型: ${models.find((m) => m.id === r.model_id)?.name || r.model_id}`}
                </span>
                <span className="badge badge--gray" style={{ marginLeft: 8 }}>
                  {r.report_type === "weekly_digest" ? `周刊 ${r.part_index ?? "?"}/${r.part_total ?? 2}` : r.report_type === "archive" ? "逐条归档" : "总结研判"}
                </span>
              </div>
              <div className="card-item-actions">
                <span className={`badge ${
                  r.status === "completed" ? "badge--green" :
                  r.status === "failed" ? "badge--gray" :
                  r.status === "generating" ? "badge--blue" : ""
                }`}>
                  {r.status === "completed" ? "已完成" :
                   r.status === "failed" ? "失败" :
                   r.status === "generating" ? "生成中" : "待处理"}
                </span>
              </div>
            </div>
            <div className="card-item-meta">
              <div className="text-muted small">
                {r.generated_at && <>生成于 {formatBeijingDateTime(r.generated_at)}</>}
                {r.item_count > 0 && <> · 生成时基于 {r.item_count} 条信息</>}
                {r.tokens_used > 0 && <> · 约 {r.tokens_used} tokens</>}
              </div>
              {r.summary && (
                <div className="report-summary-preview" style={{ fontSize: "0.82rem", color: "var(--ink-muted)", lineHeight: 1.5, marginTop: 4 }}>
                  {r.summary.slice(0, 200)}{r.summary.length > 200 ? "..." : ""}
                </div>
              )}
              {r.status === "failed" && r.error_log && (
                <div className="text-red small" style={{ marginTop: 4 }}>错误: {r.error_log}</div>
              )}
            </div>
            <div className="card-item-footer">
              <button type="button" className="btn btn-sm btn-primary" onClick={() => setViewing(r)} disabled={r.status !== "completed"}>
                <Eye size={12} /> 查看报告
              </button>
              {r.status === "completed" && (r.report_type === "archive" || r.report_type === "weekly_digest") && (
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => handleSendReport(r)} disabled={sendingReportId === r.id}>
                  <Send size={12} /> {sendingReportId === r.id ? "发送中…" : "批量送至 HaiSee"}
                </button>
              )}
              {r.status === "completed" && r.output_files && Object.keys(r.output_files).length > 0 ? (
                Object.keys(r.output_files).map((fmt) => (
                  <button key={fmt} type="button" className="btn btn-sm btn-ghost" onClick={() => void handleDownload(r.id, fmt)} disabled={downloadingKey === `${r.id}:${fmt}`}>
                    <Download size={12} /> {downloadingKey === `${r.id}:${fmt}` ? "准备中..." : fmt.toUpperCase()}
                  </button>
                ))
              ) : (
                r.status === "completed" && (
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => handleExport(r.id)} disabled={exportingId === r.id}>
                    <Download size={12} /> {exportingId === r.id ? "导出中…" : "导出文件"}
                  </button>
                )
              )}
              <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(r.id)}>
                <Trash2 size={12} /> 删除
              </button>
            </div>
          </article>
        ))}
      </div>

      {viewing && <ReportViewerModal report={viewing} onClose={() => setViewing(null)} />}

      <ConfirmDialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={executeDelete}
        title="删除报告"
        message={deleteTarget?.message || ""}
        variant="danger"
      />
      </>
      )}
    </div>
  );
}

function statusText(status: string): string {
  if (status === "completed") return "完成";
  if (status === "failed") return "失败";
  return "中";
}

// ── 全面整理面板 ──────────────────────────────────────────────────────
const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: "trade", label: "贸易政策" },
  { value: "tariff", label: "关税税则" },
  { value: "regulation", label: "法规与合规" },
  { value: "technology", label: "技术性贸易措施" },
  { value: "security", label: "出口管制" },
  { value: "enforcement", label: "执法与缉私" },
  { value: "market", label: "市场与商品" },
  { value: "energy", label: "能源" },
  { value: "defense_procurement", label: "军工采购" },
  { value: "general", label: "综合" },
];

const LANGUAGE_OPTIONS: { value: string; label: string }[] = [
  { value: "zh", label: "中文" },
  { value: "en", label: "英文" },
  { value: "ja", label: "日文" },
  { value: "ko", label: "韩文" },
  { value: "fr", label: "法文" },
  { value: "de", label: "德文" },
  { value: "es", label: "西班牙文" },
  { value: "ru", label: "俄文" },
  { value: "ar", label: "阿拉伯文" },
];

interface CurateResult { reviewed: number; curated: number; deleted: number; retained: number; }

function CuratePanel({ topics, models }: { topics: Topic[]; models: ModelConfig[] }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [topicId, setTopicId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [category, setCategory] = useState("");
  const [language, setLanguage] = useState("");
  const [keyword, setKeyword] = useState("");
  const [limit, setLimit] = useState(100);
  const [curating, setCurating] = useState(false);
  const [result, setResult] = useState<CurateResult | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchSources().then((s) => { if (active) setSources(s); }).catch(() => { if (active) setSources([]); });
    return () => { active = false; };
  }, []);

  const scopeSet = Boolean(topicId || sourceId || category || language || keyword.trim());

  const runCurate = async () => {
    setCurating(true);
    setMsg(null);
    setResult(null);
    try {
      const res = await reviewItemsInScope({
        topic_id: topicId || undefined,
        source_id: sourceId || undefined,
        category: category || undefined,
        language: language || undefined,
        q: keyword.trim() || undefined,
        limit,
      });
      setResult(res);
      setMsg(`整理完成：审核 ${res.reviewed} 条，AI 重写整理 ${res.curated} 条，删除无效信息 ${res.deleted} 条，保留 ${res.retained} 条。`);
    } catch (e) {
      setMsg(`整理失败：${e instanceof Error ? e.message : "未知错误"}`);
    }
    setCurating(false);
  };

  return (
    <div className="gen-controls" style={{ background: "var(--surface-card)", border: "1px solid var(--line)", borderRadius: "var(--radius)", padding: 20, marginBottom: 16 }}>
      <h3 style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 4 }}>全面整理采集信息</h3>
      <p className="text-muted small" style={{ marginBottom: 12 }}>
        对设定范围内的已采集信息调用 AI 模型重新整理：清理导航、图片、.gov 横幅等无效内容，重写为简洁的中文标题/摘要/正文，并删除低价值、非文章类页面。可设定主题、来源、分类、语言或关键词范围，留空则按最近采集顺序处理。
      </p>

      <div className="gen-controls-row">
        <div className="gen-field">
          <label className="gen-label" htmlFor="curate-topic">按主题</label>
          <select id="curate-topic" value={topicId} onChange={(e) => setTopicId(e.target.value)}>
            <option value="">全部主题</option>
            {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div className="gen-field">
          <label className="gen-label" htmlFor="curate-source">按来源</label>
          <select id="curate-source" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            <option value="">全部来源</option>
            {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      <div className="gen-controls-row">
        <div className="gen-field">
          <label className="gen-label" htmlFor="curate-category">按分类</label>
          <select id="curate-category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">全部分类</option>
            {CATEGORY_OPTIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>
        <div className="gen-field">
          <label className="gen-label" htmlFor="curate-language">按语言</label>
          <select id="curate-language" value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="">全部语言</option>
            {LANGUAGE_OPTIONS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </div>
      </div>

      <div className="gen-controls-row">
        <div className="gen-field">
          <label className="gen-label" htmlFor="curate-q">关键词搜索</label>
          <input id="curate-q" type="text" placeholder="在标题/摘要/正文中检索" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
        </div>
        <div className="gen-field">
          <label className="gen-label" htmlFor="curate-limit">处理条数上限</label>
          <input id="curate-limit" type="number" min={1} max={500} value={limit} onChange={(e) => setLimit(Number(e.target.value) || 100)} />
        </div>
      </div>

      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" onClick={() => void runCurate()} disabled={curating || models.length === 0}>
          <Wand2 size={14} className={curating ? "spin" : ""} />
          {curating ? "整理中…" : "开始全面整理"}
        </button>
        <span className="text-muted small">
          {scopeSet ? "将仅处理符合以上范围的信息" : "未设定范围，将按最近采集顺序处理最多 " + limit + " 条"}
        </span>
      </div>

      {models.length === 0 && (
        <div className="text-red small" style={{ marginTop: 8 }}>
          尚未配置 AI 模型。请先在"模型配置"页面添加一个模型。
        </div>
      )}

      {msg && (
        <div className={`${result ? "" : "text-red"} small`} style={{ marginTop: 12, padding: 10, background: "var(--surface-elevated)", border: "1px solid var(--line)", borderRadius: 6, fontSize: "0.8rem" }}>
          {msg}
        </div>
      )}

      {result && (
        <div className="curate-result-grid" style={{ marginTop: 12, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 8 }}>
          {[
            { label: "审核", value: result.reviewed },
            { label: "AI 重写整理", value: result.curated },
            { label: "删除无效", value: result.deleted },
            { label: "保留", value: result.retained },
          ].map((r) => (
            <div key={r.label} style={{ background: "var(--surface-elevated)", border: "1px solid var(--line)", borderRadius: 6, padding: "10px 12px", textAlign: "center" }}>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--accent)" }}>{r.value}</div>
              <div style={{ fontSize: "0.72rem", color: "var(--ink-muted)" }}>{r.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface SingleTopicPanelProps {
  topics: Topic[];
  activeModels: ModelConfig[];
  ollamaModels: Record<string, string[]>;
  defaultModelName?: string;
  selectedTopic: string;
  onTopicChange: (v: string) => void;
  selectedModel: string;
  onModelChange: (v: string) => void;
  batchOptions: BatchOption[];
  selectedBatchIds: string[];
  onToggleBatch: (id: string) => void;
  subMode: SingleSubMode;
  onSubModeChange: (m: SingleSubMode) => void;
  generating: boolean;
  disabled: boolean;
  onGenerate: () => void;
  reportType: ReportType;
}

function SingleTopicPanel(props: SingleTopicPanelProps) {
  const {
    topics, activeModels, ollamaModels, defaultModelName,
    selectedTopic, onTopicChange, selectedModel, onModelChange,
    batchOptions, selectedBatchIds, onToggleBatch, subMode, onSubModeChange,
    generating, disabled, onGenerate, reportType,
  } = props;

  const allBatchSelected = batchOptions.length > 0 && selectedBatchIds.length === batchOptions.length;
  const onToggleAll = () => {
    if (allBatchSelected) selectedBatchIds.forEach(onToggleBatch);
    else batchOptions.forEach((b) => { if (!selectedBatchIds.includes(b.batch_id)) onToggleBatch(b.batch_id); });
  };

  return (
    <>
      <h3 style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 12 }}>单一主题生成报告</h3>
      <div className="gen-controls-row">
        <div className="gen-field">
          <label className="gen-label">选择主题</label>
          <select value={selectedTopic} onChange={(e) => onTopicChange(e.target.value)} style={{ flex: 1 }}>
            <option value="">-- 请选择 --</option>
            {topics.map((t) => (
              <option key={t.id} value={t.id}>{t.name} ({t.current_item_count} 条)</option>
            ))}
          </select>
        </div>
        <div className="gen-field">
          <label className="gen-label">AI 模型</label>
          <select value={selectedModel} onChange={(e) => onModelChange(e.target.value)} style={{ flex: 1 }}>
            <option value="">{defaultModelName ? `默认: ${defaultModelName}` : "-- 默认模型 --"}</option>
            {activeModels.flatMap((m) => {
              const avail = ollamaModels[m.id];
              if ((m.provider === "ollama" || m.provider === "ollama_cloud") && avail && avail.length > 0) {
                return avail.map((modelName) => (
                  <option key={`${m.id}@@${modelName}`} value={`${m.id}@@${modelName}`}>
                    {m.name} / {modelName}{m.is_default ? " ⭐" : ""}
                  </option>
                ));
              }
              return (
                <option key={m.id} value={m.id}>{m.name} ({m.provider}/{m.model_name}){m.is_default ? " ⭐" : ""}</option>
              );
            })}
          </select>
          {reportType === "archive" && (
            <span className="text-muted small">归档型报告不做综合改写，模型仅用于必要的中文转译。</span>
          )}
        </div>
      </div>

      {/* batch multi-select */}
      <div style={{ marginTop: 12 }}>
        <div className="gen-field">
          <label className="gen-label">
            采集批次（可多选{allBatchSelected ? " · 已全选" : ""}）
          </label>
          {!selectedTopic ? (
            <div className="text-muted small">请先选择主题以加载批次。</div>
          ) : batchOptions.length === 0 ? (
            <div className="text-muted small">该主题暂无采集批次，将使用全部信息生成。</div>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
              <button type="button" className="btn btn-sm btn-ghost" onClick={onToggleAll} disabled={!selectedTopic}>
                {allBatchSelected ? "取消全选" : "全选"}
              </button>
              {batchOptions.map((b) => {
                const sel = selectedBatchIds.includes(b.batch_id);
                return (
                  <label key={b.batch_id} style={{
                    display: "flex", alignItems: "center", gap: 4, fontSize: "0.78rem", cursor: "pointer",
                    padding: "3px 8px", borderRadius: 4,
                    background: sel ? "var(--accent-bg)" : "var(--surface)",
                    border: "1px solid var(--line)",
                  }}>
                    <input type="checkbox" checked={sel} onChange={() => onToggleBatch(b.batch_id)}
                      style={{ accentColor: "var(--accent)", width: 13, height: 13 }} />
                    {b.label}
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* generation method */}
      <div style={{ marginTop: 12, display: "flex", gap: 16, alignItems: "center", fontSize: "0.82rem", flexWrap: "wrap" }}>
        <span className="text-muted">生成方式：</span>
        {(["merged", "perBatch"] as const).map((m) => (
          <label key={m} style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
            <input type="radio" name="singleSubMode" checked={subMode === m}
              onChange={() => onSubModeChange(m)} style={{ accentColor: "var(--accent)" }} />
            {m === "merged" ? "合并为一份报告" : "按批次分别生成"}
          </label>
        ))}
        <span className="text-muted small">
          {subMode === "merged"
            ? "合并所有选中批次信息，生成一份报告（不选批次则用全量信息）"
            : "每个选中批次各生成一份报告"}
        </span>
      </div>

      <div style={{ marginTop: 12 }}>
        <button type="button" className="btn btn-primary" onClick={onGenerate} disabled={disabled}>
          <BrainCircuit size={14} className={generating ? "spin" : ""} />
          {generating ? "生成中..." : "立即生成报告"}
        </button>
      </div>
    </>
  );
}
