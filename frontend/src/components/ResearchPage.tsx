import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Play, Search, Sparkles } from "lucide-react";

import { createResearchJob, fetchResearchItems, fetchResearchJobs, fetchTopics, resumeResearchJob } from "../api";
import type { ResearchJob, Topic } from "../types";

type ResultItem = { id: string; title: string; url: string; summary: string | null; quality_score: number | null };

export function ResearchPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [jobs, setJobs] = useState<ResearchJob[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [items, setItems] = useState<ResultItem[]>([]);
  const [topicId, setTopicId] = useState("");
  const [objective, setObjective] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selected = useMemo(() => jobs.find((job) => job.id === selectedId), [jobs, selectedId]);

  async function refresh() {
    const next = await fetchResearchJobs();
    setJobs(next);
    if (!selectedId && next[0]) setSelectedId(next[0].id);
  }

  useEffect(() => {
    Promise.all([fetchTopics(), fetchResearchJobs()]).then(([topicRows, jobRows]) => {
      setTopics(topicRows.filter((topic) => topic.is_active));
      setTopicId(topicRows.find((topic) => topic.is_active)?.id ?? "");
      setJobs(jobRows);
      setSelectedId(jobRows[0]?.id ?? "");
    }).catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    fetchResearchItems(selectedId).then(setItems).catch(() => setItems([]));
  }, [selectedId, selected?.result_count]);

  useEffect(() => {
    if (!jobs.some((job) => job.status === "pending" || job.status === "running")) return;
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [jobs, selectedId]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!topicId || objective.trim().length < 5) return;
    setBusy(true); setError("");
    try {
      const job = await createResearchJob({ topic_id: topicId, objective: objective.trim(), max_rounds: 3, target_items: 12 });
      setJobs((current) => [job, ...current]);
      setSelectedId(job.id);
      setObjective("");
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }

  async function resume() {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      const job = await resumeResearchJob(selected.id);
      setJobs((current) => current.map((row) => row.id === job.id ? job : row));
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(false); }
  }

  const metricLabels: Record<string, string> = {
    items: "案例数量", strong_china_ratio: "强涉华比例", china_ratio: "总涉华比例", non_hk_jurisdictions: "非港地区",
    entity_rate: "实体完整率", verified_rate: "双源验证率", official_rate: "官方来源率",
    translation_rate: "中文译文率",
  };

  return (
    <div className="research-page">
      <section className="research-launch">
        <div className="section-heading">
          <div><span className="section-kicker">RESEARCH AGENT</span><h2>多轮深度研究</h2></div>
          <Sparkles size={22} />
        </div>
        <form onSubmit={submit} className="research-form">
          <label>研究主题<select value={topicId} onChange={(e) => setTopicId(e.target.value)}>{topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}</select></label>
          <label className="research-form__objective">研究目标<textarea value={objective} onChange={(e) => setObjective(e.target.value)} placeholder="输入需要核实的问题、风险线索和期望输出" rows={3} /></label>
          <button className="btn-primary" disabled={busy || !topicId || objective.trim().length < 5}><Play size={16} />{busy ? "正在创建" : "开始研究"}</button>
        </form>
        {error && <div className="inline-error">{error}</div>}
      </section>

      <div className="research-layout">
        <section className="research-jobs">
          <h3>研究任务</h3>
          {jobs.length === 0 && <div className="empty-state">暂无研究任务</div>}
          {jobs.map((job) => <button key={job.id} className={`research-job${job.id === selectedId ? " is-active" : ""}`} onClick={() => setSelectedId(job.id)}>
            <span className={`research-status research-status--${job.status}`}>{job.status}</span>
            <strong>{job.objective}</strong>
            <small>第 {job.current_round}/{job.max_rounds} 轮 · {job.result_count}/{job.target_items} 条</small>
          </button>)}
        </section>

        <section className="research-results">
          <div className="section-heading"><div><span className="section-kicker">EVIDENCE</span><h3>研究证据</h3></div><Search size={20} /></div>
          {selected && <div className="research-progress"><span style={{ width: `${Math.min(100, selected.result_count / selected.target_items * 100)}%` }} /></div>}
          {selected?.acceptance_result?.metrics && <div className="acceptance-strip">
            {Object.entries(selected.acceptance_result.metrics).map(([key, value]) => <div className={selected.acceptance_result.checks?.[key] ? "is-pass" : "is-gap"} key={key}>
              <small>{metricLabels[key] || key}</small><strong>{key.includes("ratio") || key.includes("rate") ? `${Math.round(value * 100)}%` : value}</strong>
            </div>)}
          </div>}
          {selected?.status === "completed" && selected.acceptance_result?.passed === false && <div className="acceptance-action">
            <span>未达标：{selected.acceptance_result.gaps?.map((key) => metricLabels[key] || key).join("、")}</span>
            <button className="btn-primary" type="button" onClick={resume} disabled={busy}><Play size={15} />继续补采</button>
          </div>}
          {selected?.error_log && <div className="inline-error">{selected.error_log}</div>}
          {items.length === 0 && <div className="empty-state">任务结果将在每轮检索完成后显示</div>}
          {items.map((item) => <article className="research-result" key={item.id}>
            <div><strong>{item.title}</strong>{item.summary && <p>{item.summary}</p>}</div>
            <a href={item.url} target="_blank" rel="noreferrer" title="打开原文"><ExternalLink size={17} /></a>
          </article>)}
        </section>
      </div>
    </div>
  );
}
