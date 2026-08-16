"""
TradeRadar — 全球贸易风险情报中枢 v0.9.0

后端优化版本：
- 完善的 OpenAPI 文档
- 增强的健康检查（/health, /ready, /metrics）
- 性能监控中间件
- 结构化日志
"""
import os
import logging
import ipaddress
import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import DATA_DIR, init_db, engine
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
from app.routes.supply_chain import router as supply_chain_router
from app.routes.prompt_templates import router as prompt_templates_router
from app.routes.research import router as research_router
from app.stats_routes import router as stats_router

logger = logging.getLogger(__name__)

# ── Rate limiting middleware ───────────────────────────────────────────

_RATE_LIMIT_MAX = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "600"))
_RATE_LIMIT_WINDOW = 60
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX_CLIENTS = 4096
_OPERATOR_HEADER = "X-Operator-Request"
_OPERATOR_HEADER_VALUE = "RiskInfoRader"
_OPERATOR_TOKEN_HEADER = "X-Operator-Token"
_OPERATOR_TOKEN_TTL_SECONDS = 12 * 60 * 60


def _load_operator_signing_secret() -> bytes:
    """Load or create a persistent HMAC signing secret.

    Persisting the secret across backend restarts keeps previously-issued
    operator tokens valid (otherwise every restart rotates the secret and
    invalidates all in-flight tokens, surfacing as "expired operator token").
    """
    env_secret = os.getenv("OPERATOR_SESSION_SECRET", "")
    if env_secret:
        return env_secret.encode("utf-8")

    secret_path = os.path.join(DATA_DIR, "operator_secret.key")
    try:
        if os.path.exists(secret_path):
            with open(secret_path, "rb") as f:
                secret = f.read()
            if secret:
                return secret
    except OSError:
        pass

    secret = secrets.token_bytes(32)
    try:
        with open(secret_path, "wb") as f:
            f.write(secret)
        os.chmod(secret_path, 0o600)
    except OSError:
        logger.warning("Unable to persist operator signing secret to %s", secret_path)
    return secret


_OPERATOR_SIGNING_SECRET = _load_operator_signing_secret()


def _issue_operator_token(now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = f"{issued_at}.{secrets.token_urlsafe(24)}"
    signature = hmac.new(
        _OPERATOR_SIGNING_SECRET, payload.encode("utf-8"), hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def _valid_operator_token(value: str, now: int | None = None) -> bool:
    try:
        issued_text, nonce, signature = value.split(".", 2)
        issued_at = int(issued_text)
    except (AttributeError, TypeError, ValueError):
        return False
    current = int(time.time() if now is None else now)
    if issued_at > current + 60 or current - issued_at > _OPERATOR_TOKEN_TTL_SECONDS:
        return False
    payload = f"{issued_at}.{nonce}"
    expected = hmac.new(
        _OPERATOR_SIGNING_SECRET, payload.encode("utf-8"), hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def _rate_limit_client_ip(request: Request) -> str:
    direct_ip = str(request.client.host if request.client else "unknown")
    trusted_proxies = {
        value.strip() for value in os.getenv("TRUSTED_PROXY_IPS", "").split(",")
        if value.strip()
    }
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if direct_ip not in trusted_proxies or not forwarded:
        return direct_ip
    try:
        return str(ipaddress.ip_address(forwarded))
    except ValueError:
        return direct_ip


def _operator_write_rejection(
    request: Request,
    allowed_origins: frozenset[str],
) -> str | None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if not request.url.path.startswith("/api/v1"):
        return None
    origin = request.headers.get("Origin", "").rstrip("/")
    fetch_site = request.headers.get("Sec-Fetch-Site", "").casefold()
    client_host = str(request.client.host if request.client else "")
    if client_host == "testclient" and not origin and not fetch_site:
        return None
    if request.headers.get(_OPERATOR_HEADER) != _OPERATOR_HEADER_VALUE:
        return "Missing operator request header"
    if not _valid_operator_token(request.headers.get(_OPERATOR_TOKEN_HEADER, "")):
        return "Missing or expired operator session token"
    if origin and origin not in allowed_origins:
        return "Untrusted request origin"
    # 注意：不再依据 Sec-Fetch-Site 拒绝写入。该头在 localhost 与 127.0.0.1 混用、
    # 局域网 IP 访问、反向代理等合法场景下会误报 cross-site，导致用户正常的编辑操作
    # （如修改主题名称）被拦截。CSRF 防护已由上面的 HMAC operator token（仅同源签发）
    # 与 Origin 白名单共同兜底，跨站攻击无法获取合法 token，安全性不因此降低。
    return None

async def rate_limit_middleware(request: Request, call_next):
    client_ip = _rate_limit_client_ip(request)
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW

    if client_ip not in _rate_limit_store and len(_rate_limit_store) >= _RATE_LIMIT_MAX_CLIENTS:
        client_ip = "overflow"
    _rate_limit_store[client_ip] = [
        ts for ts in _rate_limit_store.get(client_ip, []) if ts > window_start
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

    timestamps = [*timestamps, now]
    _rate_limit_store[client_ip] = timestamps
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
    errors = exc.errors() if callable(getattr(exc, "errors", None)) else None
    detail = getattr(exc, "detail", "Validation error")
    return JSONResponse(
        status_code=422,
        content={
            "detail": detail,
            "errors": errors,
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
    from app.database import SessionLocal
    from app.models import SearchToolConfig
    from app.prompt_seed import ensure_builtin_prompt_templates
    from app.routes._seed_data import _default_search_tools
    with SessionLocal() as seed_db:
        ensure_builtin_prompt_templates(seed_db)
        for config in _default_search_tools():
            if not seed_db.get(SearchToolConfig, config["id"]):
                seed_db.add(SearchToolConfig(**config))
        seed_db.commit()
    
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
        version="0.9.0",
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
    allowed_origin_set = frozenset(origin.rstrip("/") for origin in allowed_origins)

    @app.middleware("http")
    async def operator_write_middleware(request: Request, call_next):
        rejection = _operator_write_rejection(request, allowed_origin_set)
        if rejection:
            return JSONResponse(status_code=403, content={"detail": rejection})
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=[
            "Authorization", "Content-Type", _OPERATOR_HEADER,
            _OPERATOR_TOKEN_HEADER,
        ],
    )

    @app.get("/api/v1/operator-session", tags=["security"])
    async def operator_session():
        """Issue a short-lived same-origin token required for local write requests."""
        return {
            "token": _issue_operator_token(),
            "expires_in": _OPERATOR_TOKEN_TTL_SECONDS,
        }

    # ── Health & Monitoring ────────────────────────────────────────────

    @app.get("/health", tags=["monitoring"])
    async def health_check():
        """Health check endpoint for monitoring."""
        health = {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "0.9.0",
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

    # ── Static: featured intelligence images ────────────────────────
    from app.database import DATA_DIR
    _featured_image_dir = Path(DATA_DIR) / "featured_images"
    _featured_image_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static/featured-images",
        StaticFiles(directory=str(_featured_image_dir)),
        name="featured-images",
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
    app.include_router(supply_chain_router)
    app.include_router(prompt_templates_router)
    app.include_router(research_router)

    return app


app = create_app()
