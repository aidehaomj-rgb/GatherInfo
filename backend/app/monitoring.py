"""
TradeRadar Monitoring & Observability
性能监控、指标收集、结构化日志
"""
import logging
import time
import os
import psutil
from datetime import datetime, timezone
from collections import defaultdict
from typing import Callable

from fastapi import Request
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

# ── Metrics Store ──────────────────────────────────────────────────────

class MetricsStore:
    """Simple in-memory metrics store for Prometheus-style exposition."""

    def __init__(self):
        self.counters: dict[str, int] = defaultdict(int)
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.timestamps: dict[str, str] = {}

    def inc(self, name: str, value: int = 1):
        self.counters[name] += value
        self.timestamps[name] = datetime.now(timezone.utc).isoformat()

    def set(self, name: str, value: float):
        self.gauges[name] = value
        self.timestamps[name] = datetime.now(timezone.utc).isoformat()

    def observe(self, name: str, value: float):
        self.histograms[name].append(value)
        if len(self.histograms[name]) > 1000:
            self.histograms[name] = self.histograms[name][-1000:]
        self.timestamps[name] = datetime.now(timezone.utc).isoformat()

    def to_prometheus(self) -> str:
        lines = []
        lines.append("# TradeRadar Metrics")
        lines.append(f"# Generated at {datetime.now(timezone.utc).isoformat()}")
        lines.append("")

        for name, value in sorted(self.counters.items()):
            lines.append(f"{name}_total {value}")

        lines.append("")
        for name, value in sorted(self.gauges.items()):
            lines.append(f"{name} {value}")

        lines.append("")
        for name, values in sorted(self.histograms.items()):
            if values:
                avg = sum(values) / len(values)
                lines.append(f"{name}_avg {avg:.3f}")
                lines.append(f"{name}_count {len(values)}")

        return "\n".join(lines)

metrics = MetricsStore()

# ── Performance Middleware ───────────────────────────────────────────────

async def performance_middleware(request: Request, call_next):
    """Record request timing and status code distribution."""
    start = time.monotonic()

    response = await call_next(request)

    duration = time.monotonic() - start
    status = response.status_code
    path = request.url.path
    method = request.method

    # Record metrics
    metrics.inc(f"http_requests_total", 1)
    metrics.inc(f"http_requests_{method}_total", 1)
    metrics.inc(f"http_status_{status}_total", 1)
    metrics.observe(f"http_request_duration_seconds", duration)

    # Log slow requests
    if duration > 1.0:
        logger.warning(
            "Slow request: %s %s took %.2fs (status=%d)",
            method, path, duration, status
        )

    return response

# ── System Metrics ─────────────────────────────────────────────────────

def get_system_metrics() -> dict:
    """Get current system resource usage."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()

    return {
        "memory_rss_mb": mem_info.rss / 1024 / 1024,
        "memory_vms_mb": mem_info.vms / 1024 / 1024,
        "cpu_percent": process.cpu_percent(),
        "open_files": len(process.open_files()),
        "connections": len(process.connections()),
        "threads": process.num_threads(),
    }

# ── Collection Metrics ───────────────────────────────────────────────────

def record_collection_start(topic_id: str):
    """Record collection start."""
    metrics.inc("collections_total", 1)
    metrics.set(f"collection_last_start_{topic_id}", time.time())

def record_collection_success(topic_id: str, items_count: int):
    """Record successful collection."""
    metrics.inc("collections_success_total", 1)
    metrics.inc("items_collected_total", items_count)

def record_collection_failure(topic_id: str, error: str):
    """Record failed collection."""
    metrics.inc("collections_failure_total", 1)
    logger.error("Collection failed for topic %s: %s", topic_id, error)

# ── Database Metrics ─────────────────────────────────────────────────────

def record_db_query(duration: float, query_type: str = "select"):
    """Record database query metrics."""
    metrics.observe(f"db_query_duration_seconds", duration)
    metrics.inc(f"db_queries_{query_type}_total", 1)

# ── Prometheus Exposition ────────────────────────────────────────────────

def get_prometheus_metrics() -> str:
    """Get all metrics in Prometheus exposition format."""
    # Update system metrics
    sys_metrics = get_system_metrics()
    for key, value in sys_metrics.items():
        metrics.set(f"system_{key}", value)

    return metrics.to_prometheus()
