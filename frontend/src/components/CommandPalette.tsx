import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  Search, Command, FileText, Database, Globe, BarChart3,
  Zap, ArrowRight, History as HistoryIcon, Newspaper, LayoutDashboard,
  FolderTree, Clock, Cpu, Tags, Settings, Bell,
} from "lucide-react";

type ViewId =
  | "home"
  | "dashboard"
  | "categories"
  | "topics"
  | "sources"
  | "items"
  | "tags"
  | "schedules"
  | "models"
  | "reports"
  | "history"
  | "settings"
  | "notifications";

type ActionType =
  | { kind: "navigate"; view: ViewId }
  | { kind: "noop" };

interface PaletteItem {
  id: string;
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  action: ActionType;
  recent?: boolean;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onSelectView: (view: ViewId) => void;
}

const RECENT_KEY = "traderadar_command_palette_recent";
const MAX_RECENT = 6;

function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveRecent(ids: string[]) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(ids.slice(0, MAX_RECENT)));
  } catch {}
}

function pushRecent(id: string) {
  const prev = loadRecent().filter((r) => r !== id);
  saveRecent([id, ...prev]);
}

function fuzzyScore(query: string, text: string): number {
  if (!query) return 1;
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  if (t === q) return 100;
  if (t.startsWith(q)) return 80;
  if (t.includes(q)) return 60;
  let idx = 0;
  for (const ch of q) {
    idx = t.indexOf(ch, idx);
    if (idx === -1) return 0;
    idx += 1;
  }
  return 40;
}

const VIEW_ICON: Record<ViewId, React.ReactNode> = {
  home: <Newspaper size={16} />,
  dashboard: <LayoutDashboard size={16} />,
  categories: <FolderTree size={16} />,
  topics: <BarChart3 size={16} />,
  sources: <Globe size={16} />,
  items: <Database size={16} />,
  tags: <Tags size={16} />,
  reports: <FileText size={16} />,
  history: <HistoryIcon size={16} />,
  schedules: <Clock size={16} />,
  models: <Cpu size={16} />,
  notifications: <Bell size={16} />,
  settings: <Settings size={16} />,
};

const VIEW_LABEL: Record<ViewId, string> = {
  home: "情报主页",
  dashboard: "仪表盘",
  categories: "采集类别",
  topics: "主题管理",
  sources: "信息源",
  items: "采集条目",
  tags: "标签系统",
  reports: "智能整理",
  history: "采集历史",
  schedules: "周期调度",
  models: "模型配置",
  notifications: "通知管理",
  settings: "系统配置",
};

export function CommandPalette({ open, onClose, onSelectView }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const recentIds = useMemo(() => loadRecent(), []);

  const allItems: PaletteItem[] = useMemo(() => {
    const list: PaletteItem[] = [];

    const navs: ViewId[] = [
      "home", "dashboard", "categories", "topics", "sources",
      "items", "tags", "reports", "history", "settings",
    ];
    for (const v of navs) {
      list.push({
        id: `nav-${v}`,
        title: VIEW_LABEL[v],
        subtitle: "导航",
        icon: VIEW_ICON[v],
        action: { kind: "navigate", view: v },
      });
    }

    return list;
  }, []);

  const filtered = useMemo(() => {
    if (!query.trim()) {
      const recents = recentIds
        .map((id) => allItems.find((i) => i.id === id))
        .filter(Boolean) as PaletteItem[];
      const rest = allItems.filter((i) => !recentIds.includes(i.id)).slice(0, 8);
      return [...recents.map((r) => ({ ...r, recent: true })), ...rest];
    }
    const scored = allItems
      .map((i) => ({ item: i, score: fuzzyScore(query, `${i.title} ${i.subtitle || ""}`) }))
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score);
    return scored.map((s) => s.item);
  }, [query, allItems, recentIds]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleSelect = useCallback(
    (item: PaletteItem) => {
      pushRecent(item.id);
      onClose();
      if (item.action.kind === "navigate") {
        onSelectView(item.action.view);
      }
    },
    [onClose, onSelectView]
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => (i + 1) % filtered.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => (i - 1 + filtered.length) % filtered.length);
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        handleSelect(filtered[selectedIndex]);
      }
    },
    [filtered, selectedIndex, handleSelect]
  );

  useEffect(() => {
    const el = listRef.current?.children[selectedIndex] as HTMLElement | undefined;
    if (el) {
      el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [selectedIndex]);

  if (!open) return null;

  return (
    <div className="cp-overlay" onClick={onClose}>
      <div className="cp-container" onClick={(e) => e.stopPropagation()}>
        <div className="cp-input-wrap">
          <Search size={18} style={{ color: "var(--ink-muted)", flexShrink: 0 }} />
          <input
            ref={inputRef}
            type="text"
            className="cp-input"
            placeholder="搜索页面、快捷操作…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button
            type="button"
            className="cp-kbd"
            onClick={onClose}
            title="关闭"
          >
            <Command size={12} />K
          </button>
        </div>

        <div className="cp-list" ref={listRef}>
          {filtered.length === 0 && (
            <div className="cp-empty">
              <Search size={32} style={{ color: "var(--ink-muted)", marginBottom: 8 }} />
              <span style={{ color: "var(--ink-muted)" }}>未找到匹配结果</span>
            </div>
          )}
          {filtered.map((item, idx) => {
            const active = idx === selectedIndex;
            return (
              <div
                key={item.id}
                className={`cp-item${active ? " cp-item--active" : ""}`}
                onClick={() => handleSelect(item)}
                onMouseEnter={() => setSelectedIndex(idx)}
              >
                <div className="cp-item-icon">{item.icon}</div>
                <div className="cp-item-text">
                  <div className="cp-item-title">
                    {item.title}
                    {item.recent && (
                      <span className="cp-recent-badge">
                        <HistoryIcon size={10} /> 最近
                      </span>
                    )}
                  </div>
                  {item.subtitle && (
                    <div className="cp-item-subtitle">{item.subtitle}</div>
                  )}
                </div>
                <ArrowRight
                  size={14}
                  style={{
                    color: active ? "var(--accent-light)" : "var(--ink-subtle)",
                    opacity: active ? 1 : 0,
                    transition: "var(--transition-base)",
                  }}
                />
              </div>
            );
          })}
        </div>

        <div className="cp-footer">
          <span className="cp-footer-hint">
            <kbd className="cp-footer-kbd">↑</kbd>
            <kbd className="cp-footer-kbd">↓</kbd>
            选择
          </span>
          <span className="cp-footer-hint">
            <kbd className="cp-footer-kbd">↵</kbd>
            确认
          </span>
          <span className="cp-footer-hint">
            <kbd className="cp-footer-kbd">esc</kbd>
            关闭
          </span>
        </div>
      </div>
    </div>
  );
}
