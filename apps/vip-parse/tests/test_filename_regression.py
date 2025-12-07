from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

import pytest

from src import tasks

HISTORICAL_DIR = Path(__file__).resolve().parents[1] / "data" / "historical"


def _load_payload(name: str) -> dict:
    with (HISTORICAL_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


class StubS3:
    def __init__(self) -> None:
        self.downloaded: list[tuple[str, str, str]] = []
        self.uploaded: dict[str, bytes] = {}
        self.objects: dict[str, bytes] = {}

    def download_file(self, bucket: str, key: str, dest: str) -> None:  # pragma: no cover - trivial shim
        self.downloaded.append((bucket, key, dest))
        Path(dest).write_bytes(b"pdf-bytes")

    def upload_file(self, filename: str, bucket: str, key: str) -> None:  # pragma: no cover - trivial shim
        self.uploaded[key] = Path(filename).read_bytes()

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:  # noqa: N803
        self.objects[Key] = Body

    def generate_presigned_url(self, _operation: str, *, Params: dict, ExpiresIn: int) -> str:  # noqa: N803
        return f"https://example.com/{Params['Key']}?expires={ExpiresIn}"


class FakeBidComp:
    latest_context: dict | None = None

    def __init__(self, llm_adapter: object | None = None) -> None:  # noqa: D401 - simple stub
        self.llm_adapter = llm_adapter
        self.last_narrative_debug = None
        self.last_narrative_artifact = None

    def run(self, bid_context: dict, job_id: str) -> bytes:  # noqa: D401 - simple stub
        FakeBidComp.latest_context = copy.deepcopy(bid_context)
        return b"fake-xlsx"


def _invoke_worker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    carrier_filename: str | None = None,
    contractor_filename: str | None = None,
) -> tuple[dict, dict]:
    stub_s3 = StubS3()
    monkeypatch.setattr(tasks, "get_s3", lambda: stub_s3)
    monkeypatch.setattr(tasks, "get_bucket", lambda: "unit-test-bucket")

    samples = iter(
        [
            _load_payload("1115_LACHMAN_APEX_2_ROUGH_DRAFT_CAR.json"),
            _load_payload("Estimate SF Structural damage Lachman 4.15.2025.json"),
        ]
    )

    def fake_run_parser_full(_input_path: str, _out_dir: Path) -> dict:
        try:
            return copy.deepcopy(next(samples))
        except StopIteration:  # pragma: no cover - defensive
            return copy.deepcopy(_load_payload("Estimate SF Structural damage Lachman 4.15.2025.json"))

    monkeypatch.setattr(tasks, "_run_parser_full", fake_run_parser_full)
    monkeypatch.setattr(tasks, "BidComp", FakeBidComp)
    FakeBidComp.latest_context = None

    result = tasks.run_bid_comp_keys(
        job_id="job-test",
        carrier_key="uploads/tmp.carrier.pdf",
        contractor_key="uploads/tmp.contractor.pdf",
        template=None,
        carrier_filename=carrier_filename,
        contractor_filename=contractor_filename,
        notify_email=None,
    )
    assert FakeBidComp.latest_context is not None, "BidComp.run should capture the bid context"
    return result, FakeBidComp.latest_context


def test_missing_filenames_fall_back_to_s3_key(monkeypatch: pytest.MonkeyPatch) -> None:
    result, context = _invoke_worker(monkeypatch, carrier_filename=None, contractor_filename=None)

    assert "result_keys" in result  # sanity check that worker completed

    expected_carrier = Path("uploads/tmp.carrier.pdf").name
    expected_contractor = Path("uploads/tmp.contractor.pdf").name

    assert context["carrier_source_filename"] == expected_carrier
    assert context["contractor_source_filename"] == expected_contractor

    carrier_entry, contractor_entry = context["estimates"]
    assert carrier_entry["source_filename"] == expected_carrier
    assert contractor_entry["source_filename"] == expected_contractor

    assert carrier_entry["payload"]["original_filename"] == expected_carrier
    assert contractor_entry["payload"]["original_filename"] == expected_contractor


def test_missing_filenames_emit_warning(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="vip-parse.worker")
    _invoke_worker(monkeypatch, carrier_filename=None, contractor_filename=None)
    warning_messages = [record.getMessage() for record in caplog.records if record.name == "vip-parse.worker"]
    assert any("carrier filename missing" in msg for msg in warning_messages)
    assert any("contractor filename missing" in msg for msg in warning_messages)


def test_enqueue_requires_filenames(monkeypatch: pytest.MonkeyPatch) -> None:
    fastapi = pytest.importorskip("fastapi")  # noqa: F841 - imported for side effect in TestClient
    from fastapi.testclient import TestClient  # type: ignore

    from src.api.main import app
    from src.routes import bid_comp as bid_comp_routes

    class DummyJob:
        def __init__(self) -> None:
            self.id = "job-123"

    class DummyQueue:
        def enqueue(self, *args, **kwargs):  # noqa: ANN001 - FastAPI test helper
            return DummyJob()

    monkeypatch.setattr(bid_comp_routes, "_q", DummyQueue())

    client = TestClient(app)
    resp = client.post(
        "/render/bid-comp/keys",
        json={
            "carrier_key": "uploads/a.pdf",
            "contractor_key": "uploads/b.pdf",
            # filenames intentionally omitted
        },
    )
    assert resp.status_code == 400
    assert "filename" in resp.json().get("detail", "").lower()
