import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  Activity, AlertTriangle, CheckCircle2, ChevronRight, CircleDot, Clock3,
  FileSearch, Languages, ListTree, Search, ShieldCheck, X,
} from "lucide-react";

import { fetchActiveRuns, fetchRunFailures } from "../api";
import type { ActiveRunOut, CollectionProgressEvent, RunFailure } from "../types";
import { formatBeijingTime } from "../utils/date";

const STATUS_WORDS = ["全网搜集", "智能处理", "服务战略"] as const;
const POLL_INTERVAL_MS = 2000;
const STATUS_COLORS = [
  { color: "#67e8f9", glow: "rgba(34,211,238,.72)" },
  { color: "#fbbf24", glow: "rgba(245,158,11,.68)" },
  { color: "#4ade80", glow: "rgba(34,197,94,.62)" },
  { color: "#fb7185", glow: "rgba(244,63,94,.6)" },
  { color: "#93c5fd", glow: "rgba(59,130,246,.68)" },
] as const;
const STATUS_MOTIONS = [
  { enterX: 28, enterY: 8, exitX: -30, exitY: -8 },
  { enterX: -28, enterY: 9, exitX: 30, exitY: -10 },
  { enterX: 0, enterY: -18, exitX: 24, exitY: 15 },
  { enterX: 0, enterY: 18, exitX: -24, exitY: -14 },
  { enterX: 24, enterY: -14, exitX: -28, exitY: 12 },
] as const;

const STAGE_LABELS: Record<string, string> = {
  queued: "任务准备", connecting: "连接信息源", searching: "全网检索",
  fetched: "候选汇集", discovered: "发现信息", window_review: "时间核验",
  quality_review: "智能审核", rejected: "排除低值信息", approved: "审核通过",
  persisted: "去重入库", translating: "中文转译", translated: "内容整理",
  completed: "采集完成", failed: "执行失败",
};

type ActivityIndicatorProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function nextRandomIndex(total: number, current: number): number {
  if (total <= 1) return 0;
  let next = current;
  while (next === current) next = Math.floor(Math.random() * total);
  return next;
}

function stageIcon(stage: string) {
  if (stage === "translated" || stage === "translating") return <Languages size={14} />;
  if (stage === "quality_review" || stage === "approved") return <ShieldCheck size={14} />;
  if (stage === "discovered" || stage === "fetched") return <FileSearch size={14} />;
  if (stage === "completed") return <CheckCircle2 size={14} />;
  if (stage === "searching" || stage === "connecting") return <Search size={14} />;
  return <CircleDot size={12} />;
}

function currentEvent(run: ActiveRunOut): CollectionProgressEvent | undefined {
  return run.progress_events?.[run.progress_events.length - 1];
}

function elapsedText(seconds: number | null): string {
  if (seconds == null) return "刚刚开始";
  if (seconds < 60) return `${seconds} 秒`;
  return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
}

function ActivityPill({ word, count, colorIndex, motionIndex }: {
  word: string;
  count: number;
  colorIndex: number;
  motionIndex: number;
}) {
  const color = STATUS_COLORS[colorIndex];
  const motion = STATUS_MOTIONS[motionIndex];
  const style = {
    "--activity-color": color.color,
    "--activity-glow": color.glow,
    "--activity-enter-x": `${motion.enterX}px`,
    "--activity-enter-y": `${motion.enterY}px`,
    "--activity-exit-x": `${motion.exitX}px`,
    "--activity-exit-y": `${motion.exitY}px`,
  } as React.CSSProperties;
  return (
    <div className="collection-activity-pill" aria-live="polite" style={style}>
      <span className="collection-activity-pill__signal" aria-hidden="true">
        <i /><i /><i /><i /><i />
      </span>
      <span key={`${word}-${colorIndex}-${motionIndex}`} className="collection-activity-pill__word">{word}</span>
      <span className="collection-activity-pill__count">{count}</span>
    </div>
  );
}

