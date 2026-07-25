import { useMemo } from "react";

interface AppLogoProps {
  size?: number;
  className?: string;
}

/**
 * TradeRadar Logo — 雷达信号波概念
 * 纯 SVG + CSS 动画，无需外部资源
 * 三层信号波纹扩散 + 扫描线旋转 + 中心脉冲发光
 */
export function AppLogo({ size = 40, className = "" }: AppLogoProps) {
  const s = useMemo(() => {
    const scale = size / 40;
    return {
      scale,
      cx: 20 * scale,
      cy: 20 * scale,
      rOuter: 16 * scale,
      rMid: 11 * scale,
      rInner: 6 * scale,
      rCenter: 3 * scale,
      rGlow: 3 * scale,
      strokeOuter: 1.5 * scale,
      strokeMid: 1.5 * scale,
      strokeInner: 1.5 * scale,
      strokeScan: 2 * scale,
      scanLen: 16 * scale,
    };
  }, [size]);

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ display: "block" }}
    >
      <defs>
        {/* 扫描线发光渐变 */}
        <linearGradient id="scanGlow" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0.2" />
        </linearGradient>
        {/* 中心点发光渐变 */}
        <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#22c55e" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* 外环信号波 — 扩散动画 */}
      <circle
        cx={s.cx}
        cy={s.cy}
        r={s.rOuter}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={s.strokeOuter}
        opacity="0.25"
      >
        <animate
          attributeName="r"
          values={`${s.rOuter * 0.85};${s.rOuter};${s.rOuter * 0.85}`}
          dur="3s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="opacity"
          values="0.35;0.15;0.35"
          dur="3s"
          repeatCount="indefinite"
        />
      </circle>

      {/* 中环信号波 — 延迟扩散 */}
      <circle
        cx={s.cx}
        cy={s.cy}
        r={s.rMid}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={s.strokeMid}
        opacity="0.45"
      >
        <animate
          attributeName="r"
          values={`${s.rMid * 0.82};${s.rMid};${s.rMid * 0.82}`}
          dur="3s"
          begin="0.6s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="opacity"
          values="0.55;0.25;0.55"
          dur="3s"
          begin="0.6s"
          repeatCount="indefinite"
        />
      </circle>

      {/* 内环信号波 */}
      <circle
        cx={s.cx}
        cy={s.cy}
        r={s.rInner}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={s.strokeInner}
        opacity="0.65"
      >
        <animate
          attributeName="r"
          values={`${s.rInner * 0.78};${s.rInner};${s.rInner * 0.78}`}
          dur="3s"
          begin="1.2s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="opacity"
          values="0.75;0.45;0.75"
          dur="3s"
          begin="1.2s"
          repeatCount="indefinite"
        />
      </circle>

      {/* 扫描线 — 旋转动画 */}
      <line
        x1={s.cx}
        y1={s.cy}
        x2={s.cx}
        y2={s.cy - s.scanLen}
        stroke="url(#scanGlow)"
        strokeWidth={s.strokeScan}
        strokeLinecap="round"
        opacity="0.85"
      >
        <animateTransform
          attributeName="transform"
          type="rotate"
          from={`0 ${s.cx} ${s.cy}`}
          to={`360 ${s.cx} ${s.cy}`}
          dur="4s"
          repeatCount="indefinite"
        />
      </line>

      {/* 扫描线尾部拖影 */}
      <line
        x1={s.cx}
        y1={s.cy}
        x2={s.cx}
        y2={s.cy - s.scanLen * 0.6}
        stroke="#22c55e"
        strokeWidth={s.strokeScan * 0.6}
        strokeLinecap="round"
        opacity="0.3"
      >
        <animateTransform
          attributeName="transform"
          type="rotate"
          from={`0 ${s.cx} ${s.cy}`}
          to={`360 ${s.cx} ${s.cy}`}
          dur="4s"
          repeatCount="indefinite"
        />
      </line>

      {/* 中心点 — 实心 */}
      <circle cx={s.cx} cy={s.cy} r={s.rCenter} fill="#22c55e" opacity="0.95">
        <animate
          attributeName="r"
          values={`${s.rCenter};${s.rCenter * 1.3};${s.rCenter}`}
          dur="2s"
          repeatCount="indefinite"
        />
      </circle>

      {/* 中心发光 — 脉冲 */}
      <circle cx={s.cx} cy={s.cy} r={s.rGlow} fill="url(#centerGlow)">
        <animate
          attributeName="r"
          values={`${s.rGlow};${s.rGlow * 2.5};${s.rGlow}`}
          dur="2s"
          repeatCount="indefinite"
        />
        <animate
          attributeName="opacity"
          values="0.5;0;0.5"
          dur="2s"
          repeatCount="indefinite"
        />
      </circle>
    </svg>
  );
}
