import { useEffect, useState, Suspense, lazy, useCallback } from "react";
import {
  Activity, LayoutDashboard, Globe, Tags, Database, Clock, BarChart3, Cpu, FileText, Settings, FolderTree, Bell, History, Newspaper, Keyboard, Network, FileCode2, PanelLeftClose, PanelLeftOpen,
} from "lucide-react";

import { fetchDashboard } from "./api";
import type { DashboardData } from "./types";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AppLogo } from "./components/AppLogo";
import { CommandPalette } from "./components/CommandPalette";
import { ToastProvider, useToast } from "./components/ToastProvider";
import { CollectionActivityIndicator } from "./components/CollectionActivityIndicator";
import { getBeijingHour } from "./utils/date";

// Lazy-loaded page components (code-split per view)
const DashboardPage = lazy(() => import("./components/DashboardPage").then(m => ({ default: m.DashboardPage })));
const IntelligenceHomePage = lazy(() => import("./components/IntelligenceHomePage").then(m => ({ default: m.IntelligenceHomePage })));
const TopicsPage = lazy(() => import("./components/TopicsPage").then(m => ({ default: m.TopicsPage })));
const SourcesPage = lazy(() => import("./components/SourcesPage").then(m => ({ default: m.SourcesPage })));
const ItemsPage = lazy(() => import("./components/ItemsPage").then(m => ({ default: m.ItemsPage })));
const TagsPage = lazy(() => import("./components/TagsPage").then(m => ({ default: m.TagsPage })));
const SchedulesPage = lazy(() => import("./components/SchedulesPage").then(m => ({ default: m.SchedulesPage })));
const ModelConfigPage = lazy(() => import("./components/ModelConfigPage").then(m => ({ default: m.ModelConfigPage })));
const SettingsPage = lazy(() => import("./components/SettingsPage").then(m => ({ default: m.SettingsPage })));
const HistoryPage = lazy(() => import("./components/HistoryPage").then(m => ({ default: m.HistoryPage })));
const CategoriesPage = lazy(() => import("./components/CategoriesPage").then(m => ({ default: m.CategoriesPage })));
const ReportsPage = lazy(() => import("./components/ReportsPage").then(m => ({ default: m.ReportsPage })));
const NotificationsPage = lazy(() => import("./components/NotificationsPage").then(m => ({ default: m.NotificationsPage })));
const SupplyChainPage = lazy(() => import("./components/SupplyChainPage").then(m => ({ default: m.SupplyChainPage })));
const PromptTemplatesPage = lazy(() => import("./components/PromptTemplatesPage").then(m => ({ default: m.PromptTemplatesPage })));

function PageLoader() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 0" }}>
      <div className="page-loader">
        <div className="page-loader-spinner" />
        <span style={{ color: "var(--ink-muted)", fontSize: "0.85rem" }}>加载中...</span>
      </div>
    </div>
  );
}

type ViewId = "home" | "dashboard" | "categories" | "topics" | "prompts" | "sources" | "items" | "tags" | "schedules" | "models" | "reports" | "supply-chain" | "history" | "settings" | "notifications";

interface ViewDef {
  id: ViewId;
  label: string;
  icon: typeof LayoutDashboard;
}

const views: ViewDef[] = [
  { id: "home", label: "情报主页", icon: Newspaper },
  { id: "dashboard", label: "仪表盘", icon: LayoutDashboard },
  { id: "categories", label: "采集类别", icon: FolderTree },
  { id: "topics", label: "主题管理", icon: BarChart3 },
  { id: "prompts", label: "提示词库", icon: FileCode2 },
  { id: "sources", label: "信息源", icon: Globe },
  { id: "items", label: "采集条目", icon: Database },
  { id: "tags", label: "标签系统", icon: Tags },
  { id: "reports", label: "智能报告", icon: FileText },
  { id: "supply-chain", label: "供应链穿透", icon: Network },
  { id: "models", label: "模型配置", icon: Cpu },
  { id: "schedules", label: "周期调度", icon: Clock },
  { id: "history", label: "任务查看", icon: History },
  { id: "notifications", label: "通知管理", icon: Bell },
  { id: "settings", label: "系统配置", icon: Settings },
];

function greeting(): string {
  const h = getBeijingHour();
  if (h < 6) return "夜深了";
  if (h < 12) return "上午好";
  if (h < 18) return "下午好";
  return "晚上好";
}

function ShortcutHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  const shortcuts = [
    { key: "Cmd / Ctrl + K", desc: "打开命令面板" },
    { key: "Esc", desc: "关闭模态框 / 取消选择" },
    { key: "?", desc: "显示快捷键帮助" },
    { key: "↑ / ↓", desc: "命令面板中切换选项" },
    { key: "Enter", desc: "执行选中命令" },
  ];
  return (
    <div className="shortcut-help-overlay" onClick={onClose}>
      <div className="shortcut-help" onClick={(e) => e.stopPropagation()}>
        <div className="shortcut-help__header">
          <h3>快捷键帮助</h3>
          <button type="button" className="shortcut-help__close" onClick={onClose} aria-label="关闭">
            <Keyboard size={18} />
          </button>
        </div>
        <div className="shortcut-help__list">
          {shortcuts.map((s) => (
            <div key={s.key} className="shortcut-help__row">
              <kbd className="shortcut-help__key">{s.key}</kbd>
              <span className="shortcut-help__desc">{s.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AppInner() {
  const [view, setView] = useState<ViewId>("home");
  const [dashData, setDashData] = useState<DashboardData | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [shortcutHelpOpen, setShortcutHelpOpen] = useState(false);
  const [collectionPanelOpen, setCollectionPanelOpen] = useState(false);
  const { success } = useToast();

  useEffect(() => {
    let cancelled = false;
    const refreshDashboard = () => {
      fetchDashboard().then((d) => { if (!cancelled) setDashData(d); }).catch(() => {});
    };
    refreshDashboard();
    window.addEventListener("dashboard-refresh", refreshDashboard);
    window.addEventListener("collection-data-updated", refreshDashboard);
    return () => {
      cancelled = true;
      window.removeEventListener("dashboard-refresh", refreshDashboard);
      window.removeEventListener("collection-data-updated", refreshDashboard);
    };
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev);
  }, []);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (commandOpen) {
          setCommandOpen(false);
          return;
        }
        if (shortcutHelpOpen) {
          setShortcutHelpOpen(false);
          return;
        }
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen((prev) => !prev);
        return;
      }
      if (e.key === "?" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        setShortcutHelpOpen(true);
        return;
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [commandOpen, shortcutHelpOpen]);

  useEffect(() => {
    function onResize() {
      if (window.innerWidth < 768) {
        setSidebarCollapsed(true);
      } else {
        setSidebarCollapsed(false);
      }
    }
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const itemsToday = dashData?.summary?.items_today ?? 0;
  const activeView = views.find((item) => item.id === view) || views[0];

  return (
    <div className="app-shell">
      <aside className={`side-rail${sidebarCollapsed ? " side-rail--collapsed" : ""}`}>
        <span className="side-rail__scan" aria-hidden="true" />
        <button
          type="button"
          className="sidebar-toggle"
          onClick={toggleSidebar}
          title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
          aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
          aria-pressed={sidebarCollapsed}
        >
          {sidebarCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>
        <div className="brand">
          <AppLogo size={sidebarCollapsed ? 32 : 44} />
          {!sidebarCollapsed && (
            <>
              <span className="brand-name">RiskInfoRader</span>
              <span className="brand-sub">全球贸易风险情报中枢</span>
            </>
          )}
        </div>
        <nav aria-label="系统功能导航">
          {views.map((v) => {
            const Icon = v.icon;
            const isActive = view === v.id;
            return (
              <button
                key={v.id}
                type="button"
                className={`nav-btn${isActive ? " nav-btn--active" : ""}`}
                onClick={() => setView(v.id)}
                title={v.label}
              >
                {isActive && <span className="nav-btn__indicator" />}
                <Icon size={18} />
                {!sidebarCollapsed && <span>{v.label}</span>}
              </button>
            );
          })}
        </nav>
      </aside>
      <main className={`workspace${collectionPanelOpen ? " workspace--activity-open" : ""}`}>
        <header className="workspace-header">
          <div className="header-context">
            <span className="header-context__eyebrow">GLOBAL RISK INTELLIGENCE / {activeView.label}</span>
            <div className="header-greeting">
              <strong className="header-view-title">{activeView.label}</strong>
              <span className="greeting-text">{greeting()}，今日已采集 <strong>{itemsToday.toLocaleString()}</strong> 条新情报</span>
            </div>
          </div>
          <div className="header-actions">
            <div className={`system-status${dashData ? "" : " system-status--syncing"}`} aria-live="polite">
              <span className="system-status__pulse" aria-hidden="true" />
              <Activity size={15} />
              <div>
                <small>SYSTEM STATUS</small>
                <strong>{dashData ? "数据链路在线" : "数据同步中"}</strong>
              </div>
            </div>
            <CollectionActivityIndicator open={collectionPanelOpen} onOpenChange={setCollectionPanelOpen} />
            <button
              type="button"
              className="btn-icon header-action-btn"
              title="打开命令面板 (Cmd+K)"
              aria-label="打开命令面板"
              onClick={() => setCommandOpen(true)}
            >
              <Keyboard size={18} />
            </button>
            <button
              type="button"
              className="btn-icon header-action-btn"
              title="刷新仪表盘"
              aria-label="前往仪表盘"
              onClick={() => { setView("dashboard"); }}
            >
              <LayoutDashboard size={18} />
            </button>
          </div>
        </header>
        <section className="view-frame" data-view={view}>
          <div className="view-transition" key={view}>
            <ErrorBoundary key={view}>
              <Suspense fallback={<PageLoader />}>
                {view === "home" && <IntelligenceHomePage />}
                {view === "dashboard" && <DashboardPage />}
                {view === "categories" && <CategoriesPage />}
                {view === "topics" && <TopicsPage />}
                {view === "prompts" && <PromptTemplatesPage />}
                {view === "sources" && <SourcesPage />}
                {view === "items" && <ItemsPage />}
                {view === "tags" && <TagsPage />}
                {view === "reports" && <ReportsPage />}
                {view === "supply-chain" && <SupplyChainPage />}
                {view === "models" && <ModelConfigPage />}
                {view === "history" && <HistoryPage />}
                {view === "notifications" && <NotificationsPage />}
                {view === "settings" && <SettingsPage />}
                {view === "schedules" && <SchedulesPage />}
              </Suspense>
            </ErrorBoundary>
          </div>
        </section>
      </main>
      <CommandPalette
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        onSelectView={(v) => {
          setView(v as ViewId);
          setCommandOpen(false);
          success(`已切换到: ${views.find((x) => x.id === v)?.label || v}`);
        }}
      />
      <ShortcutHelp open={shortcutHelpOpen} onClose={() => setShortcutHelpOpen(false)} />
    </div>
  );
}

export function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}
