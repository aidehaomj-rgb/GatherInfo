"""
TradeRadar — 全球贸易风险情报中枢 v0.7.0

后端优化版本：
- 完善的 OpenAPI 文档
- 增强的健康检查（/health, /ready, /metrics）
- 性能监控中间件
- 结构化日志
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
from fastapi.responses import JSONResponse, PlainTextResponse

from app.database import init_db, engine
from app.monitoring import (
    performance_middleware, get_system_metrics, get_prometheus_metrics,
    record_collection_start, record_collection_success, record_collection_failure
)
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
from app.routes.ymg_deep import router as ymg_router
from app.routes.haisee import router as haisee_router
from app.routes.material_sets import router as material_sets_router
from app.stats_routes import router as stats_router

logger = logging.getLogger(__name__)

# ── Rate limiting middleware ───────────────────────────────────────────

_RATE_LIMIT_MAX = 120
_RATE_LIMIT_WINDOW = 60
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

async def rate_limit_middleware(request: Request, call_next):
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.client.host
    )
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW

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

# ── Structured logging middleware ──────────────────────────────────────

async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start_time = datetime.now(timezone.utc)

    response = await call_next(request)
    
    duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else None,
        }
    )
    
    return response

# ── Exception handlers ───────────────────────────────────────────────

async def validation_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
        },
    )

async def value_error_handler(request: Request, exc: ValueError):
    logger.warning("ValueError in %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})

async def lookup_error_handler(request: Request, exc: LookupError):
    logger.warning("LookupError in %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})

async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception in %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# ── Lifespan ───────────────────────────────────────────────────────────

scheduler_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler_instance

    init_db()
    
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

# ── App Factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="TradeRadar",
        version="0.7.0",
        description="全球贸易风险情报中枢 — 主题驱动的多源采集、标签结构化入库、统计与分析。",
        contact={
            "name": "TradeRadar Team",
            "url": "https://github.com/traderadar",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        terms_of_service="https://traderadar.io/terms",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Exception handlers
    app.add_exception_handler(422, validation_exception_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(LookupError, lookup_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Middleware (order matters: outermost first)
    app.middleware("http")(performance_middleware)
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(log_requests)

    # CORS
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

    # ── Health & Monitoring ────────────────────────────────────────────

    @app.get("/health", tags=["monitoring"])
    async def health_check():
        """Health check endpoint for monitoring."""
        health = {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.7.0",
            "environment": os.getenv("ENV", "production"),
            "components": {},
        }
        
        # Database check
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            health["components"]["database"] = "ok"
        except Exception as exc:
            health["components"]["database"] = f"error: {exc}"
            health["status"] = "degraded"
        
        # Scheduler check
        if scheduler_instance:
            health["components"]["scheduler"] = "ok"
        else:
            health["components"]["scheduler"] = "not_running"
        
        # System metrics
        health["system"] = get_system_metrics()
        
        return health

    @app.get("/ready", tags=["monitoring"])
    async def readiness_check():
        """Readiness probe for Kubernetes."""
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": str(exc)}
            )

    @app.get("/metrics", tags=["monitoring"])
    async def prometheus_metrics():
        """Prometheus-style metrics exposition."""
        return PlainTextResponse(
            content=get_prometheus_metrics(),
            media_type="text/plain; version=0.0.4"
        )

    # ── Routers ──────────────────────────────────────────────────────
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
    app.include_router(ymg_router)
    app.include_router(haisee_router)
    app.include_router(material_sets_router)

    return app


app = create_app()
