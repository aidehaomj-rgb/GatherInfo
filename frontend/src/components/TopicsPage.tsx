import { useEffect, useState, useCallback } from "react";
import { Plus, RefreshCw, Trash2, Edit3, Globe, Target, FileText, BrainCircuit, Square, Clock } from "lucide-react";
import { fetchTopics, createTopic, deleteTopic, updateTopic, collectTopic, generateReport, fetchModels, fetchSources, fetchCategories, fetchActiveRuns, stopRun } from "../api";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import type { Topic, CollectResult, ModelConfig, Source, ActiveRunOut } from "../types";
import { TopicForm } from "./TopicForm";
import { formatBeijingDateTime } from "../utils/date";

const TOPIC_COLLECT_PENDING_KEY = "gatherinfo.topicCollect.pending";
const WEEKLY_ENFORCEMENT_RESEARCH_PROMPT =
  "请检索近一周境外海关、边境执法、港口监管、警察、检察或司法机关，以及可靠区域媒体公开发布的进出口执法案例，形成类似360执法信息周报的线索来源。纳入三类信息：一是香港、台湾、澳门海关或执法机关查获的具体案件，不要求另行证明中国大陆关联；二是其他国家和地区发布的涉中国大陆案件，重点核验中国产、中国籍、中国企业、中国目的地、经中国转运等关联；三是各国境外执法机关查获的重大跨境案件，包括枪支、弹药、爆炸物、武器、暴力犯罪、毒品、野生动物、濒危物种、烟草、假冒侵权和其他违禁品，这类案件可以不涉中国。重点关注走私、查获、扣押、没收、逮捕、调查、起诉、处罚等具体执法行为。使用英语、西班牙语、葡萄牙语，并适当补充法语、阿拉伯语、印尼语、泰语、日语、韩语等检索式。候选信息由大模型自动审核，必须核验原文日期、具体执法行为、来源可信度和纳入依据；不确定或无法核验的信息不得正式入库。排除中国大陆执法案件、普通政策解读、无执法动作或纯转载内容。";

