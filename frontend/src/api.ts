// GatherInfo — API client
import type {
  Source, Topic, Schedule, Tag, TagStats, Stats,
  DashboardData, CollectedItem, ItemList, NotificationConfig,
  CollectResult, ConnectorInfo, CollectRun, RunFailure,
  ItemInventory, PromptTemplate, PromptTemplateExport,
  ResearchJob,
} from "./types";

// 归一化 API 基础路径：无论 VITE_API_BASE_URL 传的是相对路径 (/api/v1)、
// 完整地址 (http://127.0.0.1:8109/api/v1)，还是漏写后缀的裸后端地址
// (http://127.0.0.1:8109)，都统一收敛到带 /api/v1 前缀的正确地址，避免 404。
function resolveApiBase(): string {
  const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (!raw) return "/api/v1";
  const normalized = raw.replace(/\/+$/, "");
  if (!normalized || normalized === "/api/v1") return "/api/v1";
  if (/^https?:\/\//i.test(normalized) && !normalized.endsWith("/api/v1")) {
    return `${normalized}/api/v1`;
  }
  return normalized;
}

const BASE = resolveApiBase();
let operatorTokenPromise: Promise<string> | null = null;

async function fetchOperatorToken(): Promise<string> {
  const response = await fetch(`${BASE}/operator-session`);
  if (!response.ok) throw new Error("无法建立本机操作会话");
  const payload = await response.json() as { token?: string };
  if (!payload.token) throw new Error("本机操作会话无效");
  return payload.token;
}

export async function operatorWriteHeaders(): Promise<Record<string, string>> {
  operatorTokenPromise ??= fetchOperatorToken().catch((error) => {
    operatorTokenPromise = null;
    throw error;
  });
  return {
    "X-Operator-Request": "RiskInfoRader",
    "X-Operator-Token": await operatorTokenPromise,
  };
}

function invalidateOperatorToken(): void {
  operatorTokenPromise = null;
}

function isOperatorTokenError(status: number, detail: string): boolean {
  return status === 403 && /operator/i.test(detail);
}

// 统一写请求执行器：token 过期（后端重启/密钥轮换）时自动重取并重试一次。
async function writeRequest(
  method: "POST" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
): Promise<Response> {
  const attempt = async (): Promise<Response> => {
    const operatorHeaders = await operatorWriteHeaders();
    return fetch(`${BASE}${path}`, {
      method,
      headers: body !== undefined
        ? { ...operatorHeaders, "Content-Type": "application/json" }
        : operatorHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let resp = await attempt();
  if (isOperatorTokenError(resp.status, await extractDetail(resp))) {
    invalidateOperatorToken();
    resp = await attempt();
  }
  return resp;
}

async function extractDetail(resp: Response): Promise<string> {
  try {
    const body = (await resp.clone().json()) as { detail?: string };
    return body.detail ?? resp.statusText;
  } catch {
    return resp.statusText;
  }
}

async function throwIfError<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const detail = await extractDetail(resp);
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

async function get<T>(
  path: string,
  params?: Record<string, string | undefined | null>,
): Promise<T> {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    }
  }
  const resp = await fetch(url);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? resp.statusText);
  }
  return resp.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const resp = await writeRequest("POST", path, body);
  return throwIfError<T>(resp);
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const resp = await writeRequest("PUT", path, body);
  return throwIfError<T>(resp);
}

async function del(path: string): Promise<void> {
  const resp = await writeRequest("DELETE", path);
  await throwIfError<unknown>(resp);
}

async function postCollection<T>(path: string, body?: unknown): Promise<T> {
  window.dispatchEvent(new CustomEvent("collection-started"));
  try {
    return await post<T>(path, body);
  } finally {
    window.dispatchEvent(new CustomEvent("collection-finished"));
  }
}

// ── Sources ─────────────────────────────────────────────────────────────

export const fetchSources = (configured?: boolean) => {
  const qs = configured !== undefined ? `?configured=${configured}` : "";
  return get<Source[]>(`/sources${qs}`);
};
export const fetchSource = (id: string) => get<Source>(`/sources/${id}`);
export const createSource = (data: Partial<Source> & { name: string; channel: string }) =>
  post<Source>("/sources", data);
