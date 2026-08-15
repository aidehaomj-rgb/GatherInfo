import { ConfirmDialog } from "./shared/ConfirmDialog";
import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Play, Clock } from "lucide-react";
import { fetchSchedules, createSchedule, deleteSchedule, runScheduleNow, fetchTopics, fetchSources } from "../api";
import type { Schedule, Topic, Source } from "../types";
import { formatBeijingDateTime } from "../utils/date";

// ── Cron utilities ──────────────────────────────────────────────────────────

interface CronParams {
  frequency: "every_n" | "hourly" | "daily" | "weekly" | "monthly" | "custom";
  everyN?: number;
  minute?: number;
  hour?: number;
  daysOfWeek?: number[];
  daysOfMonth?: number[];
  customCron?: string;
}

function cronToHuman(cron: string): string {
  const parts = cron.split(" ");
  if (parts.length !== 5) return cron;
  const [min, hour, dom, mon, dow] = parts;
  if (min === "*" && hour === "*" && dom === "*" && dow === "*") return "每分钟";
  if (min.startsWith("*/") && hour === "*" && dow === "*") return `每${min.slice(2)}分钟`;
  if (hour === "*" && dow === "*") return `每小时${pad(min)}分`;
  const names = ["日", "一", "二", "三", "四", "五", "六"];
  if (dow !== "*") {
    const ds = dow.split(",").filter(Boolean).map((d) => names[parseInt(d)] || d);
    return `每周${ds.join("、")} ${pad(hour)}:${pad(min)}`;
  }
  if (dom !== "*") return `每月${dom}日 ${pad(hour)}:${pad(min)}`;
  return `每日 ${pad(hour)}:${pad(min)}`;
}

function pad(n: string): string {
  return n.padStart(2, "0");
}

function humanToCron(p: CronParams): string {
  const m = p.minute ?? 0; const h = p.hour ?? 8;
  switch (p.frequency) {
    case "every_n": return `*/${p.everyN || 5} * * * *`;
    case "hourly": return `${m} * * * *`;
    case "daily": return `${m} ${h} * * *`;
    case "weekly": return `${m} ${h} * * ${(p.daysOfWeek?.length ? p.daysOfWeek : [1]).join(",")}`;
    case "monthly": return `${m} ${h} ${(p.daysOfMonth?.length ? p.daysOfMonth : [1]).join(",")} * *`;
    default: return p.customCron || "0 8 * * *";
  }
}

function parseCron(cron: string): CronParams {
  const parts = cron.split(" ");
  if (parts.length !== 5) return { frequency: "custom", customCron: cron };
  const [min, hour, dom, , dow] = parts;
  if (min.startsWith("*/")) return { frequency: "every_n", everyN: parseInt(min.slice(2)) || 5 };
  if (hour === "*" && dow === "*") return { frequency: "hourly", minute: parseInt(min) || 0 };
  if (dow !== "*") return { frequency: "weekly", daysOfWeek: dow.split(",").filter(Boolean).map(Number), hour: parseInt(hour) || 8, minute: parseInt(min) || 0 };
  if (dom !== "*") return { frequency: "monthly", daysOfMonth: dom.split(",").filter(Boolean).map(Number), hour: parseInt(hour) || 8, minute: parseInt(min) || 0 };
  return { frequency: "daily", hour: parseInt(hour) || 8, minute: parseInt(min) || 0 };
}

const DAY_LABELS = ["周日","周一","周二","周三","周四","周五","周六"];

// ── Page ────────────────────────────────────────────────────────────────────

