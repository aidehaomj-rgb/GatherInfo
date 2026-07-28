import { RefreshCw, Trash2, Edit3, BrainCircuit, Target } from "lucide-react";
import type { Topic } from "../types";
import { formatBeijingDateTime } from "../utils/date";

interface Props {
  topic: Topic;
  onCollect: (id: string) => void;
  onGenerateReport: (id: string, name: string) => void;
  onEdit: (topic: Topic) => void;
  onDelete: (id: string) => void;
  collecting: string | null;
  generating: string | null;
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

export function TopicCard({ topic, onCollect, onGenerateReport, onEdit, onDelete, collecting, generating }: Props) {
  return (
    <article className="card-item">
      <div className="card-item-header">
        <div>
          <h4>{topic.name}</h4>
          <span className="text-muted">{topic.id}</span>
          {topic.description && <p className="text-muted small" style={{ marginTop: 4 }}>{topic.description}</p>}
        </div>
        <div className="card-item-actions">
          <span className={`badge ${topic.is_active ? "badge--green" : "badge--gray"}`}>
            {topic.is_active ? "活跃" : "停用"}
          </span>
          {topic.is_scheduled && (
            <span className="badge badge--blue">定时: {humanizeCron(topic.schedule_cron)}</span>
          )}
        </div>
      </div>

      <div className="card-item-meta">
        <div>
          <strong>关键词:</strong>{" "}
          {(topic.keywords ?? []).map((kw) => (
            <span key={kw} className="chip">{kw}</span>
          ))}
        </div>
        <div>
          <strong>信息源:</strong>{" "}
          {topic.source_names?.length
            ? topic.source_names.map((nm) => (
                <span key={nm} className="chip chip--blue">{nm}</span>
              ))
            : (topic.source_ids?.length
                ? topic.source_ids.map((s) => (
                    <span key={s} className="chip chip--blue">{s}</span>
                  ))
                : <span className="text-muted">所有活跃信息源</span>)}
        </div>
        {topic.target_urls?.length ? (
          <div>
            <strong><Target size={12} /> 目标URL:</strong>{" "}
            {topic.target_urls.map((u) => (
              <span key={u} className="chip chip--green" title={u}>{u.slice(0, 50)}{u.length > 50 ? "..." : ""}</span>
            ))}
          </div>
        ) : null}
        <div>
          <strong>自动标签规则:</strong>{" "}
          {topic.auto_tag_rules?.length
            ? topic.auto_tag_rules.map((r) => (
                <span key={r.tag} className="chip chip--pink">{r.keyword} → {r.tag}</span>
              ))
            : <span className="text-muted">无</span>}
          {topic.description_prompt && (
            <div className="text-muted small" style={{ marginTop: 4 }}>
              <strong>描述提示:</strong> {topic.description_prompt}
            </div>
          )}
        </div>
        <div className="text-muted small">
          采集周期: {topic.is_scheduled ? humanizeCron(topic.schedule_cron) : "手动"}
          {" · "}自动报告: {topic.auto_report
            ? <span className="badge badge--green">开启</span>
            : <span className="text-muted">关闭</span>}
        </div>
        <div className="text-muted small">
          当前条目: {topic.current_item_count} 条
          {topic.last_run_at && <> · 最后运行: {formatBeijingDateTime(topic.last_run_at)}</>}
        </div>
      </div>

      <div className="card-item-footer">
        <button type="button" className="btn btn-sm btn-primary" onClick={() => onCollect(topic.id)} disabled={collecting === topic.id}>
          <RefreshCw size={12} className={collecting === topic.id ? "spin" : ""} />
          {collecting === topic.id ? "采集中..." : "立即采集"}
        </button>
        <button type="button" className="btn btn-sm btn-secondary" onClick={() => onGenerateReport(topic.id, topic.name)}
          disabled={generating === topic.id}>
          <BrainCircuit size={12} className={generating === topic.id ? "spin" : ""} />
          {generating === topic.id ? "生成中..." : "生成报告"}
        </button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => onEdit(topic)}>
          <Edit3 size={12} /> 编辑
        </button>
        <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(topic.id)}>
          <Trash2 size={12} /> 删除
        </button>
      </div>
    </article>
  );
}
