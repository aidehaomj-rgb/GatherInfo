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
    from app.report_export import normalize_report_output_dir

    normalized_dir = normalize_report_output_dir(cfg.report_output_dir)
    if cfg.report_output_dir != normalized_dir:
        cfg.report_output_dir = normalized_dir
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
    from app.report_export import valid_output_files

    changed = False
    for report in reports:
        available = valid_output_files(report.output_files)
        if report.output_files != available:
            report.output_files = available
            changed = True
    if changed:
        db.commit()
    return reports, total


def get_report(db: Session, report_id: str) -> Report:
    """Get a single report by ID."""
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(404, f"Report not found: {report_id}")
    return r


def cleanup_old_reports(db: Session, days: int = 7) -> int:
    """Delete transient reports while retaining published weekly editions."""
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stale = db.query(Report).filter(
        Report.created_at < cutoff,
        Report.report_type != "weekly_digest",
    ).all()
    deleted = 0
    for r in stale:
        try:
            from app.report_export import is_approved_report_path
            for path in (r.output_files or {}).values():
                if is_approved_report_path(path, require_file=True):
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
    from app.report_export import is_approved_report_path
    for path in output_files.values():
        try:
            if is_approved_report_path(path, require_file=True):
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
        output_files = _export(r, system, topic)
        if not output_files:
            raise RuntimeError("未能生成任何导出格式，请检查报告输出目录和本地导出依赖。")
        db.commit()
        db.refresh(r)
    except Exception as exc:
        db.rollback()
        logger.exception("Report export failed for %s", report_id)
        raise HTTPException(500, "报告导出失败，请检查服务器输出目录与导出依赖")
    return r


def download_report_file(report_id: str, format: str, db: Session) -> tuple[str, str, str]:
    """Return an export file, regenerating a missing requested format once."""
    from app.report_export import SUPPORTED_FORMATS, export_report, valid_output_files

    format = format.strip().lower()
    if format not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"不支持的报告格式: {format}")
    r = get_report(db, report_id)
    files = valid_output_files(r.output_files)
    path = files.get(format)
    if not path:
        if not (r.content or "").strip():
            raise HTTPException(400, "报告内容为空，无法重新生成下载文件")
        try:
            system = get_system_config(db)
            topic = db.query(Topic).filter(Topic.id == r.topic_id).first()
            files = export_report(r, system, topic, formats=[format])
            db.commit()
            db.refresh(r)
            path = files.get(format)
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to restore report %s format %s", report_id, format)
            raise HTTPException(500, f"无法重新生成 {format.upper()} 文件")
    from app.report_export import is_approved_report_path
    if not is_approved_report_path(path, require_file=True):
        raise HTTPException(409, f"未能生成 {format.upper()} 文件，请检查导出设置后重试")

    media = {
        "md": "text/markdown",
        "html": "text/html",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }.get(format, "application/octet-stream")

    return path, media, os.path.basename(path)
