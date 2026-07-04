import { Activity, CheckCircle, AlertCircle, XCircle } from "lucide-react";
import type { Source } from "../types";

interface SystemStatusProps {
  sources: Source[];
}

export function SystemStatus({ sources }: SystemStatusProps) {
  const total = sources.length;
  const active = sources.filter((s) => s.is_active && s.is_configured).length;
  const warning = sources.filter((s) => s.is_active && s.last_error).length;
  const inactive = sources.filter((s) => !s.is_active).length;

  const items = [
    {
      label: "正常运行",
      count: active,
      color: "#22c55e",
      glow: "var(--green-glow)",
      icon: CheckCircle,
    },
    {
      label: "异常警告",
      count: warning,
      color: "#f59e0b",
      glow: "var(--amber-soft)",
      icon: AlertCircle,
    },
    {
      label: "已停用",
      count: inactive,
      color: "#ef4444",
      glow: "var(--red-soft)",
      icon: XCircle,
    },
    {
      label: "总计",
      count: total,
      color: "#3b82f6",
      glow: "var(--accent-glow)",
      icon: Activity,
    },
  ];

  return (
    <section className="system-status">
      <h3 className="system-status__title">
        <Activity size={16} style={{ color: "var(--accent)" }} />
        采集器健康状态
      </h3>
      <div className="system-status__grid">
        {items.map((item) => (
          <div
            key={item.label}
            className="system-status__item"
            style={{ "--status-color": item.color, "--status-glow": item.glow } as React.CSSProperties}
          >
            <div className="system-status__dot" style={{ background: item.color, boxShadow: `0 0 8px ${item.color}` }} />
            <item.icon size={16} style={{ color: item.color }} />
            <div className="system-status__info">
              <div className="system-status__count" style={{ color: item.color }}>
                {item.count}
              </div>
              <div className="system-status__label">{item.label}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
