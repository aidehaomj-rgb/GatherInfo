const BEIJING_TIME_ZONE = "Asia/Shanghai";

type DateValue = string | number | Date;

/**
 * Backend timestamps are stored as UTC. SQLite may return them without an
 * offset, so make that convention explicit before converting to Beijing time.
 * Date-only publication values are kept as calendar dates and are not shifted.
 */
export function parseDateValue(value: DateValue): Date {
  if (value instanceof Date) return value;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
      return new Date(`${trimmed}T00:00:00+08:00`);
    }
    if (/^\d{4}-\d{2}-\d{2}T/.test(trimmed) && !/(Z|[+-]\d{2}:?\d{2})$/i.test(trimmed)) {
      return new Date(`${trimmed}Z`);
    }
  }
  return new Date(value);
}

export function formatBeijingDateTime(
  value: DateValue,
  options: Intl.DateTimeFormatOptions = {},
): string {
  return parseDateValue(value).toLocaleString("zh-CN", {
    timeZone: BEIJING_TIME_ZONE,
    ...options,
  });
}

export function formatBeijingDate(
  value: DateValue,
  options: Intl.DateTimeFormatOptions = {},
): string {
  return parseDateValue(value).toLocaleDateString("zh-CN", {
    timeZone: BEIJING_TIME_ZONE,
    ...options,
  });
}

export function formatBeijingTime(
  value: DateValue,
  options: Intl.DateTimeFormatOptions = {},
): string {
  return parseDateValue(value).toLocaleTimeString("zh-CN", {
    timeZone: BEIJING_TIME_ZONE,
    ...options,
  });
}

export function getBeijingHour(): number {
  const hour = new Intl.DateTimeFormat("zh-CN", {
    timeZone: BEIJING_TIME_ZONE,
    hour: "2-digit",
    hour12: false,
  }).formatToParts(new Date()).find((part) => part.type === "hour")?.value;
  return Number(hour || 0);
}