function TaskOverview({ runs, active, onOpenFailures }: {
  runs: ActiveRunOut[];
  active: boolean;
  onOpenFailures: (batchIds: string[]) => void;
}) {
  const summaries = new Map<string, ActiveRunOut>();
  runs.forEach((run) => summaries.set(run.batch_id || run.id, run));
  const batches = [...summaries.values()];
  const total = batches.reduce((sum, run) => sum + (run.batch_total_sources ?? 1), 0);
  const completed = active
    ? batches.reduce((sum, run) => sum + (run.batch_completed_sources ?? 0), 0)
    : total;
  const failed = active
    ? batches.reduce((sum, run) => sum + (run.batch_failed_sources ?? 0), 0)
    : 0;
  const remaining = Math.max(0, total - completed - failed);
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;
  const tasks = [...new Set(runs.map((run) => run.topic_name || "即时采集任务"))];
  const keywords = [...new Set(runs.flatMap((run) => run.keywords_used || []))];
  const channels = [...new Set(runs.map((run) => run.source_name || run.source_id))];
  const batchIds = [...new Set(runs.map((run) => run.batch_id).filter((id): id is string => Boolean(id)))];

  const openFailures = () => {
    if (failed > 0 && batchIds.length > 0) onOpenFailures(batchIds);
  };

  return (
    <section className="collection-task-overview">
      <div className="collection-task-overview__heading">
        <div>
          <span>当前采集任务</span>
          <h4>{tasks.join("、") || "正在准备采集任务"}</h4>
        </div>
        <strong>{active ? `${progress}%` : "已完成"}</strong>
      </div>
      <div className="collection-task-overview__progress" aria-label={`总体进度 ${progress}%`}>
        <span style={{ width: `${active ? progress : 100}%` }} />
      </div>
      <dl className="collection-task-overview__facts">
        <div><dt>采集关键词</dt><dd>{keywords.length ? keywords.slice(0, 8).join("、") : "按主题语义提示词采集"}</dd></div>
        <div><dt>当前采集渠道</dt><dd>{active ? channels.join("、") : "本轮渠道均已完成"}</dd></div>
      </dl>
      <div className="collection-task-overview__counts">
        <div><strong>{total}</strong><span>信息源总数</span></div>
        <div><strong>{completed}</strong><span>已采集</span></div>
        <div><strong>{remaining}</strong><span>待采集</span></div>
        <button
          type="button"
          className={`collection-task-overview__failure ${failed > 0 ? "collection-task-overview__failure--actionable" : ""}`}
          onDoubleClick={openFailures}
          onKeyDown={(event) => {
            if ((event.key === "Enter" || event.key === " ") && failed > 0) {
              event.preventDefault();
              openFailures();
            }
          }}
          disabled={failed === 0}
          title={failed > 0 ? "双击查看失败原因与处理建议" : "本轮没有失败信息源"}
        >
          <strong>{failed}</strong><span>{failed > 0 ? "失败 · 双击查看" : "失败"}</span>
        </button>
      </div>
    </section>
  );
}

