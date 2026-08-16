import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Bell, Plus, Trash2, Send, ToggleLeft, ToggleRight, RefreshCw, Edit3,
  ChevronRight, Webhook, Mail,
} from "lucide-react";
import {
  fetchNotifications, createNotification, updateNotification,
  deleteNotification, testNotification, pruneNotifications,
  fetchNotificationHistory, deleteNotificationHistory,
} from "../api";
import type { NotificationConfig, NotificationBatch } from "../types";
import { formatBeijingDateTime } from "../utils/date";
import { Modal } from "./shared/Modal";
import { EmptyState } from "./shared/EmptyState";
import { StatusBadge } from "./shared/StatusBadge";
import { ConfirmDialog } from "./shared/ConfirmDialog";

const NEW_NOTIF: Partial<NotificationConfig> = {
  name: "",
  channel: "webhook",
  webhook_url: "",
  email_to: "",
  trigger_on_new: true,
  trigger_on_failure: false,
  is_active: true,
};

type GroupKey = `${string}-${boolean}`;

interface NotifGroup {
  key: GroupKey;
  title: string;
  channel: string;
  active: boolean;
  items: NotificationConfig[];
}

const GROUP_ORDER: { channel: string; active: boolean; title: string }[] = [
  { channel: "webhook", active: true, title: "启用的 Webhook 通知" },
  { channel: "webhook", active: false, title: "停用的 Webhook 通知" },
  { channel: "email", active: true, title: "启用的 Email 通知" },
  { channel: "email", active: false, title: "停用的 Email 通知" },
];

function isTestNotification(n: NotificationConfig): boolean {
  const name = n.name.toLowerCase();
  const webhook = (n.webhook_url ?? "").toLowerCase();
  const email = (n.email_to ?? "").toLowerCase();
  return (
    name.includes("test") ||
    name.includes("测试") ||
    webhook.includes("example.com") ||
    webhook.includes("httpbin.org") ||
    webhook.includes("localhost") ||
    email.includes("test@example.com") ||
    email.includes("localhost") ||
    email === "" ||
    webhook === ""
  );
}

