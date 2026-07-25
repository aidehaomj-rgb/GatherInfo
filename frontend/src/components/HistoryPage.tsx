import { useEffect, useState, useCallback } from "react";
import { Clock, RefreshCw, ChevronDown, ChevronRight, CheckCircle, AlertTriangle, Trash2 } from "lucide-react";
import { fetchActiveRuns, fetchBatches } from "../api";
import type { ActiveRunOut, BatchOut } from "../types";
import { EmptyState } from "./shared/EmptyState";
import { StatusBadge } from "./shared/StatusBadge";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { formatBeijingDateTime, formatBeijingTime } from "../utils/date";

type ViewMode = "cards" | "timeline";

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
            {batch.runs.map((r) => (
              <div key={r.id} className="timeline-source-row">
                <span>{r.source_name || r.source_id}</span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  {r.status === "completed" ? <CheckCircle size={12} style={{ color: "var(--green)" }} /> :
                   r.status === "failed" ? <AlertTriangle size={12} style={{ color: "var(--red)" }} /> : null}
                  新增 {r.items_new} / 共 {r.items_found} 条
                  {r.duration_ms != null && <> · {(r.duration_ms / 1000).toFixed(1)}秒</>}
                </span>
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const [expandedBatch, setExpandedBatch] = useState<string | null>(null);
  const [timelineExpanded, setTimelineExpanded] = useState<Set<string>>(new Set());
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ar, b] = await Promise.all([
        fetchActiveRuns().catch(() => []),
        fetchBatches(undefined, 30).catch(() => []),
      ]);
      setActiveRuns(ar);
      setBatches(b);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleClearHistory = async () => {
    setClearing(true);
    try {
      const resp = await fetch("/api/v1/runs/clear", { method: "POST" });
      const data = await resp.json();
      if (data.ok) {
        setActiveRuns([]);
        setBatches([]);
        await load();
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

  if (loading) return <div className="loading">加载采集历史...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>采集历史</h2>
          <p className="text-muted">查看正在执行和已完成的采集任务。</p>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            type="button"
            className="btn btn-sm btn-danger"
            onClick={() => setShowClearConfirm(true)}
            disabled={batches.length === 0}
          >
            <Trash2 size={12} /> 清空历史
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
            <RefreshCw size={12} className={loading ? "spin" : ""} />
          </button>
        </div>
      </div>

      {/* View mode tabs */}
      <div className="view-tabs">
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

      {/* Active runs */}
      {activeRuns.length > 0 && (
        <div className="history-active-section" style={{ marginBottom: 20 }}>
          <h3><span className="pulse-dot" /> 正在执行 ({activeRuns.length})</h3>
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
              </div>
            </div>
          ))}
        </div>
      )}

      {activeRuns.length === 0 && batches.length === 0 && (
        <EmptyState
          icon={<Clock size={32} style={{ opacity: 0.3 }} />}
          title="暂无采集历史"
          description="执行一次采集后，历史记录会显示在这里"
        />
      )}

      {/* Card view */}
      {viewMode === "cards" && batches.length > 0 && (
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
                  {batch.runs.map((r) => (
                    <div key={r.id} className="batch-source-row">
                      <span className="source-name">{r.source_name || r.source_id}</span>
                      <span className="source-stats">
                        {r.status === "completed" ? <CheckCircle size={12} style={{ color: "var(--green)", verticalAlign: "middle", marginRight: 4 }} /> :
                         r.status === "failed" ? <AlertTriangle size={12} style={{ color: "var(--red)", verticalAlign: "middle", marginRight: 4 }} /> : null}
                        新增 {r.items_new} / 共 {r.items_found} 条
                        {r.duration_ms != null && <> · {(r.duration_ms / 1000).toFixed(1)}秒</>}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Timeline view */}
      {viewMode === "timeline" && batches.length > 0 && (
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