function RunProgress({ run }: { run: ActiveRunOut }) {
  const events = [...(run.progress_events || [])].reverse();
  const current = currentEvent(run);
  return (
    <article className="collection-run-progress">
      <header className="collection-run-progress__header">
        <div className="collection-run-progress__identity">
          <span className="collection-run-progress__live"><Activity size={15} /></span>
          <div><h4>{run.source_name || run.source_id}</h4><p>{run.topic_name || "即时采集"}</p></div>
        </div>
        <span className="collection-run-progress__elapsed"><Clock3 size={12} />{elapsedText(run.duration_seconds)}</span>
      </header>
      <div className="collection-run-progress__summary">
        <div><span>当前阶段</span><strong>{STAGE_LABELS[current?.stage || "queued"] || "处理中"}</strong></div>
        <div><span>候选信息</span><strong>{run.items_found}</strong></div>
        <div><span>新增入库</span><strong>{run.items_new}</strong></div>
      </div>
      <div className="collection-event-stream">
        {events.length === 0 ? (
          <div className="collection-event-stream__empty">正在建立采集连接，过程信息即将到达...</div>
        ) : events.map((event, index) => (
          <div key={`${event.created_at}-${index}`} className={`collection-event collection-event--${event.status}`}>
            <span className="collection-event__rail"><span className="collection-event__icon">{stageIcon(event.stage)}</span></span>
            <div className="collection-event__body">
              <div className="collection-event__meta"><span>{STAGE_LABELS[event.stage] || event.stage}</span><time>{formatBeijingTime(event.created_at)}</time></div>
              <p>{event.message}</p>
              {typeof event.detail?.url === "string" && event.detail.url && (
                <a href={event.detail.url} target="_blank" rel="noreferrer">查看源链接 <ChevronRight size={12} /></a>
              )}
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}

export function CollectionActivityIndicator({ open, onOpenChange }: ActivityIndicatorProps) {
  const [runs, setRuns] = useState<ActiveRunOut[]>([]);
  const [lastRuns, setLastRuns] = useState<ActiveRunOut[]>([]);
  const [frame, setFrame] = useState({ word: 0, color: 0, motion: 0 });
  const [starting, setStarting] = useState(false);
  const [failures, setFailures] = useState<RunFailure[] | null>(null);
  const [failureError, setFailureError] = useState<string | null>(null);
  const [loadingFailures, setLoadingFailures] = useState(false);

  const openFailures = async (batchIds: string[]) => {
    setLoadingFailures(true);
    setFailureError(null);
    setFailures([]);
    try {
      setFailures(await fetchRunFailures(batchIds));
    } catch (error) {
      setFailureError(error instanceof Error ? error.message : "无法读取失败诊断信息");
    } finally {
      setLoadingFailures(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    let previousActiveCount = 0;
    const refresh = async () => {
      try {
        const nextRuns = await fetchActiveRuns();
        if (cancelled) return;
        if (previousActiveCount > 0 && nextRuns.length === 0) {
          window.dispatchEvent(new CustomEvent("collection-data-updated"));
        }
        previousActiveCount = nextRuns.length;
        setRuns(nextRuns);
        if (nextRuns.length > 0) setLastRuns(nextRuns);
      } catch {
        // Keep the last verified progress visible during a transient request failure.
      }
    };
    const handleStarted = () => { setStarting(true); void refresh(); };
    const handleFinished = () => {
      setStarting(false);
      void refresh();
      window.dispatchEvent(new CustomEvent("collection-data-updated"));
    };
    void refresh();
    const timer = window.setInterval(refresh, POLL_INTERVAL_MS);
    window.addEventListener("collection-started", handleStarted);
    window.addEventListener("collection-finished", handleFinished);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener("collection-started", handleStarted);
      window.removeEventListener("collection-finished", handleFinished);
    };
  }, []);

  useEffect(() => {
    if (runs.length === 0 && !starting) return;
    const timer = window.setInterval(() => setFrame((current) => ({
      word: (current.word + 1) % STATUS_WORDS.length,
      color: nextRandomIndex(STATUS_COLORS.length, current.color),
      motion: nextRandomIndex(STATUS_MOTIONS.length, current.motion),
    })), 1260);
    return () => window.clearInterval(timer);
  }, [runs.length, starting]);

  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") onOpenChange(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onOpenChange, open]);

  const displayedRuns = runs.length > 0 ? runs : lastRuns;
  const isBusy = starting || runs.length > 0;
  const totalEvents = useMemo(
    () => displayedRuns.reduce((sum, run) => sum + (run.progress_events?.length || 0), 0),
    [displayedRuns],
  );

  return (
    <>
      {isBusy && (
        <div className="collection-activity-cluster">
          <ActivityPill
            word={STATUS_WORDS[frame.word]}
            count={Math.max(1, runs.length)}
            colorIndex={frame.color}
            motionIndex={frame.motion}
          />
          <button type="button" className="collection-progress-button" onClick={() => onOpenChange(true)}>
            <ListTree size={16} /><span>查看进度</span>
          </button>
        </div>
      )}
      {open && createPortal(
        <aside className="collection-drawer" role="region" aria-label="实时采集进度">
          <header className="collection-drawer__header">
            <div>
              <span className="collection-drawer__eyebrow"><span className="pulse-dot" />{runs.length > 0 ? "实时作业中" : "本轮作业已结束"}</span>
              <h3>采集进度与处理过程</h3>
              <p>{displayedRuns.length} 个信息源任务 · 已记录 {totalEvents} 个处理节点</p>
            </div>
            <button type="button" className="btn-icon" onClick={() => onOpenChange(false)} title="收起实时进度"><X size={18} /></button>
          </header>
          <div className="collection-drawer__content">
            {displayedRuns.length > 0 ? (
              <><TaskOverview runs={displayedRuns} active={runs.length > 0} onOpenFailures={(batchIds) => void openFailures(batchIds)} />{displayedRuns.map((run) => <RunProgress key={run.id} run={run} />)}</>
            ) : <div className="collection-drawer__empty">当前没有正在进行的采集任务。</div>}
          </div>
        </aside>,
        document.body,
      )}
      {failures && createPortal(
        <FailureDiagnosticsDialog
          failures={failures}
          loading={loadingFailures}
          error={failureError}
          onClose={() => setFailures(null)}
        />,
        document.body,
      )}
    </>
  );
}

function FailureDiagnosticsDialog({
  failures,
  loading,
  error,
  onClose,
}: {
  failures: RunFailure[];
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <section className="modal collection-failure-modal" role="dialog" aria-modal="true" aria-labelledby="failure-diagnostics-title" onClick={(event) => event.stopPropagation()}>
        <header className="collection-failure-modal__header">
          <div>
            <span className="collection-failure-modal__eyebrow"><AlertTriangle size={14} />采集异常诊断</span>
            <h3 id="failure-diagnostics-title">失败信息源与处理建议</h3>
            <p>系统依据本轮错误和历史失败次数给出建议；连续无法修复的失效来源会标记为可删除候选。</p>
          </div>
          <button type="button" className="btn-icon" title="关闭" onClick={onClose}><X size={18} /></button>
        </header>
        <div className="collection-failure-modal__content">
          {loading && <div className="loading">正在读取失败诊断...</div>}
          {error && <div className="error-banner">{error}</div>}
          {!loading && !error && failures.length === 0 && <div className="collection-drawer__empty">本轮未找到可诊断的失败记录。</div>}
          {!loading && !error && failures.map((failure) => (
            <article key={failure.run_id} className="failure-diagnostic-row">
              <div className="failure-diagnostic-row__title">
                <div><strong>{failure.source_name}</strong><span>{failure.source_channel} · 历史失败 {failure.recurring_failures} 次</span></div>
                <span className={`badge ${failure.suggested_action === "delete_candidate" ? "badge--red" : "badge--yellow"}`}>
                  {failure.suggested_action === "delete_candidate" ? "建议删除" : "可修复"}
                </span>
              </div>
              <p><strong>建议：</strong>{failure.recommendation}</p>
              <details>
                <summary>查看技术错误</summary>
                <ul>{failure.errors.map((item, index) => <li key={`${failure.run_id}-${index}`}>{item}</li>)}</ul>
              </details>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
