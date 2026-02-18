import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from src.api.main import app
from vip_shared.db.models import ComparisonJob, User
from src.dependencies.auth import require_auth
from src.dependencies.database import get_db
from src.routes import jobs as jobs_route
from vip_shared.services.jobs import InsufficientCreditsError, JobService


class _Result:
    def __init__(self, *, one_value=None, all_values=None):
        self._one_value = one_value
        self._all_values = all_values or []

    def one(self):
        return self._one_value

    def all(self):
        return self._all_values


class FakeDB:
    def __init__(self):
        self.jobs = {}
        self._list_jobs = []
        self._list_total = 0
        self._exec_calls = 0

    def add(self, obj):
        if isinstance(obj, ComparisonJob):
            self.jobs[obj.id] = obj

    async def commit(self):
        return None

    async def refresh(self, _obj):
        return None

    async def get(self, model, obj_id):
        if model is ComparisonJob:
            return self.jobs.get(obj_id)
        return None

    async def exec(self, _stmt):
        self._exec_calls += 1
        if self._exec_calls == 1:
            return _Result(one_value=self._list_total)
        return _Result(all_values=self._list_jobs)


class FakeQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return type("RQJob", (), {"id": "rq-123"})()


def _make_user(workspace_id):
    return User(id=uuid.uuid4(), workspace_id=workspace_id, email="user@test.com")


def _make_job(workspace_id, state=JobService.QUEUED):
    return ComparisonJob(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        created_by=uuid.uuid4(),
        state=state,
        progress_percent=0,
        primary_s3_key="carrier-key",
        comparison_s3_key="contractor-key",
        primary_filename="carrier.pdf",
        comparison_filename="contractor.pdf",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_post_jobs_success_and_insufficient_credits(monkeypatch):
    fake_db = FakeDB()
    workspace_id = uuid.uuid4()
    user = _make_user(workspace_id)
    queue = FakeQueue()
    monkeypatch.setattr(jobs_route, "_q", queue)

    async def auth_ok():
        return user

    async def db_override():
        yield fake_db

    async def create_ok(**_kwargs):
        return _make_job(workspace_id, JobService.QUEUED)

    app.dependency_overrides[require_auth] = auth_ok
    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(JobService, "create_job", staticmethod(create_ok))

    with TestClient(app) as client:
        resp = client.post(
            "/jobs",
            json={"carrier_key": "carrier-key", "contractor_key": "contractor-key"},
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "queued"
        assert len(queue.calls) == 1

    async def create_no_credit(**_kwargs):
        raise InsufficientCreditsError("insufficient_credits")

    monkeypatch.setattr(JobService, "create_job", staticmethod(create_no_credit))
    with TestClient(app) as client:
        resp = client.post(
            "/jobs",
            json={"carrier_key": "carrier-key", "contractor_key": "contractor-key"},
        )
        assert resp.status_code == 402
        assert resp.json()["detail"]["error"] == "insufficient_credits"

    app.dependency_overrides = {}


def test_post_jobs_unauthenticated(monkeypatch):
    fake_db = FakeDB()

    async def db_override():
        yield fake_db

    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(jobs_route, "_q", FakeQueue())

    with TestClient(app) as client:
        resp = client.post(
            "/jobs",
            json={"carrier_key": "carrier-key", "contractor_key": "contractor-key"},
        )
        assert resp.status_code == 401

    app.dependency_overrides = {}


def test_get_job_status_and_not_found_and_download_url(monkeypatch):
    fake_db = FakeDB()
    workspace_id = uuid.uuid4()
    user = _make_user(workspace_id)
    completed_job = _make_job(workspace_id, JobService.COMPLETED)
    completed_job.result_s3_key = "results/file.xlsx"
    completed_job.completed_at = datetime.utcnow()

    async def auth_ok():
        return user

    async def db_override():
        yield fake_db

    async def get_job_ok(_db, _job_id, workspace_id=None):
        if workspace_id != user.workspace_id:
            return None
        return completed_job

    class DummyS3:
        def generate_presigned_url(self, *_args, **_kwargs):
            return "https://example.com/download"

    app.dependency_overrides[require_auth] = auth_ok
    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(JobService, "get_job", staticmethod(get_job_ok))
    monkeypatch.setattr(jobs_route, "get_s3", lambda: DummyS3())
    monkeypatch.setattr(jobs_route, "get_bucket", lambda: "bucket")

    with TestClient(app) as client:
        resp = client.get(f"/jobs/{completed_job.id}")
        assert resp.status_code == 200
        assert resp.json()["download_url"] == "https://example.com/download"

    async def get_job_none(_db, _job_id, workspace_id=None):
        return None

    monkeypatch.setattr(JobService, "get_job", staticmethod(get_job_none))
    with TestClient(app) as client:
        resp = client.get(f"/jobs/{completed_job.id}")
        assert resp.status_code == 404

    app.dependency_overrides = {}


def test_retry_job_paths(monkeypatch):
    fake_db = FakeDB()
    workspace_id = uuid.uuid4()
    user = _make_user(workspace_id)
    failed_job = _make_job(workspace_id, JobService.FAILED)
    queue = FakeQueue()
    monkeypatch.setattr(jobs_route, "_q", queue)

    async def auth_ok():
        return user

    async def db_override():
        yield fake_db

    async def get_failed(_db, _job_id, workspace_id=None):
        if workspace_id != user.workspace_id:
            return None
        return failed_job

    async def create_new(**_kwargs):
        return _make_job(workspace_id, JobService.QUEUED)

    app.dependency_overrides[require_auth] = auth_ok
    app.dependency_overrides[get_db] = db_override
    monkeypatch.setattr(JobService, "get_job", staticmethod(get_failed))
    monkeypatch.setattr(JobService, "create_job", staticmethod(create_new))

    with TestClient(app) as client:
        resp = client.post(f"/jobs/{failed_job.id}/retry")
        assert resp.status_code == 202
        assert len(queue.calls) == 1

    failed_job.state = JobService.ANALYZING
    with TestClient(app) as client:
        resp = client.post(f"/jobs/{failed_job.id}/retry")
        assert resp.status_code == 400

    failed_job.state = JobService.FAILED

    async def create_no_credit(**_kwargs):
        raise InsufficientCreditsError("insufficient_credits")

    monkeypatch.setattr(JobService, "create_job", staticmethod(create_no_credit))
    with TestClient(app) as client:
        resp = client.post(f"/jobs/{failed_job.id}/retry")
        assert resp.status_code == 402

    app.dependency_overrides = {}


def test_list_jobs_pagination_and_workspace_isolation(monkeypatch):
    fake_db = FakeDB()
    workspace_id = uuid.uuid4()
    user = _make_user(workspace_id)
    job1 = _make_job(workspace_id, JobService.PARSING)
    job2 = _make_job(workspace_id, JobService.WRITING)
    fake_db._list_jobs = [job2, job1]
    fake_db._list_total = 2

    async def auth_ok():
        return user

    async def db_override():
        yield fake_db

    app.dependency_overrides[require_auth] = auth_ok
    app.dependency_overrides[get_db] = db_override

    with TestClient(app) as client:
        resp = client.get("/jobs?page=1&per_page=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 2
        assert len(body["jobs"]) == 2
        assert all(item["id"] in {str(job1.id), str(job2.id)} for item in body["jobs"])

    app.dependency_overrides = {}
