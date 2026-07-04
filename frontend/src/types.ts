// GatherInfo — types for the collection platform
export interface Source {
  id: string;
  name: string;
  description: string | null;
  channel: string;
  is_active: boolean;
  is_configured: boolean;
  base_url: string | null;
  api_endpoint: string | null;
  homepage_url: string | null;
  api_key: string | null;
  auth_config?: Record<string, unknown> | null;
  default_keywords: string[] | null;
  default_categories: string[] | null;
  languages: string[] | null;
  country_focus: string[] | null;
  rate_limit_rps?: number;
  last_sync_at: string | null;
  last_error: string | null;
  items_collected: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface Topic {
  id: string;
  name: string;
  description: string | null;
  category_id: string | null;
  category_name: string | null;
  keywords: string[];
  keyword_tags: KeywordTag[] | null;
  description_prompt: string | null;
  synonyms: string[] | null;
  categories: string[] | null;
  focus_countries: string[] | null;
  focus_languages: string[] | null;
  source_ids: string[] | null;
  target_urls: string[] | null;
  auto_tag_rules: AutoTagRule[] | null;
  collect_window_days: number;
  schedule_cron: string | null;
  is_scheduled: boolean;
  is_active: boolean;
  is_configured: boolean;
  auto_report: boolean;
  auto_report_model_id: string | null;
  last_collection_run_id: string | null;
  source_names: string[];
  total_items_collected: number;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface KeywordTag {
  keyword: string;
  weight: number;
  tag_id?: string;
}

export interface AutoTagRule {
  keyword: string;
  tag: string;
}

export interface CollectedItem {
 id: string;
 source_id: string;
 run_id: string | null;
  topic_id: string | null;
 title: string;
  title_zh: string | null;
  content: string | null;
  content_zh: string | null;
  summary: string | null;
  summary_zh: string | null;
  url: string | null;
  language: string | null;
  translation_status: string | null;
  category: string | null;
  tags: TagRef[];
  entities: Record<string, unknown> | null;
  quality_score: number;
  relevance_score: number;
  status: string;
  collected_at: string | null;
  published_at: string | null;
}

export interface TagRef {
  id: string;
  namespace: string;
  value: string;
  label: string | null;
}

export interface Tag {
  id: string;
  namespace: string;
  value: string;
  label: string | null;
  color: string | null;
  item_count: number;
  last_seen_at: string | null;
}

export interface TagStats {
  tag_id: string;
  namespace: string;
  value: string;
  item_count: number;
  last_seen_at: string | null;
  categories: Record<string, number>;
  languages: Record<string, number>;
  sources: Record<string, number>;
}

export interface Schedule {
  id: string;
  name: string;
  description: string | null;
  source_ids: string[] | null;
  topic_ids: string[] | null;
  cron_expression: string;
  is_active: boolean;
  is_configured: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  last_status: string | null;
}

export interface Stats {
  total_sources: number;
  active_sources: number;
  total_topics: number;
  active_topics: number;
  total_items: number;
  items_today: number;
  total_tags: number;
  total_schedules: number;
  last_collection_at: string | null;
}

export interface DashboardData {
  summary: {
    total_items: number;
    items_today: number;
    items_this_week: number;
    total_sources: number;
    active_sources: number;
    total_topics: number;
    total_tags: number;
  };
  categories: { category: string; count: number }[];
  languages: { language: string; count: number }[];
  top_tags: { id: string; namespace: string; value: string; count: number }[];
  source_health: {
    id: string;
    name: string;
    is_active: boolean;
    last_sync_at: string | null;
    items_collected: number;
    last_run_status: string | null;
  }[];
  daily_trend: { date: string; count: number }[];
}

export interface CollectRun {
  id: string;
  source_id: string;
  topic_id: string | null;
  status: string;
  items_found: number;
  items_new: number;
  items_failed: number;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error_log: string[] | null;
}

export interface CollectResult {
  run: CollectRun;
  total_items: number;
  items_new: number;
  errors: string[] | null;
}

export interface ConnectorInfo {
  channel: string;
  description: string;
  default_base_url?: string | null;
  default_api_endpoint?: string | null;
  required_fields?: string[];
  optional_fields?: string[];
  homepage_hint?: string | null;
}

export interface ItemList {
  items: CollectedItem[];
  total: number;
  page: number;
  page_size: number;
}

// ── Model Configuration ────────────────────────────────────────────────

export interface ModelConfig {
  id: string;
  name: string;
  provider: string;        // ollama | openai | lmstudio | custom
  base_url: string | null;
  api_key: string | null;
  model_name: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  is_default: boolean;
  is_active: boolean;
  is_configured: boolean;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ModelTestResult {
  success: boolean;
  message: string;
  response_preview: string | null;
  duration_ms: number | null;
}

// ── Report ─────────────────────────────────────────────────────────────

export interface Report {
  id: string;
  topic_id: string;
  topic_name?: string;
  title: string;
  content: string | null;
  summary: string | null;
  status: string;           // pending | generating | completed | failed
  model_id: string | null;
  tokens_used: number;
  item_count: number;
  item_ids: string[] | null;
  error_log: string | null;
  collection_run_id: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
  output_files: Record<string, string> | null;
  output_dir: string | null;
  generated_at: string | null;
  created_at: string | null;
}

export interface ReportList {
  reports: Report[];
  total: number;
}

export interface SystemConfig {
  report_title_format: string;
  report_output_dir: string | null;
  report_dir_pattern: string;
  report_formats: string[];
}

export interface BatchGenerateResult {
  results: Report[];
  failed: number;
}

export interface TagMergeResult {
  target_tag_id: string;
  moved_items: number;
  deleted_tag_id: string;
}

export interface DiscoveredProvider {
  provider: string;
  base_url: string;
  models: string[];
  reachable: boolean;
  note: string | null;
}

export interface AutoDiscoverResult {
  providers: DiscoveredProvider[];
}

// ── Search Tool Config ─────────────────────────────────────────────────

export interface SearchToolConfig {
  id: string;
  name: string;
  tool_type: string;
  is_active: boolean;
  is_configured: boolean;
  config_json: Record<string, unknown> | null;
  api_key_ref: string | null;
  is_default: boolean;
  created_at: string | null;
  updated_at: string | null;
}

// ── List Models Result ───────────────────────────────────────────────

export interface ListModelsResult {
  success: boolean;
  message: string;
  models: string[];
  provider_type: string;
  current_model: string;
}


// ── Collection Batch / History ──────────────────────────────────────────

export interface BatchRunOut {
  id: string;
  source_id: string;
  topic_id: string | null;
  status: string;
  items_new: number;
  items_found: number;
  items_failed: number;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error_log: string[] | null;
  source_name: string | null;
}

export interface BatchOut {
  batch_id: string;
  topic_id: string | null;
  topic_name: string | null;
  batch_label: string | null;
  status: string;
  total_items: number;
  total_new: number;
  started_at: string | null;
  completed_at: string | null;
  source_count: number;
  runs: BatchRunOut[];
}

export interface ActiveRunOut {
  id: string;
  source_id: string;
  source_name: string | null;
  topic_id: string | null;
  topic_name: string | null;
  status: string;
  keywords_used: string[];
  items_found: number;
  items_new: number;
  started_at: string | null;
  duration_seconds: number | null;
  batch_id: string | null;
}

// ── Notifications ───────────────────────────────────────────────────────

export interface NotificationConfig {
  id: string;
  name: string;
  channel: string;
  webhook_url: string | null;
  email_to: string | null;
  trigger_on_new: boolean;
  trigger_on_failure: boolean;
  is_active: boolean;
  is_configured: boolean;
  last_sent_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}


// ── YMG-Deep integration ───────────────────────────────────────────────
export interface YmgEvidenceItem {
  id: string;
  title: string;
  url: string | null;
  summary: string | null;
  source: string | null;
  published_at: string | null;
  language: string | null;
}

export interface YmgAnalyzeResponse {
  analysis_topic: string;
  evidence_count: number;
  evidence_digest: string;
  evidence_items: YmgEvidenceItem[];
  ymg_session_id: string | null;
  ymg_status: string;
  ymg_message: string | null;
  ymg_base_url: string;
}

export interface YmgHealthResponse {
  reachable: boolean;
  base_url: string;
  message: string | null;
}
