# Plan 03-02 Summary: Job Endpoints and Worker Integration

## Status

Completed on 2026-02-14.

## Scope Executed

- Added authenticated jobs router in `apps/vip-parse/src/routes/jobs.py`:
  - `POST /jobs` create job with workspace credit check and enqueue worker
  - `GET /jobs/{job_id}` fetch workspace-scoped status/progress and optional presigned download URL
  - `POST /jobs/{job_id}/retry` create new job from failed job inputs
  - `GET /jobs` list workspace jobs with pagination and total count
- Registered jobs router in `apps/vip-parse/src/api/main.py`.
- Integrated worker lifecycle callbacks in `apps/vip-parse/src/tasks.py`:
  - Added optional `db_job_id` parameter to `run_bid_comp_keys` for DB-linked jobs
  - Added progress updates with state transitions during processing stages
  - On success, calls `JobService.complete_job(...)` (credit consumption path)
  - On failure, calls `JobService.fail_job(...)` and re-raises for RQ failure semantics
  - Maintained backward compatibility for legacy invocations without `db_job_id`
- Added integration tests in `apps/vip-parse/tests/test_routes_jobs.py`.

## Requirement Mapping

- JOB-02: Job progress/state exposed via `GET /jobs/{job_id}`
- JOB-03: Failure state stores `error_code` and `error_message` through `fail_job`
- JOB-04: Retry endpoint creates a new job from failed job inputs
- JOB-06: Job creation/retry blocked when workspace has insufficient credits
- CRED-03: Credits consumed only on successful completion path

## Verification Evidence

- Imports:
  - `python -c "from src.routes.jobs import jobs_router; print('jobs_router imported OK')"`
  - `python -c "from src.tasks import run_bid_comp_keys; print('tasks.py imports OK')"`
- Syntax:
  - `python -m py_compile src/routes/jobs.py src/tasks.py src/api/main.py tests/test_routes_jobs.py`
- Route tests:
  - `python -m pytest tests/test_routes_jobs.py -v --tb=short`
  - Result: `5 passed`
- Legacy compatibility smoke check:
  - `POST /render/bid-comp/keys` still returns `202` with mocked queue (`legacy_bid_comp_keys_ok`)

## Notes

- Test output includes deprecation warnings unrelated to functional correctness (existing `datetime.utcnow()` and framework deprecation notices).