function readPendingTopicIds() {
  try {
    const raw = window.localStorage.getItem(TOPIC_COLLECT_PENDING_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

function writePendingTopicIds(ids: string[]) {
  window.localStorage.setItem(TOPIC_COLLECT_PENDING_KEY, JSON.stringify(Array.from(new Set(ids))));
}

/** Humanize a 5-field cron expression into a Chinese description (best-effort). */
function humanizeCron(cron: string | null): string {
  if (!cron) return "未设置";
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;
  const [min, hour, dom, , dow] = parts;
  const hh = hour.padStart(2, "0");
  const mm = min.padStart(2, "0");
  if (dom === "*" && dow === "*") return `每日 ${hh}:${mm}`;
  if (dom === "*" && dow !== "*") {
    const days = ["日", "一", "二", "三", "四", "五", "六"];
    const d = days[Number(dow)] ?? dow;
    return `每周${d} ${hh}:${mm}`;
  }
  if (dom !== "*" && dow === "*") return `每月${dom}日 ${hh}:${mm}`;
  return cron;
}

export function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Topic | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [collecting, setCollecting] = useState<string | null>(null);
  const [pendingCollectIds, setPendingCollectIds] = useState<string[]>(() => readPendingTopicIds());
  const [activeRuns, setActiveRuns] = useState<ActiveRunOut[]>([]);
  const [stoppingRunId, setStoppingRunId] = useState<string | null>(null);
  const [collectMsg, setCollectMsg] = useState<string | null>(null);
  const [generating, setGenerating] = useState<string | null>(null);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [categories, setCategories] = useState<{id:string;name:string}[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);
  const [expandedKeywordTopics, setExpandedKeywordTopics] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, ms, srcs, cats] = await Promise.all([
        fetchTopics(),
        fetchModels().catch(() => []),
        fetchSources().catch(() => []),
        fetchCategories().catch(() => []),
      ]);
      setTopics(t);
      setModels(ms);
      setSources(srcs);
      setCategories(cats);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const refreshActiveRuns = useCallback(async () => {
    try {
      const runs = await fetchActiveRuns();
      setActiveRuns(runs);
      const activeTopicIds = new Set(runs.map((run) => run.topic_id).filter(Boolean) as string[]);
      setPendingCollectIds((prev) => {
        const next = prev.filter((id) => activeTopicIds.has(id) || collecting === id);
        if (prev.length > 0 && next.length === 0 && prev.some((id) => !activeTopicIds.has(id))) {
          void load();
          setCollectMsg("采集任务已结束，可查看累计采集或采集历史。");
        }
        writePendingTopicIds(next);
        return next;
      });
    } catch {
      // Active-run status is best effort; the collection request itself still reports errors.
    }
  }, [collecting, load]);

  useEffect(() => {
    void refreshActiveRuns();
    const timer = window.setInterval(() => { void refreshActiveRuns(); }, 3000);
    return () => window.clearInterval(timer);
  }, [refreshActiveRuns]);

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: `删除主题 "${id}"？` });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try {
      await deleteTopic(id);
      setTopics((prev) => prev.filter((t) => t.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
    setConfirmDelete(null);
  };

  const handleCollect = async (id: string, researchPrompt?: string) => {
    setCollecting(id);
    setPendingCollectIds((prev) => {
      const next = Array.from(new Set([...prev, id]));
      writePendingTopicIds(next);
      return next;
    });
    setCollectMsg(null);
    try {
      setCollectMsg(researchPrompt
        ? "AI 正在生成检索式并启动采集，页面会自动刷新运行状态。"
        : "采集任务已启动，页面会自动刷新运行状态。");
      const results: CollectResult[] = await collectTopic(id, { researchPrompt });
      const total = results.reduce((s, r) => s + r.items_new, 0);
      const fails = results.filter((r) => r.errors?.length).length;
      setCollectMsg(`采集完成: ${total} 条新增${fails > 0 ? `, ${fails} 源失败` : ""}`);
      setPendingCollectIds((prev) => {
        const next = prev.filter((topicId) => topicId !== id);
        writePendingTopicIds(next);
        return next;
      });
      await load();
      await refreshActiveRuns();
    } catch (e) {
      setCollectMsg(`采集失败: ${e instanceof Error ? e.message : "未知错误"}`);
      setPendingCollectIds((prev) => {
        const next = prev.filter((topicId) => topicId !== id);
        writePendingTopicIds(next);
        return next;
      });
    }
    setCollecting(null);
  };

  const handlePromptCollect = async (topic: Topic) => {
    const defaultPrompt = topic.id === "weekly-enforcement-intelligence"
      ? ((topic as any).description_prompt || WEEKLY_ENFORCEMENT_RESEARCH_PROMPT)
      : ((topic as any).description_prompt || "围绕本主题检索最近一周高价值公开信息，优先官方公告、监管动态、可靠新闻和行业报告。");
    const prompt = window.prompt(
      `请输入“${topic.name}”本次智能检索提示词`,
      defaultPrompt,
    );
    const value = (prompt || "").trim();
    if (!value) return;
    await handleCollect(topic.id, value);
  };

  const handleGenerateReport = async (topicId: string, topicName: string) => {
    setGenerating(topicId);
    try {
      const topic = topics.find((t) => t.id === topicId);
      const defaultModel = models.find((m) => m.is_default);
      const report = await generateReport(topicId, {
        modelId: defaultModel?.id,
      });
      alert(`报告已生成: ${report.title}${report.status === "completed" ? "" : " (" + report.status + ")"}`);
    } catch (e) {
      alert(`报告生成失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setGenerating(null);
  };

  const handleStopRun = async (run: ActiveRunOut) => {
    setStoppingRunId(run.id);
    try {
      await stopRun(run.id);
      if (run.topic_id) {
        setPendingCollectIds((prev) => {
          const next = prev.filter((id) => id !== run.topic_id);
          writePendingTopicIds(next);
          return next;
        });
      }
      setCollectMsg("采集任务已停止。");
      await refreshActiveRuns();
      await load();
    } catch (e) {
      setCollectMsg(`停止失败: ${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setStoppingRunId(null);
    }
  };

  const activeTopicIds = new Set(activeRuns.map((run) => run.topic_id).filter(Boolean) as string[]);
  const runningTopicIds = new Set([...pendingCollectIds, ...activeTopicIds]);
  const toggleKeywordTopic = (topicId: string) => {
    setExpandedKeywordTopics((prev) => (
      prev.includes(topicId) ? prev.filter((id) => id !== topicId) : [...prev, topicId]
    ));
  };

  const handleToggleSchedule = async (topic: Topic) => {
    const enabling = !topic.is_scheduled;
    const cron = topic.schedule_cron || "0 8 * * *";
    try {
      await updateTopic(topic.id, {
        is_scheduled: enabling,
        schedule_cron: enabling ? cron : null,
      });
      setCollectMsg(enabling ? `已开启“${topic.name}”定期采集（${humanizeCron(cron)}）。` : `已关闭“${topic.name}”定期采集。`);
      await load();
    } catch (e) {
      setCollectMsg(`定期采集设置失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
  };

  if (loading) return <div className="loading">加载主题...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>采集主题</h2>
          <p className="text-muted">主题定义采集的关键词、信息源和自动标签规则</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> 新建主题
        </button>
      </div>

      {collectMsg && (
        <div className="toast" onClick={() => setCollectMsg(null)}>
          {collectMsg}
        </div>
      )}

      {activeRuns.length > 0 && (
        <div className="history-active-section" style={{ marginBottom: 16 }}>
          <h3><span className="pulse-dot" /> 正在执行采集 ({activeRuns.length})</h3>
          {activeRuns.map((run) => (
            <div key={run.id} className="active-run-card">
              <div className="run-info">
                <h4>{run.topic_name || run.topic_id || run.source_name || run.source_id}</h4>
                <p>{run.source_name || run.source_id} · 新增 {run.items_new} 条 · 已运行 {run.duration_seconds ?? 0} 秒</p>
              </div>
              <div className="run-status">
                <span className="chip chip--blue">{run.status}</span>
                <button
                  type="button"
                  className="btn btn-sm btn-danger"
                  onClick={() => void handleStopRun(run)}
                  disabled={stoppingRunId === run.id}
                  style={{ marginLeft: 8 }}
                >
                  <Square size={12} />
                  {stoppingRunId === run.id ? "停止中..." : "停止"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card-list">
        {topics.map((t) => {
          const keywords = t.keywords ?? [];
          const keywordExpanded = expandedKeywordTopics.includes(t.id);
          const visibleKeywords = keywordExpanded ? keywords : keywords.slice(0, 12);
          const hiddenKeywordCount = Math.max(0, keywords.length - visibleKeywords.length);
          return (
          <article key={t.id} className="card-item">
            <div className="card-item-header">
              <div>
                <h4>{t.name}</h4>
                <span className="text-muted">{t.id}</span>
                {t.description && <p className="text-muted small">{t.description}</p>}
              </div>
              <div className="card-item-actions">
                <span className={`badge ${t.is_active ? "badge--green" : "badge--gray"}`}>
                  {t.is_active ? "活跃" : "停用"}
                </span>
                {t.is_scheduled && (
                  <span className="badge badge--blue">定时: {t.schedule_cron}</span>
                )}
                <button
                  type="button"
                  className={`btn btn-sm ${t.is_scheduled ? "btn-secondary" : "btn-ghost"}`}
                  onClick={() => void handleToggleSchedule(t)}
                  title={t.is_scheduled ? "关闭该主题的定期采集" : "开启该主题的定期采集"}
                >
                  <Clock size={12} />
                  {t.is_scheduled ? "关闭定期采集" : "开启定期采集"}
                </button>
              </div>
            </div>

            <div className="card-item-meta">
              <div>
                <strong>关键词:</strong>{" "}
                <span className="topic-keyword-list">
                  {visibleKeywords.map((kw) => (
                    <span key={kw} className="chip">{kw}</span>
                  ))}
                  {hiddenKeywordCount > 0 && (
                    <button type="button" className="chip chip--button" onClick={() => toggleKeywordTopic(t.id)}>
                      还有 {hiddenKeywordCount} 个
                    </button>
                  )}
                  {keywordExpanded && keywords.length > 12 && (
                    <button type="button" className="chip chip--button" onClick={() => toggleKeywordTopic(t.id)}>
                      收起
                    </button>
                  )}
                </span>
              </div>
              <div>
                <strong>信息源:</strong>{" "}
                {t.source_names?.length
                  ? t.source_names.map((nm) => (
                      <span key={nm} className="chip chip--blue">{nm}</span>
                    ))
                  : (t.source_ids?.length
                      ? t.source_ids.map((s) => (
                          <span key={s} className="chip chip--blue">{s}</span>
                        ))
                      : <span className="text-muted">所有活跃信息源</span>)}
              </div>
              {t.target_urls?.length ? (
                <div>
                  <strong><Target size={12} /> 目标URL:</strong>{" "}
                  {t.target_urls.map((u) => (
                    <span key={u} className="chip chip--green" title={u}>{u.slice(0, 50)}{u.length > 50 ? "..." : ""}</span>
                  ))}
                </div>
              ) : null}
              <div>
                <strong>自动标签规则:</strong>{" "}
                {t.auto_tag_rules?.length
                  ? t.auto_tag_rules.map((r) => (
                      <span key={r.tag} className="chip chip--pink">{r.keyword} → {r.tag}</span>
                    ))
                  : <span className="text-muted">无</span>}
              {(t as any).description_prompt && (
                <div className="text-muted small" style={{ marginTop: 4 }}>
                  <strong>描述提示:</strong> {(t as any).description_prompt}
                </div>
              )}
              </div>
              <div className="text-muted small">
                采集周期: {t.is_scheduled ? humanizeCron(t.schedule_cron) : "手动"}
                {" · "}自动报告: {t.auto_report
                  ? <span className="badge badge--green">开启</span>
                  : <span className="text-muted">关闭</span>}
              </div>
              <div className="text-muted small">
                累计采集: {t.total_items_collected} 条
                {t.last_run_at && <> · 最后运行: {formatBeijingDateTime(t.last_run_at)}</>}
              </div>
            </div>

            <div className="card-item-footer">
              <button type="button" className="btn btn-sm btn-primary" onClick={() => handleCollect(t.id)} disabled={runningTopicIds.has(t.id)}>
                <RefreshCw size={12} className={runningTopicIds.has(t.id) ? "spin" : ""} />
                {runningTopicIds.has(t.id) ? "采集中..." : "立即采集"}
              </button>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => void handlePromptCollect(t)}
                disabled={runningTopicIds.has(t.id) || !models.some((m) => m.is_active && m.is_default)}
                title={!models.some((m) => m.is_active && m.is_default) ? "请先启用一个默认AI模型" : "输入提示词，由AI生成检索式后采集"}
              >
                <BrainCircuit size={12} />
                AI提示采集
              </button>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => handleGenerateReport(t.id, t.name)}
                disabled={generating === t.id} title={models.length === 0 ? "请先在模型配置页面添加AI模型" : "生成智能分析报告"}>
                <BrainCircuit size={12} className={generating === t.id ? "spin" : ""} />
                {generating === t.id ? "生成中..." : "生成报告"}
              </button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(t)}>
                <Edit3 size={12} /> 编辑
              </button>
              <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(t.id)}>
                <Trash2 size={12} /> 删除
              </button>
            </div>
          </article>
        );})}
        {topics.length === 0 && (
          <div className="empty">暂无主题。点击"新建主题"创建第一个采集主题。</div>
        )}
      </div>

      {/* Create / Edit modal */}
      {(showCreate || editing) && (
        <TopicForm
          topic={editing}
          sources={sources}
          models={models}
          categories={categories}
          onSave={async (data) => {
            if (editing) {
              await updateTopic(editing.id, data);
            } else {
              await createTopic(data as Topic);
            }
            setShowCreate(false);
            setEditing(null);
            await load();
          }}
          onClose={() => { setShowCreate(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

// ── Topic form ───────────────────────────────────────────────────────────────

