import type { CollectionBatchGap, CollectionBatchSummary } from "../types";

type CollectionBatchProgressProps = {
  summary?: CollectionBatchSummary | null;
  compact?: boolean;
};

const METRIC_LABELS: Array<[string, string[]]> = [
  ["发现候选", ["items_discovered", "discovered", "items_found"]],
  ["日期淘汰", ["items_date_rejected", "date_rejected"]],
  ["主题淘汰", ["items_topic_rejected", "topic_rejected"]],
  ["质量淘汰", ["items_quality_rejected", "quality_rejected"]],
  ["正式新增", ["items_new", "new_items", "items"]],
  ["跨主题复用", ["items_reused", "reused"]],
  ["重复信息", ["items_duplicate", "duplicates"]],
];

const STOP_REASON_LABELS: Record<string, string> = {
  accepted: "目标已达成，采集提前结束",
  dynamic_target_met: "动态目标与覆盖要求已达成",
  target_reached: "目标已达成，采集提前结束",
  max_rounds_reached: "已完成两轮采集，仍有缺口",
  no_new_urls: "本轮未发现新链接，停止补采",
  candidate_budget_reached: "已达到候选审核预算",
  time_budget_reached: "已达到本批次时间预算",
  source_exhausted: "可用来源已完成检索",
  event_volume_insufficient: "客观事件量不足",
  failed: "采集异常终止",
};

function numericValue(record: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function targetValue(target: Record<string, unknown>): number | null {
  return numericValue(target, ["weekly_target", "dynamic_target", "target_items", "items"]);
}

function acceptancePassed(summary: CollectionBatchSummary): boolean {
  return summary.acceptance?.accepted === true || summary.acceptance?.passed === true;
}

function gapText(gap: CollectionBatchGap): string {
  if (typeof gap === "string") return gap;
  if (gap.message) return gap.message;
  if (gap.label) return gap.label;
  if (gap.reason) return gap.follow_up ? `${gap.reason}；${gap.follow_up}` : gap.reason;
  const missing = typeof gap.missing === "number" ? gap.missing : null;
  const typeLabels: Record<string, string> = {
    quantity: "数量", items: "数量", domains: "独立来源", regions: "地域",
    evidence_ratio: "高等级证据占比", source_concentration: "来源集中度",
    date_completeness: "日期完整率", topic_coverage: "主题结构覆盖",
    structure: "主题结构覆盖", formal_completeness: "正式信息完整率",
  };
  const label = typeLabels[gap.type || ""] || gap.type || "验收指标";
  return missing == null ? `${label}未达标` : `${label}还差 ${missing}${gap.type === "quantity" || gap.type === "items" ? " 条" : ""}`;
}

function ratioText(value: number | null): string {
  if (value == null) return "—";
  return `${Math.round((value <= 1 ? value : value / 100) * 100)}%`;
}

function CoverageMetrics({ metrics }: { metrics: Record<string, unknown> }) {
  const domains = numericValue(metrics, ["domains", "independent_domains"]);
  const regions = numericValue(metrics, ["regions", "jurisdictions"]);
  const evidence = numericValue(metrics, ["evidence_ratio", "primary_source_ratio", "high_evidence_ratio"]);
  if (domains == null && regions == null && evidence == null) return null;
  return (
    <dl className="collection-batch-coverage" aria-label="批次覆盖指标">
      <div><dt>独立来源</dt><dd>{domains ?? "—"}</dd></div>
      <div><dt>地域覆盖</dt><dd>{regions ?? "—"}</dd></div>
      <div><dt>高等级证据</dt><dd>{ratioText(evidence)}</dd></div>
    </dl>
  );
}

export function CollectionBatchProgress({ summary, compact = false }: CollectionBatchProgressProps) {
  if (!summary) return null;
  const target = targetValue(summary.target || {});
  const passed = acceptancePassed(summary);
  const visibleMetrics = METRIC_LABELS.map(([label, keys]) => ({
    label,
    value: numericValue(summary.metrics || {}, keys),
  })).filter((metric) => metric.value != null);
  const stopReason = summary.stop_reason
    ? STOP_REASON_LABELS[summary.stop_reason] || summary.stop_reason
    : null;

  return (
    <section className={`collection-batch-progress ${compact ? "collection-batch-progress--compact" : ""}`} aria-label="采集闭环摘要">
      <header className="collection-batch-progress__header">
        <div>
          <span className="collection-batch-progress__eyebrow">采集闭环</span>
          <strong>第 {summary.current_round || 1} / {summary.max_rounds || 2} 轮</strong>
        </div>
        <span className={`collection-batch-progress__acceptance ${passed ? "is-passed" : "is-gap"}`}>
          {passed ? "已达标" : "未达标"}
        </span>
      </header>
      <div className="collection-batch-progress__target">
        <span>动态目标</span><strong>{target ?? "待计算"}{target == null ? "" : " 条 / 周"}</strong>
      </div>
      {visibleMetrics.length > 0 && (
        <dl className="collection-batch-funnel" aria-label="候选审核漏斗">
          {visibleMetrics.map((metric) => (
            <div key={metric.label}><dt>{metric.label}</dt><dd>{metric.value}</dd></div>
          ))}
        </dl>
      )}
      {!compact && <CoverageMetrics metrics={summary.metrics || {}} />}
      {summary.gaps?.length > 0 && (
        <div className="collection-batch-gaps">
          <strong>待补缺口</strong>
          <ul>{summary.gaps.map((gap, index) => <li key={`${gapText(gap)}-${index}`}>{gapText(gap)}</li>)}</ul>
        </div>
      )}
      {stopReason && <p className="collection-batch-progress__stop">停止原因：{stopReason}</p>}
    </section>
  );
}
