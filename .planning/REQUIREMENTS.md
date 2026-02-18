# Requirements: VIP30 v2.1 Repository Restructure

**Defined:** 2026-02-17
**Core Value:** Reliable end-to-end bid comparison that produces actionable output

## v2.1 Requirements

Requirements for v2.1 release. Repository restructure — clear directory names, split monolith Python into separate packages, rename Render services.

### Directory Restructure

- [ ] **DIR-01**: `apps/vip-parse/` split into `apps/api/` (FastAPI server) and `apps/worker/` (RQ worker)
- [ ] **DIR-02**: `apps/vipclaims-saas/` renamed to `apps/frontend/`
- [ ] **DIR-03**: Parser extracted to `packages/parser/` as its own standalone package (parse/ directory — Xactimate PDF → JSON, zero business logic dependencies)
- [ ] **DIR-04**: Shared Python business logic extracted to `packages/shared-python/` (pipeline, bid_comp, methodology, rules, llm, models)
- [ ] **DIR-05**: Dead code removed — `src/preflight/` module (unused in main application, only referenced by its own test and CLI)

### Package Structure

- [ ] **PKG-01**: `packages/parser/` is a self-contained Python package with its own setup.py/pyproject.toml, installable independently
- [ ] **PKG-02**: `packages/shared-python/` is a Python package importable by both `apps/api/` and `apps/worker/`
- [ ] **PKG-03**: `apps/api/` depends on `packages/shared-python/` (not on `packages/parser/` directly — parser is a worker dependency)
- [ ] **PKG-04**: `apps/worker/` depends on both `packages/parser/` and `packages/shared-python/`
- [ ] **PKG-05**: Dependency direction is strictly: api → shared-python, worker → shared-python + parser. No circular dependencies.

### Import & Reference Cleanup

- [ ] **IMP-01**: All Python imports updated for new package structure (no broken imports)
- [ ] **IMP-02**: Turborepo/pnpm workspace config updated to include new package directories
- [ ] **IMP-03**: Dockerfiles updated for new paths (api and worker each get their own or share updated Dockerfile)
- [ ] **IMP-04**: Frontend package.json name updated from `vipclaims-saas` to `frontend`

### Render Deployment

- [ ] **REN-01**: render.yaml service `vip30-web` renamed to `vip30-api` with updated rootDir, build, and start commands
- [ ] **REN-02**: render.yaml `vip30-frontend` updated with new rootDir/build/start commands for `apps/frontend/`
- [ ] **REN-03**: render.yaml `vip30-worker` updated with new rootDir/build/start commands for `apps/worker/`
- [ ] **REN-04**: `NEXT_PUBLIC_API_BASE_URL` in render.yaml updated from `vip30-web` to `vip30-api` URL
- [ ] **REN-05**: All services deploy and function correctly after restructure (end-to-end verification)

## Validated (v2.0)

All v2.0 requirements completed and shipped. See v2.0 milestone archive for details.

- [x] DATA-01 through DATA-07: Data foundation and methodology
- [x] NARR-01 through NARR-03: Narrative quality
- [x] INTL-01 through INTL-05: Intelligence layer
- [x] MODE-01 through MODE-04: Output modes
- [x] XLSX-01 through XLSX-04: Visual hierarchy
- [x] GATE-01 through GATE-05: Quality gates

## Deferred (v3+)

### Configuration & Tuning

- **DEFER-01**: User-configurable rule thresholds per claim type
- **DEFER-02**: Category name normalization across Xactimate versions
- **DEFER-03**: Template-driven litigation output (minimal LLM text) for maximum reproducibility
- **DEFER-04**: Claim-size-aware rule sensitivity tiers (small/medium/large)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| "Which estimate is better" verdicts (AF-1) | Makes tool an advocate, disqualifiable in litigation |
| Recommendation language (AF-2) | Creates liability exposure |
| Emotional terminology (AF-3) | Destroys neutrality |
| Automated fraud indicators (AF-4) | Defamatory without investigation |
| Confidence scores (AF-5) | False precision, indefensible methodology |
| Side-picking output modes (AF-6) | Credibility collapses if discovered in litigation |
| Editorializing narratives (AF-7) | Hallucination liability in legal contexts |
| Settlement predictions (AF-8) | Dangerous without claims history data |
| Refactoring internal code names (e.g., vip_job → ComparisonJob) | Not in scope for this milestone — structure only |

## Traceability

Which phases cover which requirements. Updated by create-roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DIR-01 | — | Pending |
| DIR-02 | — | Pending |
| DIR-03 | — | Pending |
| DIR-04 | — | Pending |
| DIR-05 | — | Pending |
| PKG-01 | — | Pending |
| PKG-02 | — | Pending |
| PKG-03 | — | Pending |
| PKG-04 | — | Pending |
| PKG-05 | — | Pending |
| IMP-01 | — | Pending |
| IMP-02 | — | Pending |
| IMP-03 | — | Pending |
| IMP-04 | — | Pending |
| REN-01 | — | Pending |
| REN-02 | — | Pending |
| REN-03 | — | Pending |
| REN-04 | — | Pending |
| REN-05 | — | Pending |

**Coverage:**
- v2.1 requirements: 19 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 19

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-17*
