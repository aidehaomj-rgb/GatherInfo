import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, TrendingUp, Globe, Database, Tags, AlertCircle,
} from "lucide-react";
import { fetchDashboard, collectTopic, fetchTopics } from "../api";
import type { DashboardData, Topic } from "../types";
import type { EChartsOption } from "echarts";
import { useApi } from "../hooks/useApi";

const EChart = lazy(() => import("./EChart").then(m => ({ default: m.EChart })));

export function DashboardPage() {
  const { data, loading, error, refresh } = useApi<DashboardData>(
    (_signal) => fetchDashboard(),
    [],
  );
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [collectMsg, setCollectMsg] = useState<string | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);

  useEffect(() => {
    fetchTopics().then(setTopics).catch(() => {});
  }, []);

  const triggerCollect = useCallback(async (topicId: string) => {
    setRefreshing(topicId);
    setCollectMsg(null);
    try {
      const results = await collectTopic(topicId);
      const total = results.reduce((s, r) => s + r.items_new, 0);
      const failed = results.filter((r) => r.errors?.length).length;
      setCollectMsg(`采集完成：新增 ${total} 条${failed > 0 ? `，${failed} 个来源失败` : ""}`);
      await refresh();
    } catch (err) {
      setCollectMsg(`采集失败：${err instanceof Error ? err.message : "未知错误"}`);
    }
    setRefreshing(null);
  }, [refresh]);

  // Source health → horizontal bar chart
  const sourceBarOption: EChartsOption = useMemo(() => {
    const sorted = [...(data?.source_health ?? [])].sort((a, b) => b.items_collected - a.items_collected).slice(0, 12);
    return {
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 120, right: 40, top: 5, bottom: 20 },
      xAxis: { type: "value", axisLabel: { fontSize: 10, color: "#7e93b0" }, splitLine: { lineStyle: { color: "#1e3a5f", type: "dashed" } } },
      yAxis: {
        type: "category",
        inverse: true,
        data: sorted.map((s) => s.name),
        axisLabel: { fontSize: 11, color: "#cbd5e1", width: 110, overflow: "truncate" },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [{
        type: "bar",
        data: sorted.map((s) => ({
          value: s.items_collected,
          itemStyle: { color: s.is_active ? "#3b82f6" : "#475569", borderRadius: [0, 4, 4, 0] },
        })),
        barWidth: 16,
        label: { show: true, position: "right", fontSize: 10, color: "#7e93b0" },
      }],
    };
  }, [data?.source_health]);

  // Tag font-size scaling
  const maxTagCount = useMemo(
    () => Math.max(1, ...(data?.top_tags ?? []).slice(0, 20).map((t) => t.count)),
    [data?.top_tags],
  );


  if (loading) return <div className="loading">加载仪表盘...</div>;
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return null;

  const { summary, top_tags, source_health, daily_trend, categories } = data;

  // Compute day-over-day and week-over-week comparisons from daily_trend
  const trendLen = daily_trend.length;
  const yesterdayCount = trendLen >= 2 ? daily_trend[trendLen - 2].count : 0;
  const todayCount = trendLen >= 1 ? daily_trend[trendLen - 1].count : 0;
  const dodChange = yesterdayCount > 0 ? ((todayCount - yesterdayCount) / yesterdayCount * 100) : null;

  // Week-over-week: compare last 7 days vs previous 7 (approximate from trend)
  const recent7 = daily_trend.slice(-7).reduce((s, d) => s + d.count, 0);
  const prev7 = trendLen >= 14
    ? daily_trend.slice(-14, -7).reduce((s, d) => s + d.count, 0)
    : daily_trend.slice(0, -7).reduce((s, d) => s + d.count, 0);
  const wowChange = prev7 > 0 ? ((recent7 - prev7) / prev7 * 100) : null;

  const statCards = [
    { label: "总条目", value: summary.total_items, icon: Database, color: "#3b82f6", mom: null },
    { label: "今日采集", value: summary.items_today, icon: TrendingUp, color: "#22c55e", mom: dodChange },
    { label: "活跃信息源", value: summary.active_sources, icon: Globe, color: "#f59e0b", mom: null },
    { label: "主题数", value: summary.total_topics, icon: Tags, color: "#8b5cf6", mom: null },
    { label: "标签数", value: summary.total_tags, icon: AlertCircle, color: "#ec4899", mom: null },
    { label: "本周新增", value: summary.items_this_week, icon: RefreshCw, color: "#06b6d4", mom: wowChange },
  ];

  const trendOption: EChartsOption = {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: daily_trend.map((d) => d.date.slice(5)), axisLabel: { fontSize: 11, color: "#7e93b0" } },
    yAxis: { type: "value", axisLabel: { fontSize: 10, color: "#7e93b0" }, splitLine: { lineStyle: { color: "#1e3a5f", type: "dashed" } } },
    series: [{
      name: "采集条目", type: "line", data: daily_trend.map((d) => d.count),
      smooth: true, symbol: "circle", symbolSize: 6,
      lineStyle: { color: "#3b82f6", width: 2 },
      itemStyle: { color: "#3b82f6" },
      areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [{ offset: 0, color: "rgba(59,130,246,0.3)" }, { offset: 1, color: "rgba(59,130,246,0.01)" }] } },
    }],
    grid: { left: 40, right: 20, top: 10, bottom: 30 },
  };

  const catChartOption: EChartsOption = {
    tooltip: { trigger: "item" },
    series: [{
      type: "pie", radius: ["50%", "80%"], center: ["50%", "55%"],
      data: categories.slice(0, 8).map((c) => ({ name: c.category, value: c.count })),
      label: { fontSize: 11, color: "#7e93b0" }, emphasis: { label: { fontSize: 14, fontWeight: "bold" } },
      itemStyle: { borderRadius: 4, borderColor: "#111827", borderWidth: 2 },
    }],
  };


  return (
    <div className="dashboard">
      {/* Stat cards */}
      <div className="stat-grid">
        {statCards.map((sc) => {
          const Icon = sc.icon;
          return (
            <article key={sc.label} className="stat-card">
              <div className="stat-card-header">
                <span style={{ color: sc.color }}>{Icon ? <Icon size={16} /> : null}</span>
                <span className="stat-label">{sc.label}</span>
              </div>
              <strong className="stat-value">{sc.value.toLocaleString()}</strong>
              {sc.mom !== null && (
                <div className={`stat-mom ${sc.mom > 0 ? "stat-mom--up" : sc.mom < 0 ? "stat-mom--down" : "stat-mom--neutral"}`}>
                  {sc.mom > 0 ? "↑" : sc.mom < 0 ? "↓" : "→"} {Math.abs(sc.mom).toFixed(1)}%
                  <span style={{ fontSize: "0.7rem", opacity: 0.7 }}>较上期</span>
                </div>
              )}
            </article>
          );
        })}
      </div>

      {/* Charts row */}
      <div className="chart-row">
        <div className="chart-card">
          <h3>每日采集趋势</h3>
          <Suspense fallback={<div className="chart-loading">加载图表...</div>}><EChart option={trendOption} style={{ height: 220 }} /></Suspense>
        </div>
        <div className="chart-card">
          <h3>分类分布</h3>
          <Suspense fallback={<div className="chart-loading">加载图表...</div>}><EChart option={catChartOption} style={{ height: 220 }} /></Suspense>
        </div>
      </div>

      {/* Second charts row: source bars + tags */}
      <div className="chart-row">
        <div className="chart-card">
          <h3>信息源采集量排名</h3>
          {source_health.length > 0 ? (
            <Suspense fallback={<div className="chart-loading" style={{ height: 280 }}>加载图表...</div>}><EChart option={sourceBarOption} style={{ height: 280 }} /></Suspense>
          ) : (
            <p className="text-muted" style={{ padding: 40, textAlign: "center" }}>暂无数据</p>
          )}
        </div>
        <div className="chart-card">
          <h3>热门标签</h3>
          <div className="tag-cloud" style={{ maxHeight: 280, overflowY: "auto" }}>
            {top_tags.slice(0, 24).map((t) => {
              const ratio = t.count / maxTagCount;
              const size = 0.72 + ratio * 0.6; // 0.72rem ~ 1.32rem
              const alpha = 0.4 + ratio * 0.6; // 0.4 ~ 1.0 opacity
              return (
                <span
                  key={t.id}
                  className="tag-chip"
                  title={`${t.namespace} · ${t.count} 条`}
                  style={{
                    fontSize: `${size}rem`,
                    opacity: alpha,
                    padding: `${3 + ratio * 4}px ${6 + ratio * 8}px`,
                  }}
                >
                  {t.value}
                  <em>{t.count}</em>
                </span>
              );
            })}
            {top_tags.length === 0 && (
              <p className="text-muted" style={{ padding: 20 }}>暂无标签</p>
            )}
          </div>
        </div>
      </div>

      {/* Quick collect — card-style */}
      <div className="panel">
        <h3>快速采集</h3>
        {collectMsg && (
          <div className="toast" onClick={() => setCollectMsg(null)}>
            {collectMsg}
          </div>
        )}
        <div className="card-list" style={{ marginTop: 8 }}>
          {topics.filter((t) => t.is_active !== false).map((t) => {
            const lastRun = t.last_run_at ? new Date(t.last_run_at) : null;
            const ago = lastRun
              ? (Date.now() - lastRun.getTime()) < 3600000
                ? `${Math.floor((Date.now() - lastRun.getTime()) / 60000)} 分钟前`
                : (Date.now() - lastRun.getTime()) < 86400000
                  ? `${Math.floor((Date.now() - lastRun.getTime()) / 3600000)} 小时前`
                  : `${Math.floor((Date.now() - lastRun.getTime()) / 86400000)} 天前`
              : null;
            return (
              <article key={t.id} className="card-item card-item--compact">
                <div className="card-item-header">
                  <div className="card-item-title">
                    <h4>{t.name}</h4>
                    <span className="text-muted small">{t.id}</span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    onClick={() => triggerCollect(t.id)}
                    disabled={refreshing === t.id}
                  >
                    <RefreshCw size={12} className={refreshing === t.id ? "spin" : ""} />
                    {refreshing === t.id ? "采集中..." : "采集"}
                  </button>
                </div>
                <div className="card-item-meta card-item-meta--compact">
                  <span className="meta-inline"><strong>累计采集:</strong> {t.total_items_collected} 条</span>
                  {t.schedule_cron && (
                    <span className="meta-inline"><strong>调度:</strong> {t.schedule_cron}</span>
                  )}
                  {ago && (
                    <span className="meta-inline text-muted">上次: {ago}</span>
                  )}
                  {!lastRun && (
                    <span className="meta-inline text-muted">尚未运行</span>
                  )}
                </div>
              </article>
            );
          })}
          {topics.filter((t) => t.is_active !== false).length === 0 && (
            <p className="text-muted" style={{ padding: 16, textAlign: "center" }}>暂无活跃主题，请先在主题管理中创建。</p>
          )}
        </div>
      </div>
    </div>
  );
}
