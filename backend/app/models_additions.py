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
                cols.add("api_key")
            if "homepage_url" not in cols:
                conn.execute(text("ALTER TABLE source_configs ADD COLUMN homepage_url VARCHAR(800)"))
                cols.add("homepage_url")
            source_group_added = "source_group" not in cols
            if source_group_added:
                conn.execute(text(
                    "ALTER TABLE source_configs ADD COLUMN "
                    "source_group VARCHAR(80) NOT NULL DEFAULT 'other'"
                ))
                cols.add("source_group")
            from app.source_taxonomy import backfill_source_groups
            backfill_source_groups(
                conn, available_columns=cols, replace_other=source_group_added
            )
            if "is_configured" not in cols:
                conn.execute(text("ALTER TABLE source_configs ADD COLUMN is_configured BOOLEAN DEFAULT 0"))
                # Auto-set: web_scrape/official/rss/manual sources are always configured
                conn.execute(text("UPDATE source_configs SET is_configured = 1 WHERE channel IN ('WEB_SCRAPE','OFFICIAL','RSS','SOCIAL','DEEPWEB','MANUAL')"))
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
            if "prompt_template_ids" not in cols:
                conn.execute(text("ALTER TABLE topics ADD COLUMN prompt_template_ids JSON"))
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

    if "research_jobs" in existing_tables:
        cols = {c["name"] for c in inspector.get_columns("research_jobs")}
        with engine.connect() as conn:
            if "acceptance_policy" not in cols:
                conn.execute(text("ALTER TABLE research_jobs ADD COLUMN acceptance_policy JSON"))
            if "acceptance_result" not in cols:
                conn.execute(text("ALTER TABLE research_jobs ADD COLUMN acceptance_result JSON"))
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
            conn.commit()