export const updateSource = (id: string, data: Partial<Source>) =>
  put<Source>(`/sources/${id}`, data);
export const deleteSource = (id: string) => del(`/sources/${id}`);
export const validateSource = (id: string) =>
  post<{ source_id: string; valid: boolean; error: string | null }>(`/sources/${id}/validate`);
export const reconcileSourceReadiness = () =>
  post<{ updated: number; configured: number }>("/sources/reconcile-readiness");
export const healthCheckSources = (sourceId?: string) =>
  post<import("./types").HealthCheckReport>(
    `/sources/health-check${sourceId ? `?source_id=${sourceId}` : ""}`,
  );
export const fetchHealthSummary = () =>
  get<{ total: number; healthy: number; degraded: number; failed: number; unreachable: number; unknown: number }>(
    "/sources/health-summary",
  );
export const reviewSourceCompliance = (
  id: string,
  data: {
    decision: "approve_full" | "approve_excerpt" | "block";
    robots_evidence: "allowed" | "api_required" | "blocked";
    terms_evidence: "allowed" | "public_domain" | "government_conditions" |
      "open_government" | "us_government" | "blocked";
    discovery_urls: string[];
    legal_basis: string;
    compliance_note: string;
    reviewed_by: string;
    confirmed: boolean;
  },
) => post<Source>(`/sources/${id}/compliance-review`, data);

// ── Topics ──────────────────────────────────────────────────────────────

export const fetchTopics = () => get<Topic[]>("/topics");
export const fetchTopic = (id: string) => get<Topic>(`/topics/${id}`);
export const createTopic = (data: Partial<Topic> & { name: string }) =>
  post<Topic>("/topics", data);
export const updateTopic = (id: string, data: Partial<Topic>) =>
  put<Topic>(`/topics/${id}`, data);
export const deleteTopic = (id: string) => del(`/topics/${id}`);

// ── Multi-round research ───────────────────────────────────────────────

export const fetchResearchJobs = () => get<ResearchJob[]>("/research/jobs");
export const fetchResearchJob = (id: string) => get<ResearchJob>(`/research/jobs/${id}`);
export const createResearchJob = (data: {
  topic_id: string; objective: string; model_id?: string;
  max_rounds: number; target_items: number;
}) => post<ResearchJob>("/research/jobs", data);
export const fetchResearchItems = (id: string) =>
  get<Array<{ id: string; title: string; url: string; summary: string | null; quality_score: number | null }>>(`/research/jobs/${id}/items`);
export const resumeResearchJob = (id: string) => post<ResearchJob>(`/research/jobs/${id}/resume`);

// ── Prompt templates ───────────────────────────────────────────────────

export const fetchPromptTemplates = (kind?: "prompt" | "playbook") =>
  get<PromptTemplate[]>(kind ? `/prompt-templates?kind=${kind}` : "/prompt-templates");
export const createPromptTemplate = (data: Partial<PromptTemplate> & { name: string; content: string }) =>
  post<PromptTemplate>("/prompt-templates", data);
export const updatePromptTemplate = (id: string, data: Partial<PromptTemplate>) =>
  put<PromptTemplate>(`/prompt-templates/${id}`, data);
export const deletePromptTemplate = (id: string) => del(`/prompt-templates/${id}`);
export const exportPromptTemplates = (kind?: "prompt" | "playbook") =>
  get<PromptTemplateExport>(kind ? `/prompt-templates/export?kind=${kind}` : "/prompt-templates/export");
export const importPromptTemplates = (prompts: Partial<PromptTemplate>[]) =>
  post<{ ok: boolean; created: number; updated: number }>("/prompt-templates/import", { prompts });

// ── Categories ──────────────────────────────────────────────────────────

export const fetchCategories = () =>
  get<{ id: string; name: string; description: string | null;
    created_at: string | null; updated_at: string | null;
  }[]>("/categories");

