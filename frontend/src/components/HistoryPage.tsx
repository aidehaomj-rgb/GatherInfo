import { useEffect, useState, useCallback } from "react";
import { Clock, RefreshCw, ChevronDown, ChevronRight, CheckCircle, AlertTriangle, Trash2, FileText, Square, ExternalLink } from "lucide-react";
import { fetchActiveRuns, fetchBatches, fetchReports, operatorWriteHeaders, stopRun, stopAllRuns } from "../api";
import type { ActiveRunOut, BatchOut, BatchRunOut, Report } from "../types";
import { EmptyState } from "./shared/EmptyState";
import { StatusBadge } from "./shared/StatusBadge";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { CollectionBatchProgress } from "./CollectionBatchProgress";
import { formatBeijingDateTime, formatBeijingTime } from "../utils/date";

type ViewMode = "cards" | "timeline";
type TaskCategory = "all" | "collection" | "report";

function formatReportTime(report: Report): string {
  const timestamp = report.generated_at ?? report.created_at;
  return timestamp ? formatBeijingDateTime(timestamp) : "未记录时间";
}

const LANG_LABELS: Record<string, string> = {
  zh: "中文", en: "英文", ja: "日文", ko: "韩文", fr: "法文",
  de: "德文", es: "西班牙文", ru: "俄文", ar: "阿拉伯文",
};
function langLabel(code: string): string {
  return LANG_LABELS[code] || code;
}

