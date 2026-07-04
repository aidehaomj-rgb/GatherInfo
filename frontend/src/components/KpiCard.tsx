import { useEffect, useRef, useState } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface KpiCardProps {
  label: string;
  value: number;
  icon: LucideIcon;
  color: string;
  trend?: number | null; // percentage, null means no data
  sparklineData?: number[]; // optional mini sparkline
}

function useCountUp(target: number, duration = 1000) {
  const [display, setDisplay] = useState(0);
  const startRef = useRef<number | null>(null);
  const fromRef = useRef(0);
  const toRef = useRef(target);

  useEffect(() => {
    fromRef.current = display;
    toRef.current = target;
    startRef.current = null;
    let raf = 0;

    const step = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const progress = Math.min((ts - startRef.current) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(fromRef.current + (toRef.current - fromRef.current) * eased);
      setDisplay(current);
      if (progress < 1) {
        raf = requestAnimationFrame(step);
      }
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return display;
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 96;
  const height = 28;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  });
  const pathD = `M ${points.join(" L ")}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="kpi-card__sparkline"
      aria-hidden="true"
    >
      <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={points[points.length - 1].split(",")[0]} cy={points[points.length - 1].split(",")[1]} r={2} fill={color} />
    </svg>
  );
}

export function KpiCard({ label, value, icon: Icon, color, trend, sparklineData }: KpiCardProps) {
  const displayValue = useCountUp(value, 1000);

  const TrendIcon =
    trend == null ? null : trend > 0 ? TrendingUp : trend < 0 ? TrendingDown : Minus;
  const trendColor =
    trend == null ? undefined : trend > 0 ? "#22c55e" : trend < 0 ? "#ef4444" : "#64748b";
  const trendText = trend == null ? null : `${trend > 0 ? "+" : ""}${trend.toFixed(1)}%`;

  return (
    <article className="kpi-card" style={{ "--kpi-color": color } as React.CSSProperties}>
      <div className="kpi-card__header">
        <div className="kpi-card__icon-ring" style={{ background: `linear-gradient(135deg, ${color}33, ${color}11)` }}>
          <Icon size={18} style={{ color }} />
        </div>
        {TrendIcon && trendText && (
          <div className="kpi-card__trend" style={{ color: trendColor }}>
            <TrendIcon size={14} />
            <span>{trendText}</span>
          </div>
        )}
      </div>
      <div className="kpi-card__value" style={{ color }}>
        {displayValue.toLocaleString()}
      </div>
      <div className="kpi-card__label">{label}</div>
      {sparklineData && sparklineData.length >= 2 && (
        <div className="kpi-card__sparkline-wrap">
          <Sparkline data={sparklineData} color={color} />
        </div>
      )}
    </article>
  );
}
