# Roadmap: VIP30

## Milestones

- ✅ **v1.0.1 Professional Adjuster Narratives** - Phases 1-8 (shipped 2026-02-09)
- ✅ **v1.1 MVP Launch** - Phases 1-4 (shipped 2026-02-14)
- ✅ **v1.2 Launch Ready** - Phases 5-8 (shipped 2026-02-17)
- ✅ **v2.0 Analytical Intelligence** - Phases 9-12 (shipped 2026-02-17)
- 🚧 **v2.1 Repository Restructure** - Phases 13-15 (in progress)

## Phases

- [ ] **Phase 13: Package Extraction** - Extract parser and shared-python as standalone packages, remove dead code
- [ ] **Phase 14: Directory Split & Config** - Split api/worker, rename frontend, update all imports and build configs
- [ ] **Phase 15: Render Deployment** - Update render.yaml service names and paths, end-to-end verification

## Phase Details

### 🚧 v2.1 Repository Restructure

**Milestone Goal:** Clean up repository organization — clear directory names for API, worker, frontend, and shared code. Rename Render services to match.

### Phase 13: Package Extraction
**Goal**: Extract parser and shared Python business logic into standalone packages, remove dead code
**Depends on**: v2.0 (existing codebase)
**Requirements**: DIR-03, DIR-04, DIR-05, PKG-01, PKG-02, PKG-05
**Success Criteria** (what must be TRUE):
  1. `packages/parser/` exists as a standalone Python package with pyproject.toml, installable independently
  2. `packages/shared-python/` exists as a Python package containing pipeline, bid_comp, methodology, rules, llm modules
  3. `src/preflight/` dead code is removed
  4. Parser package has zero dependencies on business logic (unidirectional: parser → JSON → business logic)
  5. Dependency direction is strictly enforced: no circular imports between packages
**Research**: Unlikely (Python packaging, established patterns)
**Plans**: 2 plans in 2 waves
  - 13-01: Parser package extraction + preflight cleanup (Wave 1)
  - 13-02: Shared-python package extraction + import updates (Wave 2)

### Phase 14: Directory Split & Config
**Goal**: Split monolith into api/worker apps, rename frontend, update all imports and build configs
**Depends on**: Phase 13 (packages must exist before apps can reference them)
**Requirements**: DIR-01, DIR-02, PKG-03, PKG-04, IMP-01, IMP-02, IMP-03, IMP-04
**Success Criteria** (what must be TRUE):
  1. `apps/api/` contains only FastAPI server code, depends on shared-python (not parser directly)
  2. `apps/worker/` contains only RQ worker code, depends on both shared-python and parser
  3. `apps/frontend/` contains the Next.js app (renamed from vipclaims-saas)
  4. All Python imports resolve correctly with no broken imports
  5. Turborepo/pnpm workspace config includes new package directories
  6. Dockerfiles updated for new paths
  7. Frontend package.json name updated to `frontend`
**Research**: Unlikely (file moves, import updates, config edits)

### Phase 15: Render Deployment
**Goal**: Update Render service configuration and verify end-to-end deployment
**Depends on**: Phase 14 (all code must be in final locations)
**Requirements**: REN-01, REN-02, REN-03, REN-04, REN-05
**Success Criteria** (what must be TRUE):
  1. render.yaml `vip30-web` renamed to `vip30-api` with correct rootDir, build, and start commands
  2. render.yaml `vip30-frontend` updated for `apps/frontend/` paths
  3. render.yaml `vip30-worker` updated for `apps/worker/` paths
  4. `NEXT_PUBLIC_API_BASE_URL` references `vip30-api` URL
  5. All services deploy and function correctly (upload → parse → compare → download works)
**Research**: Unlikely (render.yaml edits, known deployment platform)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|---------------|--------|-----------|
| 13. Package Extraction | 0/2 | Not started | - |
| 14. Directory Split & Config | 0/0 | Not started | - |
| 15. Render Deployment | 0/0 | Not started | - |

---
*Last updated: 2026-02-17 — Phase 13 planned*