export function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{id: string; message: string} | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, t] = await Promise.all([fetchSchedules(), fetchTopics().catch(() => [])]);
      setSchedules(s);
      setTopics(t);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: `删除调度 "${id}"？` });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try { await deleteSchedule(id); setSchedules((p) => p.filter((s) => s.id !== id)); }
    catch (e) { alert(e instanceof Error ? e.message : "删除失败"); }
    setConfirmDelete(null);
  };

  const handleRunNow = async (id: string) => {
    setRunning(id);
    try {
      const results = await runScheduleNow(id);
      const total = results.reduce((s, r) => s + r.items_new, 0);
      alert(`完成: ${total} 条新增`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "执行失败");
    }
    setRunning(null);
  };

  if (loading) return <div className="loading">加载调度...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>周期调度</h2>
          <p className="text-muted">
            为采集主题设定自动定时任务。每个调度可绑定一个或多个主题。
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={14} /> 新建调度
        </button>
      </div>

      <div className="card-list">
        {schedules.map((s) => (
          <article key={s.id} className="card-item">
            <div className="card-item-header">
              <div>
                <h4>{s.name}</h4>
                <span className="text-muted">{s.id}</span>
              </div>
              <div className="card-item-actions">
                <span className={`badge ${s.is_active ? "badge--green" : "badge--gray"}`}>
                  {s.is_active ? "活跃" : "停用"}
                </span>
                <span className="chip chip--blue">{cronToHuman(s.cron_expression)}</span>
              </div>
            </div>
            <div className="card-item-meta">
              <div><strong>Cron:</strong> <code>{s.cron_expression}</code></div>
              {s.topic_ids?.length && topics.length > 0 ? (
                <div>
                  <strong>主题:</strong>{" "}
                  {s.topic_ids.map((tid) => {
                    const t = topics.find((x) => x.id === tid);
                    return <span key={tid} className="chip">{t?.name || tid} ({t?.current_item_count ?? 0}条)</span>;
                  })}
                </div>
              ) : s.topic_ids?.length ? (
                <div><strong>主题:</strong> {s.topic_ids.map((t) => <span key={t} className="chip">{t}</span>)}</div>
              ) : null}
              <div className="text-muted small">
                已运行: {s.run_count} 次
                {s.last_run_at && <> · 最后: {formatBeijingDateTime(s.last_run_at)}</>}
                {s.next_run_at && <> · 下次: {formatBeijingDateTime(s.next_run_at)}</>}
                {s.last_status && <> · 状态: {s.last_status}</>}
              </div>
            </div>
            <div className="card-item-footer">
              <button type="button" className="btn btn-sm btn-primary" onClick={() => handleRunNow(s.id)} disabled={running === s.id}>
                <Play size={12} /> {running === s.id ? "执行中..." : "立即执行"}
              </button>
              <button type="button" className="btn btn-sm btn-danger" onClick={() => handleDelete(s.id)}>
                <Trash2 size={12} /> 删除
              </button>
            </div>
          </article>
        ))}
        {schedules.length === 0 && (
          <div className="empty" style={{ padding: "60px 40px" }}>
            <Clock size={32} style={{ opacity: 0.3, margin: "0 auto 12px" }} />
            <p>暂无周期调度。</p>
            <p className="text-muted small">为采集主题设定自动定时任务，系统会按周期自动采集信息。</p>
          </div>
        )}
      </div>

      {showCreate && (
        <ScheduleForm
          topics={topics}
          onSave={async (data) => {
            await createSchedule(data);
            setShowCreate(false); await load();
          }}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  );
}

// ── Schedule Form ───────────────────────────────────────────────────────────

type ScheduleFormProps = {
  topics: Topic[];
  onSave: (data: Partial<Schedule> & { id: string; name: string; cron_expression: string }) => Promise<void>;
  onClose: () => void;
};