function deduplicateNotifications(items: NotificationConfig[]): NotificationConfig[] {
  const seen = new Set<string>();
  const out: NotificationConfig[] = [];
  for (const n of items) {
    const key = `${n.channel}|${n.name.toLowerCase()}|${(n.webhook_url ?? "").toLowerCase()}|${(n.email_to ?? "").toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(n);
  }
  return out;
}

export function NotificationsPage() {
  const [items, setItems] = useState<NotificationConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Partial<NotificationConfig> | null>(null);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; message: string } | null>(null);
 const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [showAll, setShowAll] = useState(false);
  const [pruning, setPruning] = useState(false);
  const [viewTab, setViewTab] = useState<"configs" | "history">("configs");
  const [history, setHistory] = useState<NotificationBatch[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [confirmDeleteHistory, setConfirmDeleteHistory] = useState<string | null>(null);

  const filteredItems = useMemo(() => {
    if (showAll) return items;
    return deduplicateNotifications(items.filter((n) => !isTestNotification(n)));
  }, [items, showAll]);

  const hiddenCount = useMemo(() => items.length - filteredItems.length, [items, filteredItems]);

 const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await fetchNotifications());
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

 const groups = useMemo<NotifGroup[]>(() => {
   return GROUP_ORDER.map(({ channel, active, title }) => ({
     key: `${channel}-${active}` as GroupKey,
     title,
     channel,
     active,
      items: filteredItems.filter((it) => it.channel === channel && it.is_active === active),
   })).filter((g) => g.items.length > 0);
  }, [filteredItems]);

 const stats = useMemo(() => ({
    total: filteredItems.length,
    active: filteredItems.filter((i) => i.is_active).length,
    webhook: filteredItems.filter((i) => i.channel === "webhook").length,
    email: filteredItems.filter((i) => i.channel === "email").length,
  }), [filteredItems]);

  const openNew = () => { setEditing({ ...NEW_NOTIF }); setModalOpen(true); };
  const openEdit = (item: NotificationConfig) => { setEditing({ ...item }); setModalOpen(true); };

  const save = async () => {
    if (!editing?.name?.trim()) return;
    if (editing.channel === "webhook" && !editing.webhook_url?.trim()) return;
    if (editing.channel === "email" && !editing.email_to?.trim()) return;
    setSaving(true);
    try {
      if (editing.id) {
        await updateNotification(editing.id, editing);
      } else {
        await createNotification({
          name: editing.name!,
          channel: editing.channel!,
          webhook_url: editing.webhook_url ?? null,
          email_to: editing.email_to ?? null,
          trigger_on_new: editing.trigger_on_new ?? true,
          trigger_on_failure: editing.trigger_on_failure ?? false,
          is_active: editing.is_active ?? true,
        });
      }
      setModalOpen(false);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "保存失败");
    }
    setSaving(false);
  };

  const handleDelete = (id: string) => {
    setConfirmDelete({ id, message: "确定要删除这个通知配置吗？" });
  };

  const executeDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    try {
      await deleteNotification(id);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
    setConfirmDelete(null);
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    setTestResult(null);
    try {
      const r = await testNotification(id);
      setTestResult(r.success ? `✅ 测试成功: ${r.message}` : `❌ 测试失败: ${r.message}`);
    } catch (e) {
      setTestResult(`❌ 测试异常: ${e instanceof Error ? e.message : String(e)}`);
    }
    setTestingId(null);
  };

 const handleToggleActive = async (item: NotificationConfig) => {
   try {
     await updateNotification(item.id, { is_active: !item.is_active });
     await load();
   } catch (e) {
     alert(e instanceof Error ? e.message : "更新失败");
   }
 };

  const handlePrune = async () => {
    if (!confirm("清理通知将删除测试/无效/未激活的通知配置，确定继续？")) return;
    setPruning(true);
    try {
      const r = await pruneNotifications();
      setTestResult(`✅ 已清理 ${r.deleted} 个通知配置`);
      await load();
    } catch (e) {
      setTestResult(`❌ 清理失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setPruning(false);
    }
  };

 const toggleGroup = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      setHistory(await fetchNotificationHistory());
    } catch (e) {
      alert(e instanceof Error ? e.message : "加载历史事件失败");
    }
    setHistoryLoading(false);
  }, []);

  useEffect(() => {
    if (viewTab === "history") void loadHistory();
  }, [viewTab, loadHistory]);

  const handleDeleteHistory = async (id: string) => {
    try {
      await deleteNotificationHistory(id);
      setHistory((prev) => prev.filter((h) => h.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除历史事件失败");
    }
    setConfirmDeleteHistory(null);
  };

  if (loading) return <div className="loading">加载通知配置...</div>;
  if (error) return <div className="error-banner">{error}</div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>通知管理</h2>
          <p className="text-muted">配置采集完成后的 Webhook 或 Email 通知，按渠道与状态分类聚合。</p>
        </div>
       <div style={{ display: "flex", gap: 6 }}>
         <button type="button" className="btn btn-ghost btn-sm" onClick={load}>
           <RefreshCw size={12} />
         </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowAll((v) => !v)}>
            {showAll ? "精简视图" : "显示全部"}
          </button>
          <button type="button" className="btn btn-danger btn-sm" onClick={handlePrune} disabled={pruning}>
            <Trash2 size={12} /> {pruning ? "清理中..." : "清理测试通知"}
          </button>
          <button type="button" className="btn btn-primary btn-sm" onClick={openNew}>
            <Plus size={12} /> 新增通知
          </button>
       </div>
      </div>

      <div className="segmented-control" style={{ marginBottom: 16 }}>
        <button type="button" className={`seg-btn ${viewTab === "configs" ? "seg-btn--active" : ""}`} onClick={() => setViewTab("configs")}>
          <Bell size={12} /> 通知配置
        </button>
        <button type="button" className={`seg-btn ${viewTab === "history" ? "seg-btn--active" : ""}`} onClick={() => setViewTab("history")}>
          <RefreshCw size={12} /> 历史事件
        </button>
      </div>

      {viewTab === "configs" && (<>
      {testResult && (
        <div className={`notif-test-banner ${testResult.startsWith("✅") ? "notif-test-ok" : "notif-test-err"}`}>
          {testResult}
          <button type="button" className="btn-close-text" onClick={() => setTestResult(null)} style={{ marginLeft: 12 }}>✕</button>
        </div>
      )}

      {items.length === 0 ? (
        <EmptyState icon={<Bell size={36} style={{ opacity: 0.3 }} />} title="暂无通知配置" description="点击「新增通知」添加 Webhook 或 Email 通知规则" />
      ) : (
        <>
          <div className="notif-stats-row">
            <div className="notif-stat-card">
              <span className="notif-stat-num">{stats.total}</span>
              <span className="notif-stat-label">总计</span>
            </div>
            <div className="notif-stat-card">
              <span className="notif-stat-num" style={{ color: "var(--green)" }}>{stats.active}</span>
              <span className="notif-stat-label">启用中</span>
            </div>
            <div className="notif-stat-card">
              <span className="notif-stat-num">{stats.webhook}</span>
              <span className="notif-stat-label">Webhook</span>
            </div>
            <div className="notif-stat-card">
              <span className="notif-stat-num">{stats.email}</span>
              <span className="notif-stat-label">Email</span>
            </div>
         </div>

          {hiddenCount > 0 && (
            <div className="notif-hidden-tip" style={{ marginTop: 8, padding: "8px 12px", background: "var(--surface-elevated)", border: "1px solid var(--line)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--ink-muted)" }}>
              已隐藏 {hiddenCount} 个重复/测试/无效通知。
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setShowAll(true)} style={{ marginLeft: 8 }}>显示全部</button>
            </div>
          )}

         <div className="notif-groups">
            {groups.map((group) => (
              <NotifGroupSection
                key={group.key}
                group={group}
                collapsed={!!collapsed[group.key]}
                onToggle={() => toggleGroup(group.key)}
                testingId={testingId}
                onTest={handleTest}
                onToggleActive={handleToggleActive}
                onEdit={openEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>
        </>
      )}
      </>)}

      {viewTab === "history" && (
        <HistoryPanel
          history={history}
          loading={historyLoading}
          onRefresh={loadHistory}
          onDelete={(id) => setConfirmDeleteHistory(id)}
        />
      )}

      {modalOpen && editing && (
        <Modal open={modalOpen} title={editing.id ? "编辑通知" : "新增通知"} onClose={() => setModalOpen(false)}>
          <div className="form-group">
            <label className="form-label">名称</label>
            <input
              type="text"
              className="input"
              placeholder="例如：新情报微信通知"
              value={editing.name ?? ""}
              onChange={(e) => setEditing({ ...editing, name: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">通知渠道</label>
            <div className="segmented-control">
              <button
                type="button"
                className={`seg-btn ${editing.channel === "webhook" ? "seg-btn--active" : ""}`}
                onClick={() => setEditing({ ...editing, channel: "webhook" })}
              >Webhook</button>
              <button
                type="button"
                className={`seg-btn ${editing.channel === "email" ? "seg-btn--active" : ""}`}
                onClick={() => setEditing({ ...editing, channel: "email" })}
              >Email</button>
            </div>
          </div>
          {editing.channel === "webhook" ? (
            <div className="form-group">
              <label className="form-label">Webhook URL</label>
              <input
                type="url"
                className="input"
                placeholder="https://hooks.example.com/..."
                value={editing.webhook_url ?? ""}
                onChange={(e) => setEditing({ ...editing, webhook_url: e.target.value })}
              />
            </div>
          ) : (
            <div className="form-group">
              <label className="form-label">收件邮箱</label>
              <input
                type="email"
                className="input"
                placeholder="user@example.com"
                value={editing.email_to ?? ""}
                onChange={(e) => setEditing({ ...editing, email_to: e.target.value })}
              />
            </div>
          )}
          <div className="form-group">
            <label className="form-label">触发条件</label>
            <div style={{ display: "flex", gap: 12, flexDirection: "column", marginTop: 4 }}>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editing.trigger_on_new ?? true}
                  onChange={(e) => setEditing({ ...editing, trigger_on_new: e.target.checked })}
                />
                采集到新条目时触发
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={editing.trigger_on_failure ?? false}
                  onChange={(e) => setEditing({ ...editing, trigger_on_failure: e.target.checked })}
                />
                采集失败时触发
              </label>
            </div>
          </div>
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={editing.is_active ?? true}
                onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })}
              />
              启用此通知
            </label>
          </div>
          <div className="modal-footer-row" style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
            <button type="button" className="btn btn-ghost" onClick={() => setModalOpen(false)}>取消</button>
            <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
              {saving ? "保存中..." : "保存"}
            </button>
          </div>
        </Modal>
      )}

      <ConfirmDialog
        open={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={executeDelete}
        title="删除通知"
        message={confirmDelete?.message ?? ""}
        variant="danger"
        confirmLabel="删除"
      />

      <ConfirmDialog
        open={!!confirmDeleteHistory}
        onClose={() => setConfirmDeleteHistory(null)}
        onConfirm={() => void handleDeleteHistory(confirmDeleteHistory!)}
        title="删除历史事件"
        message="确定要删除这条历史通知事件吗？此操作不可撤销。"
        variant="danger"
        confirmLabel="删除"
      />
    </div>
  );
}

// ── History panel ────────────────────────────────────────────────────────

interface HistoryPanelProps {
  history: NotificationBatch[];
  loading: boolean;
  onRefresh: () => void;
  onDelete: (id: string) => void;
}

interface HistoryDetail {
  event?: string;
  summary?: Record<string, number>;
  sources?: { id: string; name: string; channel?: string; status: string; detail?: string }[];
  deleted?: { id: string; name: string; reason?: string }[];
}

function parseHistoryDetails(details: string | null): HistoryDetail | null {
  if (!details) return null;
  try {
    return JSON.parse(details) as HistoryDetail;
  } catch {
    return null;
  }
}

const HISTORY_STATUS_META: Record<string, { label: string; color: string }> = {
  completed: { label: "完成", color: "var(--green)" },
  partial: { label: "部分完成", color: "#f59e0b" },
  failed: { label: "异常", color: "var(--red)" },
};

function HistoryPanel({ history, loading, onRefresh, onDelete }: HistoryPanelProps) {
  if (loading) return <div className="loading">加载历史事件...</div>;

  if (history.length === 0) {
    return (
      <EmptyState
        icon={<Bell size={36} style={{ opacity: 0.3 }} />}
        title="暂无历史通知事件"
        description="采集完成、信息源健康检查等事件会自动记录到这里。"
      />
    );
  }

  return (
    <div className="notif-history">
      <div className="notif-history-toolbar">
        <span className="text-muted small">共 {history.length} 条历史事件</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onRefresh}>
          <RefreshCw size={12} /> 刷新
        </button>
      </div>
      <div className="notification-list">
        {history.map((item) => (
          <HistoryCard key={item.id} item={item} onDelete={() => onDelete(item.id)} />
        ))}
      </div>
    </div>
  );
}

function HistoryCard({ item, onDelete }: { item: NotificationBatch; onDelete: () => void }) {
  const meta = HISTORY_STATUS_META[item.status] ?? HISTORY_STATUS_META.completed;
  const detail = parseHistoryDetails(item.details);
  const isHealth = detail?.event === "source_health_check";

  return (
    <article className="notif-card">
      <div className="notif-main">
        <div className="notif-header">
          <Bell size={16} style={{ color: meta.color }} />
          <strong>{item.topic_name ?? "未知事件"}</strong>
          <StatusBadge status={item.status === "completed" ? "completed" : item.status === "partial" ? "partial" : "failed"} />
          <span className="chip chip--blue" style={{ fontSize: 11 }}>
            {isHealth ? "健康检查" : "采集完成"}
          </span>
        </div>
        <div className="notif-detail">
          {isHealth && detail?.summary ? (
            <span>
              健康 {detail.summary.healthy ?? 0} · 降级 {detail.summary.degraded ?? 0} · 失败 {detail.summary.failed ?? 0} · 不可达 {detail.summary.unreachable ?? 0}
              {(detail.deleted?.length ?? 0) > 0 && <> · 删除无价值源 {detail.deleted!.length}</>}
            </span>
          ) : (
            <span>新增 {item.total_new} 条 · 涉及 {item.source_count} 个来源</span>
          )}
        </div>
        {isHealth && detail?.deleted && detail.deleted.length > 0 && (
          <div className="notif-triggers">
            <span className="chip chip--red">已删除 {detail.deleted.length} 个不可达源</span>
          </div>
        )}
        <div className="notif-triggers">
          {item.created_at && (
            <span className="text-muted" style={{ fontSize: 11 }}>
              {formatBeijingDateTime(item.created_at)}
            </span>
          )}
        </div>
      </div>
      <div className="notif-actions">
        <button type="button" className="btn-icon btn-icon--danger" title="删除" onClick={onDelete}>
          <Trash2 size={14} />
        </button>
      </div>
    </article>
  );
}

interface GroupSectionProps {
  group: NotifGroup;
  collapsed: boolean;
  onToggle: () => void;
  testingId: string | null;
  onTest: (id: string) => void;
  onToggleActive: (item: NotificationConfig) => void;
  onEdit: (item: NotificationConfig) => void;
  onDelete: (id: string) => void;
}

function NotifGroupSection({
  group, collapsed, onToggle, testingId, onTest, onToggleActive, onEdit, onDelete,
}: GroupSectionProps) {
  const ChannelIcon = group.channel === "webhook" ? Webhook : Mail;
  const accentColor = group.active ? "var(--green)" : "var(--ink-muted)";

  return (
    <section className="notif-group">
      <button type="button" className="notif-group-header" onClick={onToggle}>
        <ChevronRight
          size={16}
          style={{ transition: "transform 0.2s ease-out", transform: collapsed ? "rotate(0deg)" : "rotate(90deg)", color: "var(--ink-muted)" }}
        />
        <ChannelIcon size={16} style={{ color: accentColor }} />
        <span className="notif-group-title">{group.title}</span>
        <span className="chip" style={{ fontSize: 11, color: "var(--ink-muted)" }}>{group.items.length}</span>
      </button>
      {!collapsed && (
        <div className="notification-list">
          {group.items.map((item) => (
            <article key={item.id} className={`notif-card ${item.is_active ? "" : "notif--inactive"}`}>
              <div className="notif-main">
                <div className="notif-header">
                  <Bell size={16} style={{ color: "var(--accent)" }} />
                  <strong>{item.name}</strong>
                  <StatusBadge status={item.is_active ? "active" : "inactive"} />
                  <span className="chip chip--blue" style={{ fontSize: 11 }}>
                    {item.channel === "webhook" ? "Webhook" : "Email"}
                  </span>
                </div>
                <div className="notif-detail">
                  {item.channel === "webhook" && item.webhook_url && (
                    <code>{item.webhook_url}</code>
                  )}
                  {item.channel === "email" && item.email_to && (
                    <span>收件人: {item.email_to}</span>
                  )}
                </div>
                <div className="notif-triggers">
                  {item.trigger_on_new && <span className="chip chip--green">新条目时触发</span>}
                  {item.trigger_on_failure && <span className="chip chip--red">失败时触发</span>}
                  {item.last_sent_at && (
                    <span className="text-muted" style={{ fontSize: 11 }}>
                      上次发送: {formatBeijingDateTime(item.last_sent_at)}
                    </span>
                  )}
                </div>
              </div>
              <div className="notif-actions">
                <button type="button" className="btn-icon" title="测试发送" onClick={() => onTest(item.id)} disabled={testingId === item.id}>
                  <Send size={14} className={testingId === item.id ? "spin" : ""} />
                </button>
                <button type="button" className="btn-icon" title={item.is_active ? "停用" : "启用"} onClick={() => onToggleActive(item)}>
                  {item.is_active ? <ToggleRight size={16} style={{ color: "var(--green)" }} /> : <ToggleLeft size={16} />}
                </button>
                <button type="button" className="btn-icon" title="编辑" onClick={() => onEdit(item)}>
                  <Edit3 size={14} />
                </button>
                <button type="button" className="btn-icon btn-icon--danger" title="删除" onClick={() => onDelete(item.id)}>
                  <Trash2 size={14} />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
