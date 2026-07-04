"""
TradeRadar — 全球贸易风险情报中枢

The collection engine is the core of this application.
Everything else (tags, topics, stats, search) derives from collected data.
"""
import os
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import init_db
from app.routes.sources import router as sources_router
from app.routes.topics import router as topics_router
from app.routes.items import router as items_router
from app.routes.tags import router as tags_router
from app.routes.reports import router as reports_router
from app.routes.models import router as models_router
from app.routes.schedules import router as schedules_router
from app.routes.search_tools import router as search_tools_router
from app.routes.settings import router as settings_router
from app.routes.seed import router as seed_router
from app.routes.notifications import router as notifications_router
from app.stats_routes import router as stats_router

logger = logging.getLogger(__name__)


# ── Rate limiting middleware ───────────────────────────────────────────

_RATE_LIMIT_MAX = 120          # requests per window
_RATE_LIMIT_WINDOW = 60        # seconds (sliding window)
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


async def rate_limit_middleware(request: Request, call_next):
    """Sliding-window rate limiter: max _RATE_LIMIT_MAX requests per window."""
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.client.host
    )
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW

     # Prune old entries outside the current window
    _rate_limit_store[client_ip] = [
        ts for ts in _rate_limit_store[client_ip] if ts > window_start
    ]

    timestamps = _rate_limit_store[client_ip]
    remaining = max(0, _RATE_LIMIT_MAX - len(timestamps))
    reset_at = now + _RATE_LIMIT_WINDOW if timestamps else now

    if len(timestamps) >= _RATE_LIMIT_MAX:
        logger.warning("Rate limit exceeded for %s", client_ip)
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please retry after 60 seconds.",
                "retry_after": int(_RATE_LIMIT_WINDOW - (now - timestamps[0])),
            },
            headers={
                "X-RateLimit-Limit": str(_RATE_LIMIT_MAX),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(reset_at)),
                "Retry-After": str(int(_RATE_LIMIT_WINDOW - (now - timestamps[0]))),
            },
        )

    timestamps.append(now)
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(_RATE_LIMIT_MAX)
    response.headers["X-RateLimit-Remaining"] = str(max(0, _RATE_LIMIT_MAX - len(timestamps)))
    response.headers["X-RateLimit-Reset"] = str(int(reset_at))
    return response


# ── Logging middleware ────────────────────────────────────────────────

async def log_requests(request: Request, call_next):
    """Log all API requests with timing and status."""
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start_time = datetime.now(timezone.utc)

    response = await call_next(request)

    duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

    logger.info(
        "%s %s %d %.0fms",
        request_id,
        request.method,
        response.status_code,
        duration_ms,
    )

    return response


# ── Exception handlers ─────────────────────────────────────────────────

async def validation_exception_handler(request: Request, exc):
    """Return consistent error responses for validation failures."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
        },
    )


async def value_error_handler(request: Request, exc: ValueError):
    """ValueError → 400 Bad Request."""
    logger.warning("ValueError in %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def lookup_error_handler(request: Request, exc: LookupError):
    """LookupError (KeyError, IndexError) → 404 Not Found."""
    logger.warning("LookupError in %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})


async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all → 500 Internal Server Error with full traceback."""
    logger.error(
        "Unhandled exception in %s %s: %s",
        request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Health check ──────────────────────────────────────────────────────

async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.4.0",
        "environment": os.getenv("ENV", "production"),
    }

scheduler_instance = None


