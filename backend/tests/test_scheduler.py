"""
Tests for scheduler — cron validation, job management, scheduler instantiation.

Run: cd backend && python -m pytest tests/test_scheduler.py -v
"""
import os
import sys
import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scheduler import CollectionScheduler, _now, _previous_complete_week_reference
from apscheduler.triggers.cron import CronTrigger


# ── _now ────────────────────────────────────────────────────────────────────

def test_now_returns_utc():
    result = _now()
    assert result.tzinfo == timezone.utc
    assert isinstance(result, datetime)


def test_now_is_recent():
    result = _now()
    delta = datetime.now(timezone.utc) - result
    assert abs(delta.total_seconds()) < 5


def test_missed_weekly_run_targets_previous_complete_beijing_week():
    now = datetime(2026, 8, 4, 12, tzinfo=timezone(timedelta(hours=8)))

    reference = _previous_complete_week_reference(now)

    assert reference.isoformat() == "2026-08-02T23:59:59.999999+08:00"


# ── CronTrigger validation ──────────────────────────────────────────────────

class TestCronValidation:
    def test_valid_5_field_cron(self):
        trigger = CronTrigger.from_crontab("0 8 * * *")
        assert trigger is not None

    def test_valid_cron_with_day_of_week(self):
        trigger = CronTrigger.from_crontab("30 14 * * 1-5")
        assert trigger is not None

    def test_invalid_cron_raises(self):
        with pytest.raises(Exception):
            CronTrigger.from_crontab("not a cron")

    def test_too_few_fields_raises(self):
        with pytest.raises(Exception):
            CronTrigger.from_crontab("0 8 *")

    def test_too_many_fields_raises(self):
        """APScheduler from_crontab only accepts 5-field cron expressions."""
        with pytest.raises(ValueError, match="Wrong number of fields"):
            CronTrigger.from_crontab("0 0 8 * * *")


# ── CollectionScheduler initialization ─────────────────────────────────────

class TestSchedulerInit:
    def test_creates_with_timezone(self):
        sched = CollectionScheduler()
        assert sched._scheduler is not None
        assert sched._job_ids == {}
        assert sched._scheduler.timezone is not None

    def test_starts_empty(self):
        sched = CollectionScheduler()
        assert len(sched._job_ids) == 0

    def test_shutdown_on_not_started_raises(self):
        """APScheduler raises SchedulerNotRunningError when shutting down 
        a scheduler that was never started."""
        sched = CollectionScheduler()
        with pytest.raises(Exception):
            asyncio.run(sched.shutdown())

    def test_start_registers_cleanup_and_weekly_publication_jobs(self):
        sched = CollectionScheduler()
        sched._scheduler.start = MagicMock()
        sched._scheduler.add_job = MagicMock()
        sched._load_all = AsyncMock()
        sched._publish_weekly_digests = AsyncMock()

        asyncio.run(sched.start())

        job_ids = [call.kwargs["id"] for call in sched._scheduler.add_job.call_args_list]
        assert job_ids == ["cleanup-reports", "publish-weekly-digests"]
        sched._publish_weekly_digests.assert_awaited_once()


def test_weekly_job_publishes_each_enabled_topic(monkeypatch):
    sched = CollectionScheduler()
    topic = SimpleNamespace(id="topic-weekly", weekly_digest_model_id="model-1")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [topic]
    publication = SimpleNamespace(
        reports=[SimpleNamespace(id="report-1"), SimpleNamespace(id="report-2")],
        plan=SimpleNamespace(series_id="topic-weekly-weekly-2026-W31"),
        warnings=(),
    )
    publish = AsyncMock(return_value=publication)
    monkeypatch.setattr("app.scheduler.SessionLocal", lambda: db)
    monkeypatch.setattr(
        "app.weekly_report_engine.publish_weekly_digest", publish,
    )

    asyncio.run(sched._publish_weekly_digests())

    publish.assert_awaited_once()
    assert publish.await_args.args[:2] == (db, "topic-weekly")
    assert publish.await_args.kwargs["model_id"] == "model-1"
    db.close.assert_called_once()


# ── Job ID management ───────────────────────────────────────────────────────

class TestJobIdManagement:
    def test_schedule_jid_pattern(self):
        jid = f"sched-myschedule"
        assert jid.startswith("sched-")

    def test_topic_jid_pattern(self):
        jid = f"topic-mytopic"
        assert jid.startswith("topic-")


# ── remove_schedule ────────────────────────────────────────────────────────

class TestRemoveSchedule:
    def test_remove_nonexistent_returns_false(self):
        sched = CollectionScheduler()
        with patch.object(sched._scheduler, 'remove_job'):
            result = asyncio.run(sched.remove_schedule("nonexistent"))
            assert result is False

    def test_job_not_found_for_nonexistent(self):
        sched = CollectionScheduler()
        result = sched._scheduler.get_job("nonexistent")
        assert result is None


# ── add_schedule with mocked APScheduler ────────────────────────────────────

class TestAddSchedule:
    def test_add_schedule_registers_job(self):
        sched = CollectionScheduler()
        mock_schedule = MagicMock()
        mock_schedule.id = "test-sched-1"
        mock_schedule.cron_expression = "0 8 * * *"
        mock_schedule.timezone = "Asia/Shanghai"

        sched._scheduler.add_job = MagicMock()

        jid = asyncio.run(sched.add_schedule(mock_schedule))

        assert jid == "sched-test-sched-1"
        assert sched._job_ids[mock_schedule.id] == jid
        sched._scheduler.add_job.assert_called_once()

    def test_add_schedule_stores_correct_key(self):
        """_job_ids uses schedule.id as key, sched-{id} as value."""
        sched = CollectionScheduler()
        mock_schedule = MagicMock()
        mock_schedule.id = "my-sched"
        mock_schedule.cron_expression = "0 8 * * *"
        mock_schedule.timezone = "UTC"

        sched._scheduler.add_job = MagicMock()
        asyncio.run(sched.add_schedule(mock_schedule))

        assert "my-sched" in sched._job_ids
        assert sched._job_ids["my-sched"] == "sched-my-sched"


# ── Topic cron validation ───────────────────────────────────────────────────

class TestTopicCronValidation:
    def test_valid_5_field_cron_accepted(self):
        expression = "0 8 * * *"
        parts = expression.strip().split()
        assert len(parts) == 5
        trigger = CronTrigger.from_crontab(expression, "Asia/Shanghai")
        assert trigger is not None

    def test_4_field_cron_has_wrong_count(self):
        expression = "0 8 *"
        parts = expression.strip().split()
        assert len(parts) != 5

    def test_empty_cron_has_wrong_count(self):
        expression = ""
        parts = expression.strip().split()
        assert len(parts) != 5

    def test_6_field_sec_cron_count(self):
        """6-field cron has 6 parts, _load_all only accepts 5-field."""
        expression = "0 0 8 * * *"
        parts = expression.strip().split()
        assert len(parts) == 6
