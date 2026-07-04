import { useEffect, useRef, useState } from "react";
import { Radar, Zap, FileText } from "lucide-react";
import type { DashboardData } from "../types";

interface HomeHeroProps {
  data: DashboardData;
  onCollect?: () => void;
  onReports?: () => void;
  reportsEnabled?: boolean;
}

function useTypewriter(text: string, speed = 60) {
  const [display, setDisplay] = useState("");
  const [done, setDone] = useState(false);
  useEffect(() => {
    let i = 0;
    setDisplay("");
    setDone(false);
    const timer = setInterval(() => {
      i += 1;
      setDisplay(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(timer);
        setDone(true);
      }
    }, speed);
    return () => clearInterval(timer);
  }, [text, speed]);
  return { display, done };
}

function AnimatedCounter({ target, duration = 1200 }: { target: number; duration?: number }) {
  const [value, setValue] = useState(0);
  const startRef = useRef<number | null>(null);
  const fromRef = useRef(0);
  const toRef = useRef(target);

  useEffect(() => {
    fromRef.current = value;
    toRef.current = target;
    startRef.current = null;
    let raf = 0;

    const step = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const progress = Math.min((ts - startRef.current) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(fromRef.current + (toRef.current - fromRef.current) * eased);
      setValue(current);
      if (progress < 1) {
        raf = requestAnimationFrame(step);
      }
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return <span>{value.toLocaleString()}</span>;
}

export function HomeHero({ data, onCollect, onReports, reportsEnabled }: HomeHeroProps) {
  const { summary } = data;
  const subtitle = "感知全球贸易脉搏，洞察政策风险先机";
  const { display: typedSubtitle, done } = useTypewriter(subtitle, 55);

  const kpis = [
    { label: "今日采集", value: summary.items_today, icon: Zap, color: "#22c55e" },
    { label: "本周新增", value: summary.items_this_week, icon: FileText, color: "#06b6d4" },
    { label: "活跃源", value: summary.active_sources, icon: Radar, color: "#f59e0b" },
  ];

  return (
    <section className="home-hero home-hero--compact">
      <div className="home-hero__grid" aria-hidden="true" />

      <div className="home-hero__content home-hero__content--compact">
        <div className="home-hero__brand-row">
        <h1 className="home-hero__title">RiskInfoRader</h1>
          <p className="home-hero__subtitle">
            {typedSubtitle}
            {!done && <span className="home-hero__cursor">|</span>}
          </p>
        </div>

        <div className="home-hero__kpis home-hero__kpis--compact">
          {kpis.map((k) => (
            <div key={k.label} className="home-hero__kpi home-hero__kpi--compact">
              <k.icon size={14} style={{ color: k.color }} />
              <div className="home-hero__kpi-value home-hero__kpi-value--compact">
                <AnimatedCounter target={k.value} />
              </div>
              <div className="home-hero__kpi-label home-hero__kpi-label--compact">{k.label}</div>
            </div>
          ))}
        </div>

        <div className="home-hero__actions home-hero__actions--compact">
          <button type="button" className="btn btn-primary btn-sm" onClick={onCollect}>
            <Zap size={14} />
            开始采集
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onReports}
            disabled={!reportsEnabled}
            title={reportsEnabled ? "查看最近一周的采集报告" : "暂无最近一周报告"}
          >
            <FileText size={14} />
            查看报告
          </button>
        </div>
        <p className="home-hero__tip" style={{ marginTop: 8, fontSize: "0.75rem", color: "var(--ink-muted)" }}>
          提示：选择主题后点击开始采集，完成后可查看最近一周报告，超过一周的报告会自动清理。
        </p>
      </div>
    </section>
  );
}