// 单个信息源 run 的完整结论：信息源结论 + 符合标准 = 新增 + 重复（自洽计数）
function SourceRunDetail({ run }: { run: BatchRunOut }) {
  const [showDuplicates, setShowDuplicates] = useState(false);
  const verdict = run.source_verdict;
  const duplicates = run.duplicate_items || [];
  const newCount = run.items_new || 0;
  // 重复数以 duplicate_items 实际条数为准（无明细时回退到 run.items_duplicate）
  const dupCount = duplicates.length || run.items_duplicate || 0;
  const matchedTotal = newCount + dupCount;

  return (
    <div className="source-run-detail">
      {/* 信息源结论：可连接 / 可爬取 / 可下载 / 语言 */}
      {verdict && (
        <div className="source-verdict">
          <span className={`verdict-pill ${verdict.connectable ? "verdict-ok" : "verdict-bad"}`}>
            {verdict.connectable ? "可连接" : "不可连接"}
          </span>
          <span className={`verdict-pill ${verdict.crawlable ? "verdict-ok" : "verdict-bad"}`}>
            {verdict.crawlable ? "可爬取" : "未爬取到内容"}
          </span>
          <span className={`verdict-pill ${verdict.downloadable ? "verdict-ok" : "verdict-bad"}`}>
            {verdict.downloadable ? "可下载" : "未获取到正文"}
          </span>
          {verdict.languages && verdict.languages.length > 0 && (
            <span className="verdict-pill verdict-lang">
              语言：{verdict.languages.map(langLabel).join("、")}
            </span>
          )}
        </div>
      )}

      {/* 符合标准 = 新增 + 重复（自洽） */}
      <div className="source-run-counts">
        {run.status === "completed" ? <CheckCircle size={12} style={{ color: "var(--green)" }} /> :
         run.status === "failed" ? <AlertTriangle size={12} style={{ color: "var(--red)" }} /> : null}
        <span className="count-total">符合标准 <b>{matchedTotal}</b> 条</span>
        <span className="count-eq">=</span>
        <span className="count-new">新增 {newCount}</span>
        <span className="count-plus">+</span>
        {dupCount > 0 ? (
          <button
            type="button"
            className="duplicate-count-link"
            title="点击展开重复信息（在新窗口打开原文）"
            onClick={() => setShowDuplicates((v) => !v)}
          >
            重复 {dupCount}
            <ChevronDown size={12} style={{ transform: showDuplicates ? "rotate(0deg)" : "rotate(-90deg)", transition: "transform 0.2s" }} />
          </button>
        ) : (
          <span className="count-dup">重复 0</span>
        )}
        {run.duration_ms != null && <span className="count-dur">{(run.duration_ms / 1000).toFixed(1)}秒</span>}
      </div>

      {/* 重复信息列表：点击标题在新窗口打开原文 */}
      {showDuplicates && dupCount > 0 && (
        <div className="duplicates-block">
          <ul className="duplicates-list">
            {duplicates.map((d, i) => (
              <li key={i}>
                {d.url ? (
                  <a href={d.url} target="_blank" rel="noopener noreferrer">
                    {d.title || "未命名信息"} <ExternalLink size={11} />
                  </a>
                ) : (
                  <span>{d.title || "未命名信息"}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function TimelineNode({ batch, expanded, onToggle }: { batch: BatchOut; expanded: boolean; onToggle: () => void }) {
  const dotClass = batch.status === "completed" ? "timeline-dot--completed"
    : batch.status === "failed" ? "timeline-dot--failed"
    : batch.status === "running" ? "timeline-dot--running"
    : "timeline-dot--partial";

  return (
    <div className="timeline-node">
      <div className={`timeline-dot ${dotClass}`} />
      <div className="timeline-card" onClick={onToggle}>
        <div className="timeline-card-header">
          <div>
            <h4 style={{ display: "flex", alignItems: "center", gap: 6, margin: 0, fontSize: "0.9rem" }}>
              {batch.batch_label || batch.topic_name || "多源采集"}
              <StatusBadge status={batch.status as any} />
            </h4>
            <div style={{ fontSize: "0.78rem", color: "var(--ink-muted)", marginTop: 4 }}>
              {batch.started_at && <>{formatBeijingDateTime(batch.started_at)} · </>}
              新增 {batch.total_new} 条 · {batch.source_count} 个信息源
            </div>
          </div>
          <div style={{ color: "var(--ink-muted)" }}>
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </div>
        </div>
        {expanded && (
          <div className="timeline-card-body">
            <CollectionBatchProgress summary={batch.batch_summary} />
            {batch.runs.map((r) => (
              <div key={r.id} className="timeline-source-row">
                <span className="source-name">{r.source_name || r.source_id}</span>
                <SourceRunDetail run={r} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function HistoryPage() {
  const [activeRuns, setActiveRuns] = useState<ActiveRunOut[]>([]);
  const [batches, setBatches] = useState<BatchOut[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const [expandedBatch, setExpandedBatch] = useState<string | null>(null);
  const [timelineExpanded, setTimelineExpanded] = useState<Set<string>>(new Set());
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [taskCategory, setTaskCategory] = useState<TaskCategory>("all");
  const [stoppingRunId, setStoppingRunId] = useState<string | null>(null);
  const [stoppingAll, setStoppingAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ar, b, reportList] = await Promise.all([
        fetchActiveRuns().catch(() => []),
        fetchBatches(undefined, 30).catch(() => []),
        fetchReports().then((result) => result.reports).catch(() => []),
      ]);
      setActiveRuns(ar);
      setBatches(b);
      setReports(reportList);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  // 轮询活跃任务，实时反映「正在执行」状态（避免陈旧数据）。
  // 当任务从有变为无（采集结束）时，自动重新加载批次与报告。
  useEffect(() => {
    const timer = window.setInterval(async () => {
      const ar = await fetchActiveRuns().catch(() => []);
      setActiveRuns((prev) => {
        if (prev.length > 0 && ar.length === 0) void load();
        return ar;
      });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  const handleClearHistory = async () => {
    setClearing(true);
    try {
      const resp = await fetch("/api/v1/runs/clear", {
        method: "POST",
        headers: await operatorWriteHeaders(),
      });
      const data = await resp.json();
      if (data.ok) {
        setActiveRuns([]);
        setBatches([]);
        await load();
      } else {
        alert(data.message || data.detail || "清空失败");
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "清空失败");
    }
    setClearing(false);
    setShowClearConfirm(false);
  };

  const toggleTimeline = (batchId: string) => {
    setTimelineExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(batchId)) next.delete(batchId); else next.add(batchId);
      return next;
    });
  };

  const handleStopRun = async (runId: string) => {
    setStoppingRunId(runId);
    try {
      await stopRun(runId);
      await load();
      // 停止后立即同步全局统计：情报主页的今日/本周采集数、仪表盘与采集条目
      window.dispatchEvent(new CustomEvent("collection-data-updated"));
      window.dispatchEvent(new CustomEvent("collection-finished"));
    } catch (e) {
      alert(e instanceof Error ? e.message : "停止任务失败");
    }
    setStoppingRunId(null);
  };

  const handleStopAll = async () => {
    setStoppingAll(true);
    try {
      await stopAllRuns();
      await load();
      // 停止后立即同步全局统计（已采集信息保留入库）
      window.dispatchEvent(new CustomEvent("collection-data-updated"));
      window.dispatchEvent(new CustomEvent("collection-finished"));
    } catch (e) {
      alert(e instanceof Error ? e.message : "一键停止失败");
    }
    setStoppingAll(false);
  };

  const activeReports = reports.filter((report) => report.status === "pending" || report.status === "generating");
  const completedReports = reports.filter((report) => report.status !== "pending" && report.status !== "generating");
  const showCollections = taskCategory !== "report";
  const showReports = taskCategory !== "collection";

  if (loading) return <div className="loading">加载任务...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>任务查看</h2>
          <p className="text-muted">集中查看采集与报告任务的进行状态、结果和历史。</p>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            type="button"
            className="btn btn-sm btn-danger"
            onClick={() => setShowClearConfirm(true)}
            disabled={batches.length === 0}
          >
            <Trash2 size={12} /> 清空采集历史
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
            <RefreshCw size={12} className={loading ? "spin" : ""} />
          </button>
        </div>
      </div>

      <div className="view-tabs">
        {(["all", "collection", "report"] as TaskCategory[]).map((category) => (
          <button
            type="button"
            key={category}
            className={`view-tab ${taskCategory === category ? "view-tab--active" : ""}`}
            onClick={() => setTaskCategory(category)}
          >{category === "all" ? "全部任务" : category === "collection" ? "采集任务" : "报告任务"}</button>
        ))}
      </div>

      {showCollections && (
      <div className="view-tabs" style={{ marginTop: 10 }}>
        <button
          type="button"
          className={`view-tab ${viewMode === "cards" ? "view-tab--active" : ""}`}
          onClick={() => setViewMode("cards")}
        >卡片视图</button>
        <button
          type="button"
          className={`view-tab ${viewMode === "timeline" ? "view-tab--active" : ""}`}
          onClick={() => setViewMode("timeline")}
        >时间线视图</button>
      </div>
      )}

      {showCollections && activeRuns.length > 0 && (
        <div className="history-active-section" style={{ marginBottom: 20 }}>
          <h3 style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="pulse-dot" /> 正在执行 ({activeRuns.length})
            <button
              type="button"
              className="btn btn-sm btn-danger"
              onClick={() => void handleStopAll()}
              disabled={stoppingAll}
            >
              <Square size={12} /> {stoppingAll ? "停止中..." : "一键停止全部"}
            </button>
          </h3>
          {activeRuns
            .filter((run, index, runs) => run.batch_summary && runs.findIndex(
              (candidate) => candidate.batch_summary?.batch_id === run.batch_summary?.batch_id,
            ) === index)
            .map((run) => <CollectionBatchProgress key={run.batch_summary!.batch_id} summary={run.batch_summary} compact />)}
          {activeRuns.map((run) => (
            <div key={run.id} className="active-run-card">
              <div className="run-info">
                <h4>{run.topic_name || run.source_name || run.source_id}</h4>
                <p>
                  {run.source_name && <>来源: {run.source_name} · </>}
                  {run.keywords_used?.length > 0 && <>关键词: {run.keywords_used.slice(0, 3).join(", ")}{run.keywords_used.length > 3 ? "..." : ""} · </>}
                  {run.started_at && <>开始: {formatBeijingTime(run.started_at)}</>}
                  {run.duration_seconds != null && <> · 已耗时: {Math.floor(run.duration_seconds / 60)}分{run.duration_seconds % 60}秒</>}
                </p>
              </div>
              <div className="run-status">
                {run.items_found > 0 && <span className="chip chip--blue">{run.items_found} 条</span>}
                <StatusBadge status={run.status as any} />
                <button type="button" className="btn btn-sm btn-danger" onClick={() => void handleStopRun(run.id)} disabled={stoppingRunId === run.id}>
                  <Square size={12} /> {stoppingRunId === run.id ? "停止中..." : "停止"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showReports && activeReports.length > 0 && (
        <div className="history-active-section" style={{ marginBottom: 20 }}>
          <h3><span className="pulse-dot" /> 正在生成报告 ({activeReports.length})</h3>
          {activeReports.map((report) => (
            <div key={report.id} className="active-run-card">
              <div className="run-info">
                <h4>{report.title || report.topic_name || "分析报告"}</h4>
                <p>{report.topic_name || report.topic_id} · 报告生成时使用 {report.item_count} 条采集信息 · {report.created_at && `创建于 ${formatBeijingTime(report.created_at)}`}</p>
              </div>
              <div className="run-status"><StatusBadge status={report.status as any} /></div>
            </div>
          ))}
        </div>
      )}

      {showReports && completedReports.length > 0 && (
        <section style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 12 }}><FileText size={14} style={{ verticalAlign: "middle" }} /> 报告任务 ({completedReports.length})</h3>
          <div className="card-list">
            {completedReports.map((report) => (
              <article key={report.id} className="history-batch-card">
                <div className="batch-header">
                  <div>
                    <h4 style={{ display: "flex", alignItems: "center", gap: 6 }}>{report.title}<StatusBadge status={report.status as any} /></h4>
                    <div className="batch-meta">{report.topic_name || report.topic_id} · 使用 {report.item_count} 条信息</div>
                  </div>
                  <div className="batch-meta">{formatReportTime(report)}</div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeRuns.length === 0 && batches.length === 0 && reports.length === 0 && (
        <EmptyState
          icon={<Clock size={32} style={{ opacity: 0.3 }} />}
          title="暂无任务"
          description="执行采集或生成报告后，任务进度和历史会显示在这里"
        />
      )}

      {showCollections && viewMode === "cards" && batches.length > 0 && (
        <div>
          <h3 style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 12 }}>
            已完成批次 ({batches.length})
          </h3>
          {batches.map((batch) => (
            <div key={batch.batch_id} className="history-batch-card">
              <div className="batch-header" onClick={() => setExpandedBatch(expandedBatch === batch.batch_id ? null : batch.batch_id)}>
                <div>
                  <h4 style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    {batch.batch_label || batch.topic_name || "多源采集"}
                    <StatusBadge status={batch.status as any} />
                  </h4>
                  <div className="batch-meta">
                  {batch.started_at && <span>{formatBeijingDateTime(batch.started_at)}</span>}
                  </div>
                </div>
                <div className="batch-meta">
                  <span>新增 {batch.total_new} 条 · {batch.source_count} 源</span>
                  {expandedBatch === batch.batch_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </div>
              </div>
              {expandedBatch === batch.batch_id && (
                <div className="batch-detail">
                  <CollectionBatchProgress summary={batch.batch_summary} />
                  {batch.runs.map((r) => (
                    <div key={r.id} className="batch-source-row">
                      <span className="source-name">{r.source_name || r.source_id}</span>
                      <SourceRunDetail run={r} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showCollections && viewMode === "timeline" && batches.length > 0 && (
        <div className="timeline">
          {batches.map((batch) => (
            <TimelineNode
              key={batch.batch_id}
              batch={batch}
              expanded={timelineExpanded.has(batch.batch_id)}
              onToggle={() => toggleTimeline(batch.batch_id)}
            />
          ))}
        </div>
      )}

      <ConfirmDialog
        open={showClearConfirm}
        title="清空采集历史"
        message="确定要清空所有采集历史和条目吗？\n\n此操作将删除所有采集记录和已采集的条目，不可撤销。"
        variant="danger"
        confirmLabel="确认清空"
        onClose={() => setShowClearConfirm(false)}
        onConfirm={handleClearHistory}
        loading={clearing}
      />
    </div>
  );
}
