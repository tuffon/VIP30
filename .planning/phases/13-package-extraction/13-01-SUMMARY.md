# 13-01 Summary — Parser Package Extraction + Preflight Cleanup

## Scope Executed
- Phase: 13 (Package Extraction)
- Plan: 13-01
- Requirements addressed:
  - DIR-03 (parser extracted to standalone package)
  - DIR-05 (preflight dead code removed)
  - PKG-01 (parser package installable metadata)
  - PKG-05 (parser isolated from business logic)

## Changes Implemented

### 1. Created standalone parser package
- Added `packages/parser/pyproject.toml` with package metadata for `vip-parser`.
- Added package layout under `packages/parser/vip_parser/`.
- Moved parser code from `apps/vip-parse/parse/` to:
  - `packages/parser/vip_parser/__init__.py`
  - `packages/parser/vip_parser/bni_extract_unit_costs.py`
  - `packages/parser/vip_parser/parse_dir.py`
  - `packages/parser/vip_parser/xactimate_rough_draft_parse.py`
  - `packages/parser/vip_parser/xactimate/*`
- Removed original `apps/vip-parse/parse/` directory.

### 2. Updated parser import sites
Replaced `parse.xactimate` imports with `vip_parser.xactimate` in:
- `apps/vip-parse/src/tasks.py`
- `apps/vip-parse/src/worker_parse_helper.py`
- `apps/vip-parse/src/api/render.py`
- `apps/vip-parse/tests/test_xactimate_parser.py`
- `apps/vip-parse/tests/test_visible_text.py`

### 3. Updated dependency manifests
Added editable parser dependency:
- `apps/vip-parse/requirements.txt`
- `apps/vip-parse/requirements-web.txt`
- `apps/vip-parse/requirements-worker.txt`

Entry added:
- `-e ../../packages/parser`

### 4. Removed dead preflight module
Deleted:
- `apps/vip-parse/src/preflight/` (all module files)
- `apps/vip-parse/tests/test_pdf_preflight.py`

## Verification

### Structural checks
- `packages/parser/pyproject.toml` exists.
- `packages/parser/vip_parser/xactimate/parser.py` exists.
- `apps/vip-parse/parse/` removed.
- `apps/vip-parse/src/preflight/` removed.
- `apps/vip-parse/tests/test_pdf_preflight.py` removed.

### Import checks
- No remaining `from parse...`/`parse.xactimate` imports in app/test code.
- Positive matches confirmed for `from vip_parser...` in src/tests.

### Test validation
Executed:
- `PYTHONPATH=.:../../packages/parser pytest -q tests/test_xactimate_parser.py tests/test_visible_text.py`
  - Result: pass
- `PYTHONPATH=.:../../packages/parser pytest -q`
  - Result: `216 passed`

Note: local editable install command (`pip install -e ../../packages/parser`) failed in this WSL mount due filesystem permission constraints creating `*.egg-info`; runtime/test verification was completed via `PYTHONPATH` and package structure is valid for normal Linux CI/deploy environments.

## Outcome
Plan 13-01 complete. Parser is now a standalone package, app/test imports are updated, and dead preflight code is removed.
