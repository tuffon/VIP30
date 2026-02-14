import asyncio
import uuid
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from src.db.models import ComparisonJob
from src.services.credits import CreditAlreadyConsumedError, CreditService
from src.services.jobs import (
    InsufficientCreditsError,
    InvalidStateTransitionError,
    JobService,
)


class FakeAsyncSession:
    def __init__(self):
        self.jobs = {}
        self.consumed_job_ids = set()
        self.commits = 0
        self.rollbacks = 0
        self.raise_integrity_on_duplicate = False
        self.pending_consumption = None

    def add(self, obj):
        if isinstance(obj, ComparisonJob):
            self.jobs[obj.id] = obj
        else:
            self.pending_consumption = obj

    async def commit(self):
        self.commits += 1
        if self.pending_consumption is not None:
            job_id = self.pending_consumption.job_id
            if self.raise_integrity_on_duplicate and job_id in self.consumed_job_ids:
                raise IntegrityError("duplicate", {}, Exception("duplicate"))
            self.consumed_job_ids.add(job_id)
            self.pending_consumption = None

    async def refresh(self, _obj):
        return None

    async def rollback(self):
        self.rollbacks += 1
        self.pending_consumption = None

    async def get(self, model, obj_id):
        if model is ComparisonJob:
            return self.jobs.get(obj_id)
        return None

    async def exec(self, _stmt):
        class DummyResult:
            def first(self_nonlocal):
                return None

        return DummyResult()


def _make_job(state=JobService.QUEUED):
    return ComparisonJob(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        state=state,
        progress_percent=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_state_transitions_valid_and_invalid():
    db = FakeAsyncSession()
    job = _make_job(JobService.QUEUED)
    db.jobs[job.id] = job

    asyncio.run(JobService.transition_state(db, job.id, JobService.PARSING))
    assert job.state == JobService.PARSING
    assert job.progress_percent == 10

    asyncio.run(JobService.transition_state(db, job.id, JobService.ANALYZING))
    assert job.state == JobService.ANALYZING
    assert job.progress_percent == 40

    asyncio.run(JobService.transition_state(db, job.id, JobService.WRITING))
    assert job.state == JobService.WRITING
    assert job.progress_percent == 70

    asyncio.run(JobService.transition_state(db, job.id, JobService.COMPLETED))
    assert job.state == JobService.COMPLETED
    assert job.progress_percent == 100

    with pytest.raises(InvalidStateTransitionError):
        asyncio.run(JobService.transition_state(db, job.id, JobService.PARSING))


def test_transition_to_failed_from_non_terminal():
    db = FakeAsyncSession()
    job = _make_job(JobService.ANALYZING)
    db.jobs[job.id] = job

    failed = asyncio.run(JobService.fail_job(db, job.id, "parse_error", "broken payload"))
    assert failed.state == JobService.FAILED
    assert failed.error_code == "parse_error"
    assert failed.completed_at is not None


def test_invalid_skip_transition_queued_to_completed():
    db = FakeAsyncSession()
    job = _make_job(JobService.QUEUED)
    db.jobs[job.id] = job

    with pytest.raises(InvalidStateTransitionError):
        asyncio.run(JobService.transition_state(db, job.id, JobService.COMPLETED))


def test_create_job_requires_credit(monkeypatch):
    db = FakeAsyncSession()
    workspace_id = uuid.uuid4()
    created_by = uuid.uuid4()

    async def zero_balance(_db, _workspace_id):
        return 0

    monkeypatch.setattr(CreditService, "get_balance", staticmethod(zero_balance))

    with pytest.raises(InsufficientCreditsError):
        asyncio.run(JobService.create_job(db, workspace_id, created_by))

    async def enough_balance(_db, _workspace_id):
        return 1

    monkeypatch.setattr(CreditService, "get_balance", staticmethod(enough_balance))

    job = asyncio.run(
        JobService.create_job(
            db,
            workspace_id,
            created_by,
            primary_filename="a.pdf",
            comparison_filename="b.pdf",
        )
    )
    assert job.state == JobService.QUEUED
    assert job.progress_percent == 0


def test_complete_consumes_credit_fail_does_not(monkeypatch):
    db = FakeAsyncSession()

    complete_job = _make_job(JobService.WRITING)
    db.jobs[complete_job.id] = complete_job

    fail_job = _make_job(JobService.PARSING)
    db.jobs[fail_job.id] = fail_job

    calls = {"count": 0}

    async def consume(_db, workspace_id, job_id, amount=1):
        calls["count"] += 1
        assert workspace_id == complete_job.workspace_id
        assert job_id == complete_job.id
        assert amount == 1
        return object()

    monkeypatch.setattr(CreditService, "consume_credit", staticmethod(consume))

    completed = asyncio.run(JobService.complete_job(db, complete_job.id, "s3://result"))
    assert completed.state == JobService.COMPLETED
    assert completed.result_s3_key == "s3://result"
    assert calls["count"] == 1

    failed = asyncio.run(JobService.fail_job(db, fail_job.id, "oops", "worker failed"))
    assert failed.state == JobService.FAILED
    assert calls["count"] == 1


def test_consume_credit_idempotency_duplicate_job_id():
    db = FakeAsyncSession()
    db.raise_integrity_on_duplicate = True
    workspace_id = uuid.uuid4()
    job_id = uuid.uuid4()

    asyncio.run(CreditService.consume_credit(db, workspace_id, job_id, amount=1))
    assert job_id in db.consumed_job_ids

    with pytest.raises(CreditAlreadyConsumedError):
        asyncio.run(CreditService.consume_credit(db, workspace_id, job_id, amount=1))
