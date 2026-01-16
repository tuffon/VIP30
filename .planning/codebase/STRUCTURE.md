# Codebase Structure

**Analysis Date:** 2026-01-15

## Directory Layout

```
VIP30/
├── apps/
│   ├── vipclaims-saas/       # Next.js 14 frontend
│   │   ├── app/              # App Router pages and API routes
│   │   ├── components/       # React components
│   │   ├── redux/            # Redux store, slices, RTK Query services
│   │   └── public/           # Static assets
│   └── vip-parse/            # Python FastAPI backend + worker
│       ├── src/              # Main source code
│       │   ├── api/          # FastAPI app and retriever
│       │   ├── routes/       # API route handlers
│       │   ├── bid_comp/     # Bid comparison engine
│       │   ├── llm/          # LLM adapters and templates
│       │   ├── integrations/ # External service clients
│       │   ├── preflight/    # PDF preflight analysis
│       │   ├── prompts/      # LLM prompt templates (JSON)
│       │   ├── utils/        # Utility modules (S3 client)
│       │   ├── workers/      # Worker utilities
│       │   └── tasks.py      # RQ job handlers
│       ├── parse/            # PDF parsing modules
│       │   └── xactimate/    # Xactimate parser
│       ├── tests/            # Python tests
│       ├── data/             # Local data files
│       ├── documents/        # Sample documents
│       └── embeddings/       # Embedding scripts
├── packages/
│   └── shared/               # Shared TypeScript package
│       └── src/              # Shared types and constants
├── docker/                   # Docker utilities
├── docs/                     # Documentation
├── assets/                   # Project assets
├── package.json              # Monorepo root package
├── pnpm-workspace.yaml       # Workspace configuration
├── turbo.json                # Turborepo pipeline config
├── Dockerfile                # Docker build
├── docker-compose.yml        # Local dev services
└── render.yaml               # Render.com deployment config
```

## Directory Purposes

**apps/vipclaims-saas/:**
- Purpose: Next.js frontend SaaS application
- Contains: Pages, components, Redux state, auth config
- Key files: `app/layout.tsx`, `app/page.tsx`, `app/bid-comp/page.tsx`

**apps/vipclaims-saas/app/:**
- Purpose: Next.js App Router pages and API routes
- Contains: Page components, route handlers, layouts
- Key files: `layout.tsx` (root layout), `page.tsx` (landing), `bid-comp/page.tsx`

**apps/vipclaims-saas/components/:**
- Purpose: Reusable React components
- Contains: UI components, providers
- Key files: `providers/AppProviders.tsx`, `NavAuth.tsx`, `brand.ts`

**apps/vipclaims-saas/redux/:**
- Purpose: Redux state management
- Contains: Store config, feature slices, RTK Query services
- Key files: `store.ts`, `features/uiSlice.ts`, `services/api.ts`

**apps/vip-parse/src/:**
- Purpose: Main Python backend source
- Contains: API, routes, business logic, integrations
- Key files: `main.py`, `tasks.py`, `worker_parse_helper.py`

**apps/vip-parse/src/api/:**
- Purpose: FastAPI application and core endpoints
- Contains: App initialization, retriever for costbook search
- Key files: `main.py`, `retriever.py`

**apps/vip-parse/src/routes/:**
- Purpose: API route handlers organized by feature
- Contains: Bid comp routes, S3 upload routes, marketing routes
- Key files: `bid_comp.py`, `s3.py`, `marketing.py`

**apps/vip-parse/src/bid_comp/:**
- Purpose: Bid comparison engine
- Contains: Core comparison logic, XLSX export, matchers, taxonomy
- Key files: `core.py`, `export_xlsx.py`, `identity.py`, `normalize.py`

**apps/vip-parse/src/llm/:**
- Purpose: LLM integration layer
- Contains: Adapter interface, OpenAI implementation, template registry
- Key files: `adapter.py`, `templates.py`

**apps/vip-parse/src/integrations/:**
- Purpose: External service client wrappers
- Contains: SendGrid email client, Supabase client
- Key files: `sendgrid_client.py`, `supabase.py`

**apps/vip-parse/src/prompts/:**
- Purpose: LLM prompt templates
- Contains: JSON prompt definitions
- Key files: `bid_comp_summary.json`, `explain_bid_comp.json`

**apps/vip-parse/src/utils/:**
- Purpose: Utility modules
- Contains: S3/R2 client wrapper
- Key files: `s3_client.py`

**apps/vip-parse/parse/:**
- Purpose: PDF parsing modules
- Contains: Xactimate parser, BNI cost extraction
- Key files: `xactimate/__init__.py`, `xactimate/parser.py`

**apps/vip-parse/parse/xactimate/:**
- Purpose: Xactimate estimate PDF parser
- Contains: Main parser class, helpers, constants, text extraction
- Key files: `parser.py` (main), `helpers.py`, `constants.py`, `visible_text.py`