// ── Schedules ───────────────────────────────────────────────────────────

export const fetchSchedules = () => get<Schedule[]>("/schedules");
export const createSchedule = (data: Partial<Schedule> & { id: string; name: string; cron_expression: string }) =>
  post<Schedule>("/schedules", data);
export const deleteSchedule = (id: string) => del(`/schedules/${id}`);
export const runScheduleNow = (id: string) =>
  postCollection<CollectResult[]>(`/schedules/${id}/run-now`);

// ── Collection ──────────────────────────────────────────────────────────

export const collectTopic = (
  topicId: string,
  opts: { researchPrompt?: string; researchModelId?: string } = {},
) =>
  postCollection<CollectResult[]>("/collect", {
    topic_id: topicId,
    ...(opts.researchPrompt ? { research_prompt: opts.researchPrompt } : {}),
    ...(opts.researchModelId ? { research_model_id: opts.researchModelId } : {}),
  });
export const collectSource = (sourceId: string, keywords?: string[]) =>
  postCollection<CollectResult[]>("/collect", { source_id: sourceId, keywords });

// ── Collection Batches / History ─────────────────────────────────────────

export const fetchBatches = (topicId?: string, limit = 20) =>
  get<import("./types").BatchOut[]>("/runs/batches", {
    ...(topicId ? { topic_id: topicId } : {}),
    limit: String(limit),
  } as Record<string, string>);
export const fetchActiveRuns = () => get<import("./types").ActiveRunOut[]>("/runs/active");
export const fetchRunFailures = (batchIds: string[]) =>
  get<RunFailure[]>("/runs/failures", { batch_ids: batchIds.join(",") });
export const stopRun = (runId: string) =>
  post<{ id: string; status: string; message: string }>(`/runs/${runId}/stop`);
export const stopAllRuns = () =>
  post<{ count: number; stopped: string[] }>("/runs/stop-all");

export const fetchRuns = (topicId?: string, limit = 20) =>
  get<CollectRun[]>("/runs", {
    ...(topicId ? { topic_id: topicId } : {}),
    limit: String(limit),
  });

// ── Items ───────────────────────────────────────────────────────────────

