"""Notification configuration CRUD + test endpoint."""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.notification_models import NotificationConfig, NotificationSender

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# ── Schemas ─────────────────────────────────────────────────────────────

class NotificationCreate(BaseModel):
    id: str | None = None
    name: str
    channel: str
    webhook_url: str | None = None
    email_to: str | None = None
    trigger_on_new: bool = True
    trigger_on_failure: bool = False
    is_active: bool = True


class NotificationUpdate(BaseModel):
    name: str | None = None
    channel: str | None = None
    webhook_url: str | None = None
    email_to: str | None = None
    trigger_on_new: bool | None = None
    trigger_on_failure: bool | None = None
    is_active: bool | None = None


class NotificationOut(BaseModel):
    id: str
    name: str
    channel: str
    webhook_url: str | None = None
    email_to: str | None = None
    trigger_on_new: bool
    trigger_on_failure: bool
    is_active: bool
    last_sent_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}

    @field_validator('created_at', 'updated_at', 'last_sent_at', mode='before')
    @classmethod
    def coerce_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            return v
        return v.isoformat()


class TestNotificationRequest(BaseModel):
    id: str


class TestNotificationResponse(BaseModel):
    success: bool
    message: str


# ── CRUD ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db)):
    return db.query(NotificationConfig).order_by(NotificationConfig.created_at.desc()).all()


@router.post("", response_model=NotificationOut)
def create_notification(data: NotificationCreate, db: Session = Depends(get_db)):
    if data.channel not in ("webhook", "email"):
        raise HTTPException(400, "channel must be 'webhook' or 'email'")
    if data.channel == "webhook" and not data.webhook_url:
        raise HTTPException(400, "webhook_url required for webhook channel")
    if data.channel == "email" and not data.email_to:
        raise HTTPException(400, "email_to required for email channel")

    cfg = NotificationConfig(
        id=data.id or f"notif-{uuid4().hex[:12]}",
        name=data.name,
        channel=data.channel,
        webhook_url=data.webhook_url,
        email_to=data.email_to,
        trigger_on_new=data.trigger_on_new,
        trigger_on_failure=data.trigger_on_failure,
        is_active=data.is_active,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.put("/{notif_id}", response_model=NotificationOut)
def update_notification(notif_id: str, data: NotificationUpdate, db: Session = Depends(get_db)):
    cfg = db.query(NotificationConfig).filter(NotificationConfig.id == notif_id).first()
    if not cfg:
        raise HTTPException(404, f"Notification config not found: {notif_id}")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)

    cfg.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.delete("/{notif_id}")
def delete_notification(notif_id: str, db: Session = Depends(get_db)):
    cfg = db.query(NotificationConfig).filter(NotificationConfig.id == notif_id).first()
    if not cfg:
        raise HTTPException(404, f"Notification config not found: {notif_id}")
    db.delete(cfg)
    db.commit()
    return {"ok": True}


@router.post("/prune", response_model=dict)
def prune_notifications(db: Session = Depends(get_db)):
    """清理测试、无效、未激活的通知配置。"""
    patterns = [
        NotificationConfig.name.ilike("%test%"),
        NotificationConfig.webhook_url.ilike("%example.com%"),
        NotificationConfig.webhook_url.ilike("%httpbin.org%"),
        NotificationConfig.webhook_url.ilike("%localhost%"),
        NotificationConfig.email_to.ilike("%test@example.com%"),
        NotificationConfig.email_to.ilike("%localhost%"),
    ]
    empty = or_(
        and_(NotificationConfig.channel == "webhook", NotificationConfig.webhook_url == ""),
        and_(NotificationConfig.channel == "email", NotificationConfig.email_to == ""),
    )
    query = db.query(NotificationConfig).filter(
        or_(NotificationConfig.is_active == False, or_(*patterns), empty)
    )
    count = query.count()
    for cfg in query.all():
        db.delete(cfg)
    db.commit()
    return {"deleted": count}




@router.post("/test", response_model=TestNotificationResponse)
def test_notification(data: TestNotificationRequest, db: Session = Depends(get_db)):
    cfg = db.query(NotificationConfig).filter(NotificationConfig.id == data.id).first()
    if not cfg:
        raise HTTPException(404, f"Notification config not found: {data.id}")

    from app.database import SessionLocal
    sender = NotificationSender(SessionLocal)
    try:
        sender.send_single(cfg.id, {
            "event": "test",
            "topic_id": cfg.id,
            "topic_name": cfg.name,
            "source_id": cfg.id,
            "source_name": cfg.name,
            "total_new": 1,
            "batch_id": None,
        })
        return TestNotificationResponse(success=True, message=f"Test notification sent via {cfg.channel}")
    except Exception as exc:
        return TestNotificationResponse(success=False, message=str(exc))
