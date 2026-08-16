import { useEffect, useState, useCallback } from "react";
import { Plus, RefreshCw, Trash2, Edit3, BrainCircuit, Clock } from "lucide-react";
import { fetchTopics, createTopic, deleteTopic, updateTopic, collectTopic, generateReport, fetchModels, fetchSources, fetchPromptTemplates } from "../api";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import type { Topic, CollectResult, ModelConfig, Source, PromptTemplate } from "../types";
import { TopicForm } from "./TopicForm";
import { formatBeijingDateTime } from "../utils/date";

const WEEKLY_ENFORCEMENT_RESEARCH_PROMPT =
  "请检索近一周境外海关、边境执法、港口监管、警察、检察或司法机关，以及可靠区域媒体公开发布的进出口执法案例，形成类似360执法信息周报的线索来源。纳入三类信息：一是香港、台湾、澳门海关或执法机关查获的具体案件，不要求另行证明中国大陆关联；二是其他国家和地区发布的涉中国大陆案件，重点核验中国产、中国籍、中国企业、中国目的地、经中国转运等关联；三是各国境外执法机关查获的重大跨境案件，包括枪支、弹药、爆炸物、武器、暴力犯罪、毒品、野生动物、濒危物种、烟草、假冒侵权和其他违禁品，这类案件可以不涉中国。重点关注走私、查获、扣押、没收、逮捕、调查、起诉、处罚等具体执法行为。使用英语、西班牙语、葡萄牙语，并适当补充法语、阿拉伯语、印尼语、泰语、日语、韩语等检索式。候选信息由大模型自动审核，必须核验原文日期、具体执法行为、来源可信度和纳入依据；不确定或无法核验的信息不得正式入库。排除中国大陆执法案件、普通政策解读、无执法动作或纯转载内容。";

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
  const [collectMsg, setCollectMsg] = useState<string | null>(null);
  const [generating, setGenerating] = useState<string | null>(null);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);
  const [aiPromptTopic, setAiPromptTopic] = useState<Topic | null>(null);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiPromptModelId, setAiPromptModelId] = useState("");
  const [savingAiPrompt, setSavingAiPrompt] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, ms, srcs, prompts] = await Promise.all([
        fetchTopics(),
        fetchModels().catch(() => []),
        fetchSources().catch(() => []),
        fetchPromptTemplates().catch(() => []),
      ]);
      setTopics(t);
      setModels(ms);
      setSources(srcs);
      setPromptTemplates(prompts);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

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

  const handleCollect = async (id: string, researchPrompt?: string, researchModelId?: string) => {
    setCollecting(id);
    setCollectMsg(null);
    try {
      setCollectMsg(researchPrompt
        ? "AI 正在生成检索式并启动采集，页面会自动刷新运行状态。"
        : "采集任务已启动，页面会自动刷新运行状态。");
      const results: CollectResult[] = await collectTopic(id, { researchPrompt, researchModelId });
      const total = results.reduce((s, r) => s + r.items_new, 0);
      const fails = results.filter((r) => r.errors?.length).length;
      setCollectMsg(`采集完成: ${total} 条新增${fails > 0 ? `, ${fails} 源失败` : ""}。详细进度和历史请在“任务查看”中查看。`);
      await load();
      window.dispatchEvent(new Event("dashboard-refresh"));
      // 通知情报主页刷新今日/本周采集数与最新条目
      window.dispatchEvent(new CustomEvent("collection-data-updated"));
      window.dispatchEvent(new CustomEvent("collection-finished"));
    } catch (e) {
      setCollectMsg(`采集失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setCollecting(null);
  };

  const openPromptCollect = (topic: Topic) => {
    const defaultPrompt = topic.id === "weekly-enforcement-intelligence"
      ? ((topic as any).description_prompt || WEEKLY_ENFORCEMENT_RESEARCH_PROMPT)
      : ((topic as any).description_prompt || "围绕本主题检索最近一周高价值公开信息，优先官方公告、监管动态、可靠新闻和行业报告。");
    setAiPromptTopic(topic);
    setAiPrompt(defaultPrompt);
    setAiPromptModelId(topic.ai_research_model_id || topic.collection_model_ids?.[0] || models.find((model) => model.is_default)?.id || "");
  };

  const saveAndCollectAiPrompt = async () => {
    if (!aiPromptTopic || !aiPrompt.trim()) return;
    setSavingAiPrompt(true);
    try {
      await updateTopic(aiPromptTopic.id, {
        description_prompt: aiPrompt.trim(),
        ai_research_model_id: aiPromptModelId || null,
      });
      setAiPromptTopic(null);
      await handleCollect(aiPromptTopic.id, aiPrompt.trim(), aiPromptModelId || undefined);
    } catch (e) {
      setCollectMsg(`保存 AI 采集策略失败: ${e instanceof Error ? e.message : "未知错误"}`);
    }
    setSavingAiPrompt(false);
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

  const runningTopicIds = new Set(collecting ? [collecting] : []);
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

      <div className="topic-card-grid">
        {topics.map((t) => {
          const keywords = t.keywords ?? [];
          const visibleKeywords = keywords.slice(0, 4);
          const hiddenKeywordCount = Math.max(0, keywords.length - visibleKeywords.length);
          return (
          <article key={t.id} className="card-item topic-card">
            <div className="card-item-header topic-card__header">
              <div className="topic-card__title">
                <h4 title={t.name}>{t.name}</h4>
                <span className={`badge ${t.is_active ? "badge--green" : "badge--gray"}`}>
                  {t.is_active ? "活跃" : "停用"}
                </span>
              </div>
              <div className="card-item-actions topic-card__schedule">
                <button
                  type="button"
                  className={`btn btn-sm ${t.is_scheduled ? "btn-secondary" : "btn-ghost"}`}
                  onClick={() => void handleToggleSchedule(t)}
                  title={t.is_scheduled
                    ? `关闭定期采集（${humanizeCron(t.schedule_cron)}）`
                    : "开启该主题的定期采集"}
                >
                  <Clock size={12} />
                  {t.is_scheduled ? humanizeCron(t.schedule_cron) : "开启定期"}
                </button>
              </div>
            </div>

            <div className="card-item-meta topic-card__meta">
              <div className="topic-card__keywords">
                <strong>关键词:</strong>{" "}
                <span className="topic-keyword-list">
                  {visibleKeywords.map((kw, index) => (
                    <span key={`${kw}-${index}`} className="chip topic-keyword-chip" title={kw}>{kw}</span>
                  ))}
                  {hiddenKeywordCount > 0 && (
                    <span className="chip topic-keyword-more" title={keywords.slice(visibleKeywords.length).join("、")}>+{hiddenKeywordCount}</span>
                  )}
                  {keywords.length === 0 && <span className="text-muted small">无</span>}
                </span>
              </div>
              <div className="text-muted small topic-card__facts">
                采集窗口: {t.collect_window_days} 天 · {t.is_scheduled ? humanizeCron(t.schedule_cron) : "手动"}
                {" · "}自动报告: {t.auto_report
                  ? <span className="badge badge--green">开启</span>
                  : <span className="text-muted">关闭</span>}
              </div>
              <div className="text-muted small topic-card__facts">
                当前条目: {t.current_item_count} 条
                {t.last_run_at && <> · 最后运行: {formatBeijingDateTime(t.last_run_at)}</>}
              </div>
            </div>

            <div className="card-item-footer topic-card__footer">
              <button type="button" className="btn btn-sm btn-primary" onClick={() => handleCollect(t.id)} disabled={runningTopicIds.has(t.id)}>
                <RefreshCw size={12} className={runningTopicIds.has(t.id) ? "spin" : ""} />
                {runningTopicIds.has(t.id) ? "采集中..." : "立即采集"}
              </button>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => openPromptCollect(t)}
                disabled={runningTopicIds.has(t.id) || !models.some((m) => m.is_active && m.is_configured)}
                title={!models.some((m) => m.is_active && m.is_configured) ? "请先在模型配置中启用一个有效模型" : "保存主题的 AI 提示词并启动采集"}
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
          promptTemplates={promptTemplates}
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
      {aiPromptTopic && (
        <AiPromptCollectDialog
          topic={aiPromptTopic}
          prompt={aiPrompt}
          modelId={aiPromptModelId}
          models={models.filter((model) => model.is_active && model.is_configured)}
          saving={savingAiPrompt}
          onPromptChange={setAiPrompt}
          onModelChange={setAiPromptModelId}
          onClose={() => setAiPromptTopic(null)}
          onSubmit={() => void saveAndCollectAiPrompt()}
        />
      )}
      {confirmDelete && (
        <ConfirmDialog
          open={true}
          title="删除主题"
          message={confirmDelete.message}
          variant="danger"
          confirmLabel="删除"
          cancelLabel="取消"
          onConfirm={() => void executeDelete()}
          onClose={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

function AiPromptCollectDialog({
  topic,
  prompt,
  modelId,
  models,
  saving,
  onPromptChange,
  onModelChange,
  onClose,
  onSubmit,
}: {
  topic: Topic;
  prompt: string;
  modelId: string;
  models: ModelConfig[];
  saving: boolean;
  onPromptChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <section className="modal modal--config ai-prompt-modal" role="dialog" aria-modal="true" aria-labelledby="ai-prompt-title" onClick={(event) => event.stopPropagation()}>
        <header className="modal-header-with-actions">
          <div>
            <h3 id="ai-prompt-title">AI 提示采集</h3>
            <p className="text-muted small">{topic.name} · 提示词会保存为本主题的长期采集要求。</p>
          </div>
        </header>
        <div className="ai-prompt-form">
          <label>
            采集提示词
            <textarea rows={12} value={prompt} onChange={(event) => onPromptChange(event.target.value)} placeholder="说明信息范围、地区、时间窗口、重点风险、排除条件和优先来源" autoFocus />
          </label>
          <label>
            AI 采集模型
            <select value={modelId} onChange={(event) => onModelChange(event.target.value)}>
              <option value="">使用主题采集模型或默认模型</option>
              {models.map((model) => <option key={model.id} value={model.id}>{model.name} · {model.model_name}</option>)}
            </select>
          </label>
          <p className="text-muted small">主题关联“AI 提示采集”信息源后，手动采集和定时采集都会加载这份提示词；模型凭据继续使用模型配置中的已有设置。</p>
        </div>
        <footer className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={onSubmit} disabled={saving || !prompt.trim()}>
            <BrainCircuit size={16} /> {saving ? "保存中..." : "保存并启动采集"}
          </button>
        </footer>
      </section>
    </div>
  );
}

// ── Topic form ───────────────────────────────────────────────────────────────
