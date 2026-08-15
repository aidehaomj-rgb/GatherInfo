import { useEffect, useState } from "react";
import { AlignJustify, Check, Contrast, RotateCcw, Sparkles, Type } from "lucide-react";

import {
  DEFAULT_UI_PREFERENCES,
  FONT_SCALE_MAX,
  FONT_SCALE_MIN,
  FONT_SCALE_STEP,
  loadUiPreferences,
  saveUiPreferences,
  type UiDensity,
  type UiPreferences,
} from "../utils/uiPreferences";

const DENSITY_OPTIONS: { id: UiDensity; label: string; description: string }[] = [
  { id: "compact", label: "紧凑", description: "同屏展示更多内容" },
  { id: "comfortable", label: "舒适", description: "均衡的默认间距" },
  { id: "spacious", label: "宽松", description: "更大的阅读留白" },
];

const DENSITY_LABELS: Record<UiDensity, string> = {
  compact: "紧凑",
  comfortable: "舒适",
  spacious: "宽松",
};

export function AppearanceSettings() {
  const [preferences, setPreferences] = useState<UiPreferences>(loadUiPreferences);

  useEffect(() => {
    saveUiPreferences(preferences);
  }, [preferences]);

  const updatePreference = <Key extends keyof UiPreferences>(key: Key, value: UiPreferences[Key]) => {
    setPreferences((current) => ({ ...current, [key]: value }));
  };

  const resetPreferences = () => {
    setPreferences({ ...DEFAULT_UI_PREFERENCES });
  };

  return (
    <section className="appearance-settings" aria-labelledby="appearance-settings-title">
      <header className="appearance-settings__header">
        <div>
          <span>INTERFACE PREFERENCES</span>
          <h3 id="appearance-settings-title">界面与显示</h3>
          <p>调整字体、内容密度和视觉辅助效果。设置即时生效，并保存在当前设备。</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={resetPreferences}>
          <RotateCcw size={14} />恢复默认
        </button>
      </header>

      <div className="appearance-settings__grid">
        <section className="appearance-preference appearance-preference--font">
          <PreferenceHeading icon={Type} title="全局字体大小" description="同步调整导航、正文、表格和数据卡片字号。" />
          <div className="font-scale-control">
            <div className="font-scale-control__value">
              <span>当前比例</span>
              <output htmlFor="ui-font-scale">{preferences.fontScale}%</output>
            </div>
            <input
              id="ui-font-scale"
              type="range"
              min={FONT_SCALE_MIN}
              max={FONT_SCALE_MAX}
              step={FONT_SCALE_STEP}
              value={preferences.fontScale}
              onChange={(event) => updatePreference("fontScale", Number(event.target.value))}
              aria-label="全局字体大小"
            />
            <div className="font-scale-control__marks" aria-hidden="true">
              <span>较小</span><span>标准</span><span>较大</span>
            </div>
          </div>
        </section>

        <section className="appearance-preference">
          <PreferenceHeading icon={AlignJustify} title="内容密度" description="控制列表、面板和工作区的整体留白。" />
          <div className="density-options" role="group" aria-label="内容密度">
            {DENSITY_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={preferences.density === option.id ? "active" : ""}
                aria-pressed={preferences.density === option.id}
                onClick={() => updatePreference("density", option.id)}
              >
                <span>{preferences.density === option.id && <Check size={13} />}{option.label}</span>
                <small>{option.description}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="appearance-preference appearance-preference--assist">
          <PreferenceHeading icon={Sparkles} title="视觉辅助" description="根据使用环境减少动态干扰或增强文字辨识度。" />
          <div className="appearance-switches">
            <PreferenceSwitch
              icon={Sparkles}
              title="减少动态效果"
              description="停用扫描线、页面转场和图谱流动粒子。"
              checked={preferences.reduceMotion}
              onChange={(checked) => updatePreference("reduceMotion", checked)}
            />
            <PreferenceSwitch
              icon={Contrast}
              title="增强文字对比度"
              description="提高辅助文字和边界线的清晰度。"
              checked={preferences.highContrast}
              onChange={(checked) => updatePreference("highContrast", checked)}
            />
          </div>
        </section>
      </div>

      <div className="appearance-preview" aria-live="polite">
        <span>LIVE PREVIEW</span>
        <div><strong>全球贸易风险情报工作台</strong><small>字体 {preferences.fontScale}% · {DENSITY_LABELS[preferences.density]}密度 · {preferences.highContrast ? "增强对比" : "标准对比"}</small></div>
        <p>系统正在持续感知全球贸易脉搏与供应链风险变化。</p>
      </div>
    </section>
  );
}

function PreferenceHeading({ icon: Icon, title, description }: {
  icon: typeof Type;
  title: string;
  description: string;
}) {
  return (
    <header className="appearance-preference__heading">
      <span><Icon size={17} /></span>
      <div><strong>{title}</strong><p>{description}</p></div>
    </header>
  );
}

function PreferenceSwitch({ icon: Icon, title, description, checked, onChange }: {
  icon: typeof Type;
  title: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button type="button" className="appearance-switch" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}>
      <span className="appearance-switch__icon"><Icon size={16} /></span>
      <span className="appearance-switch__copy"><strong>{title}</strong><small>{description}</small></span>
      <span className={`appearance-switch__control${checked ? " active" : ""}`} aria-hidden="true"><i /></span>
    </button>
  );
}
