"""
Model additions: ModelConfig, Report. Run at startup to migrate DB schema.
"""
from sqlalchemy import inspect, text

def migrate_schema(engine):
    """Add new columns/tables if they don't exist (safer for dev iteration)."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Add api_key column to source_configs
    if "source_configs" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("source_configs")}
        with engine.connect() as conn:
            if "api_key" not in cols:
                conn.execute(text("ALTER TABLE source_configs ADD COLUMN api_key VARCHAR(500)"))
            if "homepage_url" not in cols:
                conn.execute(text("ALTER TABLE source_configs ADD COLUMN homepage_url VARCHAR(800)"))
            if "is_configured" not in cols:
                conn.execute(text("ALTER TABLE source_configs ADD COLUMN is_configured BOOLEAN DEFAULT 0"))
                # Auto-set: web_scrape/official/rss/manual sources are always configured
                conn.execute(text("UPDATE source_configs SET is_configured = 1 WHERE channel IN ('WEB_SCRAPE','OFFICIAL','RSS','SOCIAL','DEEPWEB','MANUAL')"))
            if "verification_status" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN verification_status "
                    "VARCHAR(80) DEFAULT 'legacy_unverified'"
                ))
            if "discovery_urls" not in cols:
                conn.execute(text("ALTER TABLE source_configs ADD COLUMN discovery_urls JSON"))
            if "robots_status" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN robots_status VARCHAR(80) DEFAULT 'unverified'"
                ))
            if "terms_status" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN terms_status VARCHAR(80) DEFAULT 'unverified'"
                ))
            if "llm_ingest_allowed" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN llm_ingest_allowed BOOLEAN DEFAULT 0"
                ))
            if "origin_resolution_required" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN origin_resolution_required BOOLEAN DEFAULT 1"
                ))
            if "crawl_delay_seconds" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN crawl_delay_seconds INTEGER DEFAULT 8"
                ))
            if "verified_at" not in cols:
                conn.execute(text("ALTER TABLE source_configs ADD COLUMN verified_at TIMESTAMP"))
            if "compliance_reviewed_by" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN compliance_reviewed_by VARCHAR(200)"
                ))
            if "compliance_snapshot" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN compliance_snapshot JSON"
                ))
            if "health_status" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN health_status "
                    "VARCHAR(40) DEFAULT 'unknown'"
                ))
            if "health_checked_at" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN health_checked_at TIMESTAMP"
                ))
            if "health_detail" not in cols:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN health_detail TEXT"
                ))
            # Public URL sources imported before readiness checks were introduced
            # already have all credentials they need. Only mark them ready when
            # an actual collection address is present.
            conn.execute(text("""
                UPDATE source_configs
                SET is_configured = 1
                WHERE UPPER(channel) IN ('WEB_SCRAPE', 'OFFICIAL', 'RSS', 'SOCIAL', 'DEEPWEB')
                  AND is_configured = 0
                  AND COALESCE(base_url, api_endpoint, homepage_url, '') != ''
            """))
            conn.commit()

    # Add columns to `topics` table if it exists
    if "topics" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("topics")}
        with engine.connect() as conn:
            if "keyword_tags" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN keyword_tags JSON"))
            if "description_prompt" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN description_prompt TEXT"))
            if "ai_research_model_id" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN ai_research_model_id VARCHAR(80)"))
            if "auto_report" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN auto_report BOOLEAN DEFAULT 0"))
            if "auto_report_model_id" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN auto_report_model_id VARCHAR(80)"))
            if "auto_report_type" not in cols:
                conn.execute(text(
                    "ALTER TABLE topics ADD COLUMN auto_report_type VARCHAR(20) DEFAULT 'analytical'"
                ))
            if "last_collection_run_id" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN last_collection_run_id VARCHAR(80)"))
            if "last_error" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN last_error TEXT"))
            if "collect_window_days" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN collect_window_days INTEGER DEFAULT 7"))
            if "schedule_cron" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN schedule_cron VARCHAR(100)"))
            if "next_run_at" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN next_run_at TIMESTAMP"))
            if "collection_model_ids" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN collection_model_ids JSON"))
            if "weekly_digest_enabled" not in cols:
                conn.execute(text(
                    "ALTER TABLE topics ADD COLUMN weekly_digest_enabled BOOLEAN DEFAULT 0"
                ))
            if "weekly_digest_model_id" not in cols:
                conn.execute(text(
                    "ALTER TABLE topics ADD COLUMN weekly_digest_model_id VARCHAR(80)"
                ))
            if "weekly_digest_target_items" not in cols:
                conn.execute(text(
                    "ALTER TABLE topics ADD COLUMN weekly_digest_target_items INTEGER DEFAULT 80"
                ))
            if "weekly_digest_part_size" not in cols:
                conn.execute(text(
                    "ALTER TABLE topics ADD COLUMN weekly_digest_part_size INTEGER DEFAULT 40"
                ))
            if "weekly_digest_min_items" not in cols:
                conn.execute(text(
                    "ALTER TABLE topics ADD COLUMN weekly_digest_min_items INTEGER DEFAULT 60"
                ))
            conn.commit()

    # Older schedule rows predate explicit timezone support.  Keep the existing
    # Beijing-time behavior while making the model/API contract truthful.
    if "schedule_configs" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("schedule_configs")}
        with engine.connect() as conn:
            if "timezone" not in cols:
                conn.execute(text(
                    "ALTER TABLE schedule_configs ADD COLUMN timezone VARCHAR(80) "
                    "DEFAULT 'Asia/Shanghai'"
                ))
            conn.commit()

    # Add window columns to `collection_runs` table if it exists
    if "collection_runs" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("collection_runs")}
        with engine.connect() as conn:
            if "batch_id" not in cols:
                conn.execute(text("ALTER TABLE collection_runs ADD COLUMN batch_id VARCHAR(80)"))
            if "window_start" not in cols:
                conn.execute(text("ALTER TABLE collection_runs ADD COLUMN window_start TIMESTAMP"))
            if "window_end" not in cols:
                conn.execute(text("ALTER TABLE collection_runs ADD COLUMN window_end TIMESTAMP"))
            if "progress_events" not in cols:
                conn.execute(text("ALTER TABLE collection_runs ADD COLUMN progress_events JSON"))
            conn.commit()

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS item_topic_memberships (
                item_id VARCHAR(120) NOT NULL REFERENCES collected_items(id) ON DELETE CASCADE,
                topic_id VARCHAR(80) NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                first_run_id VARCHAR(80),
                last_run_id VARCHAR(80),
                relevance_score FLOAT,
                first_seen_at TIMESTAMP,
                last_seen_at TIMESTAMP,
                PRIMARY KEY (item_id, topic_id)
            )
        """))
        membership_columns = {
            column["name"]
            for column in inspect(engine).get_columns("item_topic_memberships")
        }
        if "relevance_score" not in membership_columns:
            conn.execute(text(
                "ALTER TABLE item_topic_memberships "
                "ADD COLUMN relevance_score FLOAT"
            ))
        conn.execute(text("""
            INSERT OR IGNORE INTO item_topic_memberships (
                item_id, topic_id, first_run_id, last_run_id, relevance_score,
                first_seen_at, last_seen_at
            )
            SELECT id, topic_id, run_id, run_id, relevance_score, collected_at, updated_at
            FROM collected_items
            WHERE topic_id IS NOT NULL
        """))
        conn.execute(text("""
            UPDATE item_topic_memberships
            SET relevance_score = (
                SELECT collected_items.relevance_score
                FROM collected_items
                WHERE collected_items.id = item_topic_memberships.item_id
            )
            WHERE relevance_score IS NULL
        """))
        conn.commit()

    # Add scope columns to `reports` table if it exists
    if "reports" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("reports")}
        with engine.connect() as conn:
            if "collection_run_id" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN collection_run_id VARCHAR(80)"))
            if "date_range_start" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN date_range_start TIMESTAMP"))
            if "date_range_end" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN date_range_end TIMESTAMP"))
            if "output_files" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN output_files JSON"))
            if "output_dir" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN output_dir VARCHAR(800)"))
            if "report_type" not in cols:
                conn.execute(text(
                    "ALTER TABLE reports ADD COLUMN report_type VARCHAR(20) DEFAULT 'analytical'"
                ))
            if "series_id" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN series_id VARCHAR(120)"))
            if "period_key" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN period_key VARCHAR(40)"))
            if "part_index" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN part_index INTEGER"))
            if "part_total" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN part_total INTEGER"))
            if "selection_policy" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN selection_policy JSON"))
            if "selection_audit" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN selection_audit JSON"))
            if "retry_count" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN retry_count INTEGER DEFAULT 0"))
            if "last_error_at" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN last_error_at TIMESTAMP"))
            if "generation_owner" not in cols:
                conn.execute(text("ALTER TABLE reports ADD COLUMN generation_owner VARCHAR(80)"))
            if "generation_lease_until" not in cols:
                conn.execute(text(
                    "ALTER TABLE reports ADD COLUMN generation_lease_until TIMESTAMP"
                ))
            conn.execute(text(
                "UPDATE reports SET status = 'failed', "
                "error_log = COALESCE(error_log, '应用重启后释放未完成的生成任务') "
                "WHERE status = 'generating' AND generation_owner IS NULL"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_weekly_part "
                "ON reports(topic_id, period_key, report_type, part_index) "
                "WHERE period_key IS NOT NULL AND part_index IS NOT NULL"
            ))
            conn.commit()

    # Create model_configs table
    if "model_configs" not in existing_tables:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE model_configs (
                    id VARCHAR(80) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    provider VARCHAR(50) NOT NULL DEFAULT 'ollama',
                    base_url VARCHAR(500),
                    api_key VARCHAR(500),
                    model_name VARCHAR(200) NOT NULL DEFAULT '',
                    temperature FLOAT DEFAULT 0.7,
                    max_tokens INTEGER DEFAULT 4096,
                    top_p FLOAT DEFAULT 0.9,
                    is_default BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    description TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            conn.commit()

    # Create reports table
    if "reports" not in existing_tables:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE reports (
                    id VARCHAR(80) PRIMARY KEY,
                    topic_id VARCHAR(80) REFERENCES topics(id),
                    title VARCHAR(500) NOT NULL,
                    report_type VARCHAR(20) DEFAULT 'analytical',
                    content TEXT,
                    summary TEXT,
                    status VARCHAR(20) DEFAULT 'pending',
                    model_id VARCHAR(80),
                    tokens_used INTEGER DEFAULT 0,
                    item_count INTEGER DEFAULT 0,
                    item_ids JSON,
                    error_log TEXT,
                    collection_run_id VARCHAR(80),
                    date_range_start TIMESTAMP,
                    date_range_end TIMESTAMP,
                    generated_at TIMESTAMP,
                    created_at TIMESTAMP
                )
            """))
            conn.commit()

    # Create search_tool_configs table
    if "search_tool_configs" not in existing_tables:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE search_tool_configs (
                    id VARCHAR(80) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    tool_type VARCHAR(50) NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    config_json JSON,
                    api_key_ref VARCHAR(200),
                    is_default BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            conn.commit()

    # Create system_config table (single-row global settings)
    if "system_config" not in existing_tables:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE system_config (
                    id VARCHAR(20) PRIMARY KEY,
                    report_title_format VARCHAR(300) DEFAULT '{topic}_情报报告_{date}',
                    report_output_dir VARCHAR(800),
                    report_dir_pattern VARCHAR(100) DEFAULT '%Y-%m-%d',
                    report_formats JSON,
                    featured_item_ids JSON,
                    featured_updated_at TIMESTAMP,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            conn.commit()
    else:
        cols = {c["name"] for c in inspector.get_columns("system_config")}
        with engine.connect() as conn:
            if "featured_item_ids" not in cols:
                conn.execute(text("ALTER TABLE system_config ADD COLUMN featured_item_ids JSON"))
            if "featured_updated_at" not in cols:
                conn.execute(text("ALTER TABLE system_config ADD COLUMN featured_updated_at TIMESTAMP"))
            conn.execute(text(
                "UPDATE system_config SET report_title_format = '{title}_{date}' "
                "WHERE report_title_format = '{topic}_情报报告_{date}'"
            ))
            conn.commit()