**apps/vip-parse/tests/:**
- Purpose: Python test suite
- Contains: Unit and integration tests
- Key files: `test_xactimate_parser.py`, `test_pdf_preflight.py`, `test_bid_comp_normalize.py`

**packages/shared/:**
- Purpose: Shared TypeScript types and utilities
- Contains: Type exports, version constant
- Key files: `src/index.ts`

## Key File Locations

**Entry Points:**
- `apps/vipclaims-saas/app/layout.tsx`: Frontend root layout with providers
- `apps/vip-parse/src/main.py`: Python module entry for gunicorn
- `apps/vip-parse/src/api/main.py`: FastAPI app initialization
- `apps/vip-parse/src/tasks.py`: RQ worker job handlers

**Configuration:**
- `package.json`: Monorepo scripts and dev dependencies
- `pnpm-workspace.yaml`: Workspace package locations
- `turbo.json`: Turborepo pipeline configuration
- `render.yaml`: Render.com deployment configuration
- `apps/vipclaims-saas/next.config.mjs`: Next.js configuration
- `apps/vipclaims-saas/tailwind.config.ts`: Tailwind CSS configuration
- `apps/vip-parse/requirements.txt`: Python dependencies (full)
- `apps/vip-parse/requirements-web.txt`: Python dependencies (web service)
- `apps/vip-parse/requirements-worker.txt`: Python dependencies (worker)
- `apps/vip-parse/gunicorn.conf.py`: Gunicorn server configuration

**Core Logic:**
- `apps/vip-parse/src/bid_comp/core.py`: BidComp comparison engine
- `apps/vip-parse/parse/xactimate/parser.py`: Xactimate PDF parser
- `apps/vip-parse/src/tasks.py`: Background job processing

**Testing:**
- `apps/vip-parse/tests/`: Python tests
- `apps/vipclaims-saas/components/__tests__/`: React component tests

## Naming Conventions

**Files:**
- Python: `snake_case.py` (e.g., `bid_comp.py`, `s3_client.py`)
- TypeScript/React: `PascalCase.tsx` for components (e.g., `NavAuth.tsx`), `camelCase.ts` for modules (e.g., `store.ts`, `uiSlice.ts`)
- Next.js pages: `page.tsx` in directory-based routing

**Directories:**
- Python packages: `snake_case` (e.g., `bid_comp`, `xactimate`)
- Next.js app routes: `kebab-case` (e.g., `bid-comp`, `pdf-to-esx`)
- React components: `PascalCase` for component dirs, `camelCase` or `kebab-case` for utilities

## Where to Add New Code

**New Feature (Backend):**
- Route handler: `apps/vip-parse/src/routes/{feature}.py`
- Business logic: `apps/vip-parse/src/{feature}/` directory
- Register router in: `apps/vip-parse/src/api/main.py`

**New Feature (Frontend):**
- Page: `apps/vipclaims-saas/app/{feature}/page.tsx`
- API route: `apps/vipclaims-saas/app/api/{feature}/route.ts`
- Component: `apps/vipclaims-saas/components/{ComponentName}.tsx`

**New Component/Module:**
- React component: `apps/vipclaims-saas/components/{ComponentName}.tsx`
- Python module: `apps/vip-parse/src/{module_name}.py` or `apps/vip-parse/src/{module_name}/`

**New Parser:**
- Parser module: `apps/vip-parse/parse/{format_name}/`
- Export from: `apps/vip-parse/parse/{format_name}/__init__.py`

**Utilities:**
- Python helpers: `apps/vip-parse/src/utils/{utility}.py`
- TypeScript helpers: `packages/shared/src/{utility}.ts`

**New Integration:**
- External service client: `apps/vip-parse/src/integrations/{service}_client.py`

**New LLM Prompt:**
- Prompt template: `apps/vip-parse/src/prompts/{template_name}.json`

**New Redux Slice:**
- Feature slice: `apps/vipclaims-saas/redux/features/{feature}Slice.ts`
- RTK Query endpoint: `apps/vipclaims-saas/redux/services/api.ts` (extend existing)

**New Background Job:**
- Job handler: Add function to `apps/vip-parse/src/tasks.py`
- Enqueue from route in: `apps/vip-parse/src/routes/`

## Special Directories

**.planning/:**
- Purpose: GSD planning and codebase analysis documents
- Generated: By GSD tools
- Committed: Yes

**.next/:**
- Purpose: Next.js build output and cache
- Generated: Yes (build process)
- Committed: No

**.venv/ and apps/vip-parse/.venv/:**
- Purpose: Python virtual environments
- Generated: Yes
- Committed: No

**.pnpm-store/:**
- Purpose: pnpm package cache
- Generated: Yes
- Committed: No

**node_modules/:**
- Purpose: npm/pnpm dependencies
- Generated: Yes
- Committed: No

**apps/vip-parse/data/:**
- Purpose: Local data files for development/testing
- Generated: Mixed
- Committed: Selective

**apps/vip-parse/documents/:**
- Purpose: Sample PDF documents for testing
- Generated: No
- Committed: Selective

---

*Structure analysis: 2026-01-15*
