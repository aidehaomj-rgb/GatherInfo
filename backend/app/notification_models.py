"""
Notification system — fire-and-forget webhook / email notifications
after collection completes.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx
from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer
from sqlalchemy.orm import Session

from app.database import Base

logger = logging.getLogger(__name__)


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    channel = Column(String, nullable=False)  # "webhook" | "email"
    webhook_url = Column(String, nullable=True)
    email_to = Column(String, nullable=True)
    trigger_on_new = Column(Boolean, default=True)  # fire when items_new > 0
    trigger_on_failure = Column(Boolean, default=False)  # fire when collection fails
    is_active = Column(Boolean, default=True)
    last_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class NotificationBatch(Base):
    """记录批次通知（包含多个子事件）。"""
    __tablename__ = "notification_batches"

    id = Column(String, primary_key=True)
    topic_id = Column(String, nullable=True)
    topic_name = Column(String, nullable=True)
    batch_id = Column(String, nullable=True)
    total_new = Column(Integer, default=0)
    source_count = Column(Integer, default=0)
    details = Column(Text, nullable=True)  # JSON 序列化的子事件摘要
    status = Column(String, default="completed")  # "completed" | "failed" | "partial"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_notification_tables(engine):
    """Create notification tables if not exists."""
    Base.metadata.create_all(engine)
    logger.info("Notification tables initialized")


@dataclass
class BatchEvent:
    """单个来源的采集结果事件，用于聚合。"""
    source_id: str
    source_name: str = ""
    items_new: int = 0
    status: str = "completed"
    error: str = ""


@dataclass
class AggregatedNotification:
    """聚合后的通知数据。"""
    event_type: str
    topic_id: str | None
    topic_name: str
    batch_id: str | None
    total_new: int
    source_count: int
    events: list[BatchEvent] = field(default_factory=list)
    status: str = "completed"


class NotificationSender:
    """Fire-and-forget sender for collection notifications.

    支持两种模式：
    1. 单条通知（向后兼容）：send()
    2. 批次聚合通知（推荐）：send_batch()
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def send(self, event_type: str, payload: dict):
        """Check active notification configs and dispatch fire-and-forget.

        向后兼容：将单条 payload 包装为单个事件后走聚合逻辑。
        """
        event = BatchEvent(
            source_id=payload.get("source_id", ""),
            source_name=payload.get("source_name", ""),
            items_new=payload.get("total_new", 0),
            status="completed" if event_type != "failure" else "failed",
            error=payload.get("error", ""),
        )
        aggregated = self.aggregate_notifications(
            topic_id=payload.get("topic_id"),
            topic_name=payload.get("topic_name", ""),
            batch_id=payload.get("batch_id"),
            events=[event],
        )
        if aggregated.total_new == 0 and aggregated.status == "completed":
            return
        self._dispatch(aggregated)

    def send_batch(
        self,
        topic_id: str | None,
        topic_name: str,
        batch_id: str | None,
        events: list[BatchEvent],
    ):
        """接收批次事件列表，合并后发送一次通知。"""
        aggregated = self.aggregate_notifications(
            topic_id=topic_id,
            topic_name=topic_name,
            batch_id=batch_id,
            events=events,
        )
        if aggregated.total_new == 0 and aggregated.status == "completed":
            return
        self._dispatch(aggregated)

    def aggregate_notifications(
        self,
        topic_id: str | None,
        topic_name: str,
        batch_id: str | None,
        events: list[BatchEvent],
    ) -> AggregatedNotification:
        """将同一主题/来源的多个通知合并为一条聚合通知。"""
        total_new = sum(e.items_new for e in events if e.status == "completed")
        failed_count = sum(1 for e in events if e.status == "failed")
        status = "failed" if failed_count == len(events) else ("partial" if failed_count > 0 else "completed")

        return AggregatedNotification(
            event_type="new_items" if total_new > 0 else "completion",
            topic_id=topic_id,
            topic_name=topic_name,
            batch_id=batch_id,
            total_new=total_new,
            source_count=len(events),
            events=events,
            status=status,
        )

    def _dispatch(self, aggregated: AggregatedNotification, config_ids: list[str] | None = None):
        """根据聚合结果发送通知，并持久化批次记录。config_ids 非空时只发给指定配置。"""
        db: Session = self.session_factory()
        try:
            q = db.query(NotificationConfig).filter(NotificationConfig.is_active == True)
            if config_ids:
                q = q.filter(NotificationConfig.id.in_(config_ids))
            configs = q.all()
            if not configs:
                return

            # 构建人类可读的通知正文
            subject, body = self._format_message(aggregated)
            payload = {
                "event": "collection_complete",
                "topic_id": aggregated.topic_id,
                "topic_name": aggregated.topic_name,
                "batch_id": aggregated.batch_id,
                "total_new": aggregated.total_new,
                "source_count": aggregated.source_count,
                "status": aggregated.status,
                "subject": subject,
                "body": body,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            for cfg in configs:
                should_fire = False
                if aggregated.event_type == "new_items" and cfg.trigger_on_new:
                    should_fire = True
                elif aggregated.event_type == "failure" and cfg.trigger_on_failure:
                    should_fire = True
                elif aggregated.event_type == "completion" and cfg.trigger_on_new:
                    should_fire = True

                if not should_fire:
                    continue

                if cfg.channel == "webhook" and cfg.webhook_url:
                    self._send_webhook_async(cfg, payload)
                elif cfg.channel == "email" and cfg.email_to:
                    self._send_email_async(cfg, payload)

                cfg.last_sent_at = datetime.now(timezone.utc)
                db.commit()

            # 持久化批次记录
            batch_record = NotificationBatch(
                id=f"nb-{uuid4().hex[:12]}",
                topic_id=aggregated.topic_id,
                topic_name=aggregated.topic_name,
                batch_id=aggregated.batch_id,
                total_new=aggregated.total_new,
                source_count=aggregated.source_count,
                details=json.dumps(
                    [{"source_id": e.source_id, "source_name": e.source_name, "items_new": e.items_new, "status": e.status} for e in aggregated.events],
                    ensure_ascii=False,
                ),
                status=aggregated.status,
            )
            db.add(batch_record)
            db.commit()
        except Exception as exc:
            logger.warning("Notification dispatch failed (non-blocking): %s", exc)
        finally:
            db.close()

    def send_single(self, config_id: str, payload: dict):
        """向单个配置发送测试/事件通知。"""
        event = BatchEvent(
            source_id=payload.get("source_id", ""),
            source_name=payload.get("source_name", ""),
            items_new=payload.get("total_new", 0),
            status="completed",
            error=payload.get("error", ""),
        )
        aggregated = self.aggregate_notifications(
            topic_id=payload.get("topic_id"),
            topic_name=payload.get("topic_name", ""),
            batch_id=payload.get("batch_id"),
            events=[event],
        )
        self._dispatch(aggregated, config_ids=[config_id])

    def _format_message(self, aggregated: AggregatedNotification) -> tuple[str, str]:
        """格式化聚合通知为可读的标题和正文。"""
        topic_name = aggregated.topic_name or "未知主题"
        total_new = aggregated.total_new
        source_count = aggregated.source_count

        # 构建来源明细："来源A: 8条，来源B: 7条"
        details_parts = []
        for e in aggregated.events:
            if e.status == "completed":
                name = e.source_name or e.source_id or "未知来源"
                details_parts.append(f"{name}: {e.items_new}条")

        if details_parts:
            detail_str = "（" + "，".join(details_parts) + "）"
        else:
            detail_str = ""

        subject = f"主题 '{topic_name}' 采集完成"
        body = f"主题 '{topic_name}' 采集完成：新增 {total_new} 条{detail_str}"
        return subject, body

    def _send_webhook_async(self, cfg: NotificationConfig, payload: dict):
        """Fire webhook in a background task."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._post_webhook(cfg.webhook_url, payload))
            else:
                asyncio.run(self._post_webhook(cfg.webhook_url, payload))
        except RuntimeError:
            asyncio.run(self._post_webhook(cfg.webhook_url, payload))

    async def _post_webhook(self, url: str, payload: dict):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            logger.warning("Webhook delivery failed for %s: %s", url, exc)

    def _send_email_async(self, cfg: NotificationConfig, payload: dict):
        """Send email via SMTP. Reads SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS
        from environment variables. Falls back to logging-only if not configured."""
        import os
        smtp_host = os.environ.get("SMTP_HOST", "")
        if not smtp_host:
            logger.info(
                "Email notification logged (SMTP not configured): to=%s, subject=%s",
                cfg.email_to,
                payload.get("subject", "GatherInfo Notification"),
            )
            return

        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        smtp_from = os.environ.get("SMTP_FROM", smtp_user or "gatherinfo@localhost")
        use_tls = os.environ.get("SMTP_TLS", "1") == "1"

        subject = payload.get("subject", "GatherInfo Notification")
        body = payload.get("body", json.dumps(payload, ensure_ascii=False))

        msg = MIMEMultipart()
        msg["From"] = smtp_from
        msg["To"] = cfg.email_to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            if use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)

            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)

            server.sendmail(smtp_from, cfg.email_to, msg.as_string())
            server.quit()
            logger.info("Email sent to %s via %s:%s", cfg.email_to, smtp_host, smtp_port)
        except Exception as exc:
            logger.warning("Email delivery failed for %s: %s", cfg.email_to, exc)