export interface ItemFilters {
  topic_id?: string;
  source_id?: string;
  category?: string;
  tag?: string;
  status?: string;
  language?: string;
  run_id?: string;
  batch_id?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export const fetchItems = (filters: ItemFilters = {}) =>
  get<ItemList>("/items", {
    ...(filters.topic_id ? { topic_id: filters.topic_id } : {}),
    ...(filters.source_id ? { source_id: filters.source_id } : {}),
    ...(filters.category ? { category: filters.category } : {}),
    ...(filters.tag ? { tag: filters.tag } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    ...(filters.language ? { language: filters.language } : {}),
    ...(filters.run_id ? { run_id: filters.run_id } : {}),
    ...(filters.batch_id ? { batch_id: filters.batch_id } : {}),
    ...(filters.q ? { q: filters.q } : {}),
    page: String(filters.page ?? 1),
    page_size: String(filters.page_size ?? 50),
  } as Record<string, string>);
export const fetchItemInventory = () => get<ItemInventory>("/items/inventory");
export const fetchFeaturedItems = () => get<CollectedItem[]>("/items/featured");

export const resolveFeaturedImages = (itemIds?: string[]) =>
  post<{ images: Record<string, string | null> }>(
    "/items/featured/resolve-images",
    { item_ids: itemIds ?? null },
  );
export const fetchItem = (id: string) => get<CollectedItem>(`/items/${id}`);
export const translateItems = (itemIds: string[]) =>
  post<{ requested: number; translated: number; items: string[]; errors?: string[] }>(
    "/items/translate",
    { item_ids: itemIds },
  );
export const reviewItemQuality = (itemIds: string[], limit = 100) =>
  post<{ reviewed: number; curated: number; deleted: number; retained: number }>(
    "/items/quality-review",
    { item_ids: itemIds, limit },
  );

export interface CurateScope {
  topic_id?: string;
  source_id?: string;
  category?: string;
  language?: string;
  q?: string;
  limit?: number;
}

export const reviewItemsInScope = (scope: CurateScope) =>
  post<{ reviewed: number; curated: number; deleted: number; retained: number }>(
    "/items/quality-review",
    {
      item_ids: [],
      limit: scope.limit ?? 100,
      topic_id: scope.topic_id || undefined,
      source_id: scope.source_id || undefined,
      category: scope.category || undefined,
      language: scope.language || undefined,
      q: scope.q || undefined,
    },
  );
export const fetchItemIds = (filters: ItemFilters) =>
  get<{ids: string[]; total: number; matching: number}>("/items/ids", {
    ...(filters.topic_id ? { topic_id: filters.topic_id } : {}),
    ...(filters.source_id ? { source_id: filters.source_id } : {}),
    ...(filters.category ? { category: filters.category } : {}),
    ...(filters.tag ? { tag: filters.tag } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    ...(filters.language ? { language: filters.language } : {}),
    ...(filters.run_id ? { run_id: filters.run_id } : {}),
    ...(filters.batch_id ? { batch_id: filters.batch_id } : {}),
    ...(filters.q ? { q: filters.q } : {}),
  } as Record<string, string>);

// ── Tags ────────────────────────────────────────────────────────────────

export const fetchTags = (namespace?: string, limit = 100) =>
  get<Tag[]>("/tags", { ...(namespace ? { namespace } : {}), limit: String(limit) });
export const fetchTagStats = () => get<TagStats[]>("/tags/stats");

// ── Stats ───────────────────────────────────────────────────────────────

export const fetchStats = () => get<Stats>("/stats");
export const fetchDashboard = () => get<DashboardData>("/stats/dashboard");
export const fetchDailyTrend = (days = 30) => get<{ date: string; count: number }[]>("/stats/items-per-day", { days: String(days) });
export const fetchStatsByCategory = () => get<{ category: string; count: number }[]>("/stats/by-category");
export const fetchStatsByLanguage = () => get<{ language: string; count: number }[]>("/stats/by-language");
export const fetchStatsBySource = () => get<{ source_id: string; count: number }[]>("/stats/by-source");

// ── Seed ────────────────────────────────────────────────────────────────

export const seedDefaults = () => post<{ sources_created: number; topics_created: number }>("/seed-defaults");

export const fetchSupplyChainInvestigations = (country = "United States") =>
  get<import("./types").SupplyChainInvestigation[]>("/supply-chain/investigations", { country });
export const createSupplyChainInvestigation = (data: { name: string; country: string; description?: string }) =>
  post<import("./types").SupplyChainInvestigation>("/supply-chain/investigations", data);
export const fetchSupplyChainDashboard = (country = "United States", investigation_id?: string) =>
  get<import("./types").SupplyChainDashboard>("/supply-chain/dashboard", { country, investigation_id });
export const fetchSupplyChainEntities = (country?: string, investigation_id?: string) =>
  get<import("./types").SupplyChainEntity[]>("/supply-chain/entities", { country, investigation_id });
export const createSupplyChainEntity = (data: Record<string, unknown>) =>
  post<import("./types").SupplyChainEntity>("/supply-chain/entities", data);
export const fetchSupplyChainCases = (country = "United States", investigation_id?: string) =>
  get<import("./types").SupplyChainCase[]>("/supply-chain/cases", { country, investigation_id });
export const createSupplyChainCase = (data: Record<string, unknown>) =>
  post<import("./types").SupplyChainCase>("/supply-chain/cases", data);
export const fetchSupplyChainShipments = (country = "United States", investigation_id?: string) =>
  get<import("./types").SupplyChainShipment[]>("/supply-chain/shipments", { country, investigation_id });
export const createSupplyChainShipment = (data: Record<string, unknown>) =>
  post<import("./types").SupplyChainShipment>("/supply-chain/shipments", data);
export const fetchSupplyChainEvidence = (country = "United States", investigation_id?: string) =>
  get<import("./types").SupplyChainEvidence[]>("/supply-chain/evidence", { country, investigation_id });
export const fetchSupplyChainOpenSourceEvidence = (country = "United States", investigation_id?: string) =>
  get<import("./types").SupplyChainOpenSourceEvidence[]>("/supply-chain/open-source-evidence", { country, investigation_id });
export const analyzeSupplyChain = (data: { case_id?: string; model_id?: string; country?: string; investigation_id?: string }) =>
  post<{ evidence_created: number; cases_scanned: number; shipments_scanned: number }>(
    "/supply-chain/analyze", data,
  );
export const discoverSupplyChains = (data: {
  countries: string[]; minimum_score: number; max_candidates: number; mcp_tools: string[]; model_id?: string; research_rounds?: number; import_record_window_days?: 90 | 180 | 365;
}) => post<import("./types").SupplyChainDiscoveryResult>("/supply-chain/experts/discover", data);
export const fetchSupplyChainCandidates = (status = "pending") =>
  get<import("./types").SupplyChainDiscovery[]>("/supply-chain/experts/candidates", { status });
export const reviewSupplyChainCandidate = (id: string, action: "approve" | "reject", note?: string) =>
  post<import("./types").SupplyChainDiscovery>(`/supply-chain/experts/candidates/${id}/review`, { action, note });
export const fetchSupplyChainReports = (country = "United States", investigation_id?: string) =>
  get<import("./types").SupplyChainReport[]>("/supply-chain/reports", { country, investigation_id });
export const generateSupplyChainReport = (data: {
  case_ids?: string[]; model_id?: string; title?: string; country?: string; investigation_id?: string;
}) => post<import("./types").SupplyChainReport>("/supply-chain/reports/generate", data);

// ── Connectors ──────────────────────────────────────────────────────────

export const fetchConnectors = () => get<ConnectorInfo[]>("/connectors");

// ── Model Config ───────────────────────────────────────────────────

export const fetchModels = () => get<import("./types").ModelConfig[]>("/models");
export const fetchModel = (id: string) => get<import("./types").ModelConfig>(`/models/${id}`);
export const createModel = (data: import("./types").ModelConfig & { id: string; name: string; provider: string; model_name: string }) =>
  post<import("./types").ModelConfig>("/models", data);
export const updateModel = (id: string, data: Partial<import("./types").ModelConfig>) =>
  put<import("./types").ModelConfig>(`/models/${id}`, data);
export const deleteModel = (id: string) => del(`/models/${id}`);
export const testModel = (id: string) =>
  post<import("./types").ModelTestResult>(`/models/${id}/test`);

// ── Reports ────────────────────────────────────────────────────────

export const fetchReports = (topicId?: string, days?: number) =>
  get<import("./types").ReportList>("/reports", {
    ...(topicId ? { topic_id: topicId } : {}),
    ...(days ? { days: String(days) } : {}),
  });
export const fetchReport = (id: string) => get<import("./types").Report>(`/reports/${id}`);
export const generateReport = (
  topicId: string,
  opts: { reportType?: "analytical" | "archive"; modelId?: string; modelNameOverride?: string; title?: string; collectionRunId?: string; collectionRunIds?: string[]; dateFrom?: string; dateTo?: string } = {},
) =>
  post<import("./types").Report>("/reports/generate", {
    topic_id: topicId,
    report_type: opts.reportType || "analytical",
    ...(opts.modelId ? { model_id: opts.modelId } : {}),
    ...(opts.modelNameOverride ? { model_name_override: opts.modelNameOverride } : {}),
    ...(opts.title ? { title: opts.title } : {}),
    ...(opts.collectionRunId ? { collection_run_id: opts.collectionRunId } : {}),
    ...(opts.collectionRunIds ? { collection_run_ids: opts.collectionRunIds } : {}),
    ...(opts.dateFrom ? { date_from: opts.dateFrom } : {}),
    ...(opts.dateTo ? { date_to: opts.dateTo } : {}),
  });
export const batchGenerateReports = (
  topicIds: string[],
  modelId?: string,
  collectionRunIds?: (string | null)[],
  modelNameOverride?: string,
  collectionRunIdsList?: string[][],
  reportType: "analytical" | "archive" = "analytical",
) =>
  post<import("./types").BatchGenerateResult>("/reports/batch-generate", {
    topic_ids: topicIds,
    report_type: reportType,
    ...(modelId ? { model_id: modelId } : {}),
    ...(modelNameOverride ? { model_name_override: modelNameOverride } : {}),
    ...(collectionRunIds ? { collection_run_ids: collectionRunIds } : {}),
    ...(collectionRunIdsList ? { collection_run_ids_list: collectionRunIdsList } : {}),
  });
export const generateWeeklyReports = (
  topicId: string,
  opts: { modelId?: string; weekStart?: string; allowPartial?: boolean } = {},
) => post<import("./types").WeeklyReportGenerateResult>("/reports/weekly-generate", {
  topic_id: topicId,
  allow_partial: opts.allowPartial ?? false,
  ...(opts.modelId ? { model_id: opts.modelId } : {}),
  ...(opts.weekStart ? { week_start: opts.weekStart } : {}),
});
export const batchDeleteItems = (itemIds: string[]) =>
  post<{deleted: number; total: number}>("/items/batch-delete", { item_ids: itemIds });

export const deleteReport = (id: string) => del(`/reports/${id}`);
export const exportReport = (id: string) =>
  post<import("./types").Report>(`/reports/${id}/export`, {});
export const downloadReportUrl = (id: string, format: string) =>
  `${BASE}/reports/${id}/download?format=${encodeURIComponent(format)}`;
export async function downloadReportFile(id: string, format: string): Promise<{ blob: Blob; filename: string }> {
  const resp = await fetch(downloadReportUrl(id, format));
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? resp.statusText);
  }
  const disposition = resp.headers.get("content-disposition") ?? "";
  const matched = disposition.match(/filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)\"?/i);
  const filename = decodeURIComponent(matched?.[1] ?? matched?.[2] ?? `report.${format}`);
  return { blob: await resp.blob(), filename };
}

// ── System settings ────────────────────────────────────────────────

export const fetchSettings = () => get<import("./types").SystemConfig>("/settings");
export const updateSettings = (data: Partial<import("./types").SystemConfig>) =>
  put<import("./types").SystemConfig>("/settings", data);

// ── Search Tools ───────────────────────────────────────────────────

export const fetchSearchTools = () => get<import("./types").SearchToolConfig[]>("/search-tools");
export const createSearchTool = (data: Partial<import("./types").SearchToolConfig> & { id: string; name: string; tool_type: string }) =>
  post<import("./types").SearchToolConfig>("/search-tools", data);
export const updateSearchTool = (id: string, data: Partial<import("./types").SearchToolConfig>) =>
  put<import("./types").SearchToolConfig>(`/search-tools/${id}`, data);
export const deleteSearchTool = (id: string) => del(`/search-tools/${id}`);
export const fetchMCPToolCatalog = () => get<import("./types").MCPToolCatalog>("/research/tools/catalog");

// ── Tag Management ────────────────────────────────────────────────────

export const updateTag = (id: string, data: Partial<import("./types").Tag>) =>
  put<import("./types").Tag>(`/tags/${id}`, data);
export const deleteTag = (id: string) => del(`/tags/${id}`);
export const mergeTags = (sourceTagId: string, targetTagId: string) =>
  post<import("./types").TagMergeResult>("/tags/merge", {
    source_tag_id: sourceTagId,
    target_tag_id: targetTagId,
  });

// ── Model available models listing ────────────────────────────────────

export const listAvailableModels = (id: string) =>
  post<import("./types").ListModelsResult>(`/models/${id}/list-models`);

export const listAvailableModelsFromConfig = (data: {
  provider: string;
  base_url: string | null;
  api_key: string | null;
  model_name?: string;
}) =>
  post<import("./types").ListModelsResult>("/models/list-available", data);

export const autoDiscoverModels = () =>
  post<import("./types").AutoDiscoverResult>("/models/auto-discover");

// ── Configuration Export / Import ────────────────────────────────────

export const exportConfig = () => get<any>("/config/export");
export const importConfig = (data: any) => post<{imported: Record<string, number>; conflicts: any[]; conflict_count: number; dry_run?: boolean}>("/config/import", data);
export const importConfigApply = (data: any, decisions: Record<string, "append" | "overwrite" | "skip">) =>
  post<{imported: Record<string, number>; conflicts: any[]; conflict_count: number}>("/config/import/apply", { ...data, decisions });

// ── FTS Search ──────────────────────────────────────────────────────

export const searchItems = (
  q: string,
  opts: { topicId?: string; sourceId?: string; page?: number; pageSize?: number } = {},
) => {
  const params: Record<string, string> = { q };
  if (opts.topicId) params.topic_id = opts.topicId;
  if (opts.sourceId) params.source_id = opts.sourceId;
  if (opts.page) params.page = String(opts.page);
  if (opts.pageSize) params.page_size = String(opts.pageSize);
  return get<import("./types").ItemList>("/items/search", params);
};

// ── Data Export ─────────────────────────────────────────────────────

export const exportItems = (
  format: "csv" | "json" | "xlsx" = "csv",
  filters: { topicId?: string; sourceId?: string; category?: string; tag?: string; language?: string; q?: string } = {},
) => {
  const params: Record<string, string> = { format };
  if (filters.topicId) params.topic_id = filters.topicId;
  if (filters.sourceId) params.source_id = filters.sourceId;
  if (filters.category) params.category = filters.category;
  if (filters.tag) params.tag = filters.tag;
  if (filters.language) params.language = filters.language;
  if (filters.q) params.q = filters.q;
  const url = new URL(`${BASE}/items/export`, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    url.searchParams.set(k, v);
  }
  return url.toString();
};

// ── Notifications ───────────────────────────────────────────────────


export const fetchNotifications = () => get<NotificationConfig[]>("/notifications");
export const createNotification = (data: Partial<NotificationConfig> & { name: string; channel: string }) =>
  post<NotificationConfig>("/notifications", data);
export const updateNotification = (id: string, data: Partial<NotificationConfig>) =>
  put<NotificationConfig>(`/notifications/${id}`, data);
export const deleteNotification = (id: string) => del(`/notifications/${id}`);
export const testNotification = (id: string) =>
  post<{ success: boolean; message: string }>("/notifications/test", { id });

export const pruneNotifications = () =>
  post<{ deleted: number }>("/notifications/prune");

export const fetchNotificationHistory = () =>
  get<import("./types").NotificationBatch[]>("/notifications/history");
export const deleteNotificationHistory = (id: string) =>
  del(`/notifications/history/${id}`);


// ── YMG-Deep integration ───────────────────────────────────────────────

export const ymgHealth = () =>
  get<import("./types").YmgHealthResponse>("/ymg-deep/health");

export const ymgAnalyze = (body: {
  topic_id?: string;
  material_set_id?: string;
  item_ids?: string[];
  collection_run_ids?: string[];
  report_id?: string;
  model_id?: string;
  ymg_depth?: string;
  ymg_mode?: string;
  extra_requirements?: string;
}) => post<import("./types").YmgAnalyzeResponse>("/ymg-deep/analyze", body);

export const haiseeHealth = () =>
  get<import("./types").HaiSeeHealthResponse>("/haisee/health");

export const pushItemsToHaiSee = (itemIds: string[]) =>
  post<import("./types").HaiSeePushResponse>("/haisee/push", { item_ids: itemIds });

export const pushReportToHaiSee = (reportId: string) =>
  post<import("./types").HaiSeePushResponse>("/haisee/push", { report_id: reportId });

export const fetchMaterialSets = (topicId?: string) =>
  get<import("./types").MaterialSet[]>("/material-sets", topicId ? { topic_id: topicId } : {});

export const archiveMaterialSet = (id: string) => del(`/material-sets/${id}`);
