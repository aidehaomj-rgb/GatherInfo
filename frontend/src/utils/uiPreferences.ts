export type UiDensity = "compact" | "comfortable" | "spacious";

export interface UiPreferences {
  fontScale: number;
  density: UiDensity;
  reduceMotion: boolean;
  highContrast: boolean;
}

export const FONT_SCALE_MIN = 90;
export const FONT_SCALE_MAX = 120;
export const FONT_SCALE_STEP = 5;

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  fontScale: 100,
  density: "comfortable",
  reduceMotion: false,
  highContrast: false,
};

const STORAGE_KEY = "risk-info-rader:ui-preferences:v1";

function normalizeFontScale(value: unknown) {
  const numberValue = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numberValue)) return DEFAULT_UI_PREFERENCES.fontScale;
  const steppedValue = Math.round(numberValue / FONT_SCALE_STEP) * FONT_SCALE_STEP;
  return Math.min(FONT_SCALE_MAX, Math.max(FONT_SCALE_MIN, steppedValue));
}

function normalizeDensity(value: unknown): UiDensity {
  return value === "compact" || value === "spacious" ? value : "comfortable";
}

function normalizePreferences(value: unknown): UiPreferences {
  if (!value || typeof value !== "object") return { ...DEFAULT_UI_PREFERENCES };
  const input = value as Partial<UiPreferences>;
  return {
    fontScale: normalizeFontScale(input.fontScale),
    density: normalizeDensity(input.density),
    reduceMotion: input.reduceMotion === true,
    highContrast: input.highContrast === true,
  };
}

export function loadUiPreferences(): UiPreferences {
  if (typeof window === "undefined") return { ...DEFAULT_UI_PREFERENCES };
  try {
    const storedValue = window.localStorage.getItem(STORAGE_KEY);
    return storedValue ? normalizePreferences(JSON.parse(storedValue)) : { ...DEFAULT_UI_PREFERENCES };
  } catch {
    return { ...DEFAULT_UI_PREFERENCES };
  }
}

export function applyUiPreferences(preferences: UiPreferences) {
  if (typeof document === "undefined") return;
  const normalized = normalizePreferences(preferences);
  const root = document.documentElement;
  root.style.setProperty("--ui-font-scale", String(normalized.fontScale / 100));
  root.dataset.uiDensity = normalized.density;
  root.dataset.uiMotion = normalized.reduceMotion ? "reduced" : "full";
  root.dataset.uiContrast = normalized.highContrast ? "high" : "standard";
}

export function saveUiPreferences(preferences: UiPreferences) {
  const normalized = normalizePreferences(preferences);
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    } catch {
      /* The preference still applies for the current session when storage is unavailable. */
    }
  }
  applyUiPreferences(normalized);
  return normalized;
}