function ScheduleForm({ topics, onSave, onClose }: ScheduleFormProps) {
  const [saving, setSaving] = useState(false);
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  // Frequency state
  const [freq, setFreq] = useState<CronParams["frequency"]>("daily");
  const [everyN, setEveryN] = useState(30);
  const [hour, setHour] = useState(8);
  const [minute, setMinute] = useState(0);
  const [daysOfWeek, setDaysOfWeek] = useState<number[]>([1, 3, 5]);
  const [daysOfMonth, setDaysOfMonth] = useState<number[]>([1, 15]);
  const [customCron, setCustomCron] = useState("0 8 * * *");
  // Topics
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);

  const toggleDay = (d: number) => {
    setDaysOfWeek((prev) => prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort());
  };

  const currentCron = (() => {
    if (freq === "custom") return customCron;
    return humanToCron({ frequency: freq, everyN, minute, hour, daysOfWeek, daysOfMonth, customCron });
  })();

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        id, name, cron_expression: currentCron, is_active: true,
        topic_ids: selectedTopics.length > 0 ? selectedTopics : null,
      });
    } catch (e) {
      alert(e instanceof Error ? e.message : "保存失败");
    }
    setSaving(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal--config" onClick={(e) => e.stopPropagation()}>
        <h3>新建周期调度</h3>

        <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          {/* Basic info */}
          <label>ID <input value={id} onChange={(e) => setId(e.target.value)} placeholder="daily-trade" /></label>
          <label>名称 <input value={name} onChange={(e) => setName(e.target.value)} placeholder="每日贸易政策采集" /></label>

          {/* Frequency selector */}
          <label className="span-2">
            <span className="text-muted small" style={{ display: "block", marginBottom: 6, fontWeight: 600 }}>采集频率</span>
            <div className="freq-selector">
              {(["every_n","hourly","daily","weekly","monthly","custom"] as const).map((f) => (
                <button key={f} type="button" className={`freq-btn ${freq === f ? "freq-btn--active" : ""}`} onClick={() => setFreq(f)}>
                  {{ every_n: "每N分钟", hourly: "每小时", daily: "每日", weekly: "每周", monthly: "每月", custom: "自定义" }[f]}
                </button>
              ))}
            </div>
          </label>

          {/* Frequency-specific inputs */}
          {freq === "every_n" && (
            <label className="span-2">
              每 <input type="number" min={1} max={1440} value={everyN} onChange={(e) => setEveryN(parseInt(e.target.value) || 30)} style={{ width: 80, display: "inline" }} /> 分钟采集一次
            </label>
          )}

          {(freq === "daily" || freq === "weekly" || freq === "monthly") && (
            <>
              <label>
                时间
                <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                  <select value={hour} onChange={(e) => setHour(parseInt(e.target.value))} style={{ flex: 1 }}>
                    {Array.from({ length: 24 }, (_, i) => <option key={i} value={i}>{String(i).padStart(2, "0")}</option>)}
                  </select>
                  <span>:</span>
                  <select value={minute} onChange={(e) => setMinute(parseInt(e.target.value))} style={{ flex: 1 }}>
                    {Array.from({ length: 60 }, (_, i) => <option key={i} value={i}>{String(i).padStart(2, "0")}</option>)}
                  </select>
                </div>
              </label>
              <div />
            </>
          )}

          {freq === "hourly" && (
            <label>
              在第
              <select value={minute} onChange={(e) => setMinute(parseInt(e.target.value))} style={{ width: 80, display: "inline" }}>
                {Array.from({ length: 60 }, (_, i) => <option key={i} value={i}>{i}</option>)}
              </select>
              分采集
            </label>
          )}

          {freq === "weekly" && (
            <label className="span-2">
              <span className="text-muted small" style={{ display: "block", marginBottom: 4 }}>选择采集日</span>
              <div className="day-checkboxes">
                {DAY_LABELS.map((label, i) => (
                  <button
                    key={i}
                    type="button"
                    className={`day-btn ${daysOfWeek.includes(i) ? "day-btn--on" : "day-btn--off"}`}
                    onClick={() => toggleDay(i)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </label>
          )}

          {freq === "monthly" && (
            <label className="span-2">
              <span className="text-muted small" style={{ display: "block", marginBottom: 4 }}>选择日期（多选）</span>
              <div className="day-checkboxes" style={{ gap: 2 }}>
                {Array.from({ length: 31 }, (_, i) => (
                  <button
                    key={i}
                    type="button"
                    className={`day-btn ${daysOfMonth.includes(i + 1) ? "day-btn--on" : "day-btn--off"}`}
                    style={{ width: 36, height: 32, fontSize: "0.75rem" }}
                    onClick={() => setDaysOfMonth((prev) => prev.includes(i + 1) ? prev.filter((x) => x !== i + 1) : [...prev, i + 1].sort((a, b) => a - b))}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
            </label>
          )}

          {freq === "custom" && (
            <label className="span-2">
              Cron 表达式
              <input value={customCron} onChange={(e) => setCustomCron(e.target.value)} placeholder="分 时 日 月 周" />
              <span className="text-muted small">标准5字段: 分 时 日 月 周。例如 "0 8 * * *" = 每日 08:00</span>
            </label>
          )}

          {/* Cron preview */}
          <label className="span-2">
            <div className="cron-preview-box">
              <code>{currentCron}</code>
              <span className="text-muted"> = {cronToHuman(currentCron)}</span>
            </div>
          </label>

          {/* Topic selection */}
          <label className="span-2">
            <span className="text-muted small" style={{ display: "block", marginBottom: 4, fontWeight: 600 }}>绑定主题</span>
            <div className="topic-select-grid">
              {topics.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`topic-opt ${selectedTopics.includes(t.id) ? "topic-opt--on" : "topic-opt--off"}`}
                  onClick={() => setSelectedTopics((prev) => prev.includes(t.id) ? prev.filter((x) => x !== t.id) : [...prev, t.id])}
                >
                  <strong>{t.name}</strong>
                  <span className="text-muted small">{t.current_item_count} 条</span>
                </button>
              ))}
              {topics.length === 0 && <span className="text-muted small">暂无主题，请先在主题管理中创建主题。</span>}
            </div>
          </label>
        </div>

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving || !id || !name}>
            {saving ? "保存中..." : "创建调度"}
          </button>
        </div>
      </div>
    </div>
  );
}