def _startup_diagnostics():
    """Validate critical config exists, auto-seed if missing, and log DB diagnostics."""
    from sqlalchemy import inspect, text
    from app.database import SessionLocal, engine, _db_file_path
    from app.models import SourceConfig, ModelConfig

    db = SessionLocal()
    try:
        active_sources = db.query(SourceConfig).filter(SourceConfig.is_active == True).count()
        active_models = db.query(ModelConfig).filter(ModelConfig.is_active == True).count()

        # Auto-seed defaults if critical config is missing.
        if active_sources == 0 or active_models == 0:
            logger.warning(
                "Missing critical config (active_sources=%d, active_models=%d). Seeding defaults.",
                active_sources, active_models,
            )
            try:
                from app.routes.seed import (
                    _default_sources, _default_topics, _default_models,
                    _default_search_tools, _default_keyword_tags, _default_description_prompt,
                    _DEFAULT_CATEGORIES,
                )
                from app.models import Category
                from app.models import Topic, SearchToolConfig
                for cfg in _default_sources():
                    if not db.query(SourceConfig).filter(SourceConfig.id == cfg["id"]).first():
                        db.add(SourceConfig(**cfg))
                for cfg in _default_models():
                    if not db.query(ModelConfig).filter(ModelConfig.id == cfg["id"]).first():
                        db.add(ModelConfig(**cfg))
                for cfg in _default_topics():
                    if not db.query(Topic).filter(Topic.id == cfg["id"]).first():
                        t = Topic(**cfg)
                        t.keyword_tags = _default_keyword_tags(cfg["id"])
                        t.description_prompt = _default_description_prompt(cfg["id"])
                        db.add(t)
                for cat in _DEFAULT_CATEGORIES:
                    if not db.query(Category).filter(Category.id == cat["id"]).first():
                        db.add(Category(**cat))
                for cfg in _default_search_tools():
                    if not db.query(SearchToolConfig).filter(SearchToolConfig.id == cfg["id"]).first():
                        db.add(SearchToolConfig(**cfg))
                db.commit()
                logger.info("Default configuration seeded.")
            except Exception as exc:
                db.rollback()
                logger.error("Auto-seed failed: %s", exc)

        # Diagnostics: db path, table count, per-table row counts.
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info("DB path: %s", _db_file_path() or "(non-sqlite)")
        logger.info("Tables (%d): %s", len(tables), ", ".join(tables))
        for tbl in tables:
            try:
                count = db.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                logger.info("   %-22s %d rows", tbl, count)
            except Exception:
                pass
    except Exception as exc:
        logger.error("Startup diagnostics failed: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler_instance

    init_db()
    _startup_diagnostics()

    try:
        from app.scheduler import CollectionScheduler
        scheduler_instance = CollectionScheduler()
        import app.scheduler as sched_module
        sched_module.scheduler_instance = scheduler_instance
        await scheduler_instance.start()
        logger.info("Scheduler started")
    except Exception as exc:
        logger.warning("Scheduler unavailable: %s", exc)

    yield

    if scheduler_instance:
        await scheduler_instance.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TradeRadar",
        version="0.4.0",
        description="全球贸易风险情报中枢 — 主题驱动的多源采集、标签结构化入库、统计与分析。",
        lifespan=lifespan,
        docs_url="/docs",             # Swagger UI
        redoc_url="/redoc",           # ReDoc
        openapi_url="/openapi.json", # OpenAPI schema
    )

    # Register custom validation exception handler
    app.add_exception_handler(422, validation_exception_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(LookupError, lookup_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Add logging middleware
    app.middleware("http")(log_requests)

    # ── Middleware (order matters: outermost first) ─────────────────────
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(log_requests)

    allowed_origins = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5178,http://localhost:5178").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Health check (must be before routers to avoid prefix conflicts)
    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring."""
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.4.0",
            "environment": os.getenv("ENV", "production"),
        }

    # ── Collection is the core ─────────────────────────────────────────
    app.include_router(sources_router)
    app.include_router(topics_router)
    app.include_router(items_router)
    app.include_router(tags_router)
    app.include_router(reports_router)
    app.include_router(models_router)
    app.include_router(schedules_router)
    app.include_router(search_tools_router)
    app.include_router(settings_router)
    app.include_router(seed_router)
    app.include_router(stats_router)
    app.include_router(notifications_router)

    return app


app = create_app()
