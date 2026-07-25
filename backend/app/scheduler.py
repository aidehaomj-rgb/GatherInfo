"""
APScheduler integration for periodic topic/schedule execution.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.engine import CollectionEngine
from app.models import ScheduleConfig, Topic
from app.services.report_service import cleanup_old_reports


logger = logging.getLogger(__name__)
scheduler_instance: "CollectionScheduler | None" = None


def _now():
    return datetime.now(timezone.utc)


class CollectionScheduler:
    def __init__(self):
        self._scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._job_ids: dict[str, str] = {}

    async def start(self):
        self._scheduler.start()
        await self._load_all()
        self._scheduler.add_job(
            self._cleanup_reports,
            trigger=CronTrigger(hour=3, minute=0, timezone="Asia/Shanghai"),
            id="cleanup-reports",
            replace_existing=True,
        )
        logger.info("Scheduler started (%d jobs)", len(self._job_ids))

    async def shutdown(self):
        self._scheduler.shutdown(wait=False)

    async def add_schedule(self, schedule: ScheduleConfig) -> str:
        jid = f"sched-{schedule.id}"
        if jid in self._job_ids.values():
            self._scheduler.remove_job(jid)
        trigger = CronTrigger.from_crontab(schedule.cron_expression, schedule.timezone)
        self._scheduler.add_job(
            self._run_schedule, trigger=trigger, id=jid,
            args=[schedule.id], replace_existing=True,
        )
        self._job_ids[schedule.id] = jid
        return jid

    async def remove_schedule(self, schedule_id: str) -> bool:
        jid = f"sched-{schedule_id}"
        if jid in self._job_ids.values():
            self._scheduler.remove_job(jid)
            self._job_ids.pop(schedule_id, None)
            return True
        return False

    async def reload(self):
        for jid in list(self._job_ids.values()):
            self._scheduler.remove_job(jid)
        self._job_ids.clear()
        await self._load_all()

    # ── internal ─────────────────────────────────────────────────────────

    async def _load_all(self):
        db = SessionLocal()
        try:
            for s in db.query(ScheduleConfig).filter(ScheduleConfig.is_active == True).all():
                await self.add_schedule(s)

            for t in db.query(Topic).filter(Topic.is_scheduled == True, Topic.is_active == True).all():
                jid = f"topic-{t.id}"
                if jid in self._job_ids.values():
                    continue
                if t.schedule_cron and len(t.schedule_cron.strip().split()) == 5:
                    try:
                        trigger = CronTrigger.from_crontab(t.schedule_cron, "Asia/Shanghai")
                        self._scheduler.add_job(
                            self._run_topic, trigger=trigger, id=jid,
                            args=[t.id], replace_existing=True,
                        )
                        self._job_ids[jid] = jid
                    except Exception:
                        logger.warning("Invalid cron for topic %s: %s", t.id, t.schedule_cron)
        finally:
            db.close()

    async def _run_topic(self, topic_id: str):
        db = SessionLocal()
        try:
            engine = CollectionEngine(db)
            results = await engine.collect_topic(topic_id)
            total_new = sum(r.items_new for r in results)
            logger.info("Topic %s done: %d new", topic_id, total_new)

            topic = db.query(Topic).filter(Topic.id == topic_id).first()
            if topic and topic.auto_report:
                run_ids = [result.run_id for result in results if getattr(result, "run_id", None)]
                try:
                    from app.report_engine import generate_report
                    report_date = datetime.now().strftime("%Y-%m-%d")
                    report = await generate_report(
                        topic_id=topic_id,
                        model_id=topic.auto_report_model_id,
                        title_override=f"{topic.name}（{report_date}）",
                        collection_run_ids=run_ids,
                    )
                    logger.info("Auto-report for topic %s: %s (%s)",
                                topic_id, report.id, report.status)
                except Exception as exc:
                    logger.error("Auto-report for topic %s failed: %s", topic_id, exc)
        except Exception as exc:
            logger.error("Topic %s failed: %s", topic_id, exc)
        finally:
            db.close()

    async def _run_schedule(self, schedule_id: str):
        db = SessionLocal()
        try:
            engine = CollectionEngine(db)
            results = await engine.execute_schedule(schedule_id)
            total_new = sum(r.items_new for r in results)
            logger.info("Schedule %s done: %d new", schedule_id, total_new)
        except Exception as exc:
            logger.error("Schedule %s failed: %s", schedule_id, exc)
        finally:
            db.close()

    async def _cleanup_reports(self):
        db = SessionLocal()
        try:
            deleted = cleanup_old_reports(db, days=7)
            logger.info("Cleaned up %d reports older than 7 days", deleted)
        except Exception as exc:
            logger.error("Report cleanup failed: %s", exc)
        finally:
            db.close()
