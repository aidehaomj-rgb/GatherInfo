"""Report business logic — CRUD helpers, system config, exports."""
import logging
import os
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Report, SystemConfig, Topic

logger = logging.getLogger(__name__)


def get_system_config(db: Session) -> SystemConfig:
    """Get or create the global system config."""
    cfg = db.query(SystemConfig).filter(SystemConfig.id == "global").first()
    if not cfg:
        cfg = SystemConfig(id="global")
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def list_reports(db: Session, topic_id: Optional[str] = None, days: Optional[int] = None, limit: int = 50):
    """List reports, optionally filtered by topic and recent days."""
    q = db.query(Report)
    if topic_id:
        q = q.filter(Report.topic_id == topic_id)
    if days:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        q = q.filter(Report.created_at >= cutoff)
    total = q.count()
    reports = q.order_by(Report.created_at.desc()).limit(limit).all()
    return reports, total


def get_report(db: Session, report_id: str) -> Report:
    """Get a single report by ID."""
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(404, f"Report not found: {report_id}")
    return r


def cleanup_old_reports(db: Session, days: int = 7) -> int:
    """Delete reports older than the given number of days and their exported files."""
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stale = db.query(Report).filter(Report.created_at < cutoff).all()
    deleted = 0
    for r in stale:
        try:
            for path in (r.output_files or {}).values():
                if path and os.path.isfile(path):
                    os.remove(path)
        except OSError:
            pass
        db.delete(r)
        deleted += 1
    db.commit()
    return deleted


def delete_report(db: Session, report_id: str) -> None:
    """Delete a report and its exported files."""
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(404, f"Report not found: {report_id}")
    # Clean up exported files
    output_files = r.output_files or {}
    for path in output_files.values():
        try:
            if path and os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
    db.delete(r)
    db.commit()


def export_report_files(db: Session, report_id: str) -> Report:
    """Export a report to configured formats and persist file paths."""
    r = get_report(db, report_id)
    if not (r.content or "").strip():
        raise HTTPException(400, "报告内容为空，无法导出")

    from app.report_export import export_report as _export
    system = get_system_config(db)
    topic = db.query(Topic).filter(Topic.id == r.topic_id).first()
    try:
        _export(r, system, topic)
        db.commit()
        db.refresh(r)
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"导出失败: {exc}")
    return r


def download_report_file(report_id: str, format: str, db: Session) -> tuple[str, str, str]:
    """Validate download request, return (file_path, media_type, filename)."""
    r = get_report(db, report_id)
    files = r.output_files or {}
    path = files.get(format)
    if not path or not os.path.isfile(path):
        raise HTTPException(404, f"未找到 {format} 格式文件，请先导出")

    media = {
        "md": "text/markdown",
        "html": "text/html",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }.get(format, "application/octet-stream")

    return path, media, os.path.basename(path)
