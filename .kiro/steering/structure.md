# Project Structure

## Monorepo Layout

```
VIP30/
├── apps/
│   ├── vipclaims-saas/       # Next.js frontend
│   └── vip-parse/            # FastAPI backend + RQ worker
├── packages/
│   └── shared/               # Shared TypeScript types
└── [config files]
```

## Frontend Structure (apps/vipclaims-saas/)

```
vipclaims-saas/
├── app/                      # Next.js App Router
│   ├── layout.tsx           # Root layout with providers
│   ├── page.tsx             # Landing page
│   ├── bid-comp/            # Bid comparison feature
│   └── api/                 # API routes
├── components/              # React components
│   ├── __tests__/          # Component tests
│   ├── providers/          # Context providers
│   └── [components].tsx
├── redux/                   # Redux state
│   ├── store.ts            # Store configuration
│   ├── features/           # Feature slices
│   └── services/           # RTK Query services
└── public/                  # Static assets
```

## Backend Structure (apps/vip-parse/)

```
vip-parse/
├── src/                     # Main source code
│   ├── api/                # FastAPI app initialization
│   │   ├── main.py        # App entry point
│   │   └── retriever.py   # Costbook search
│   ├── routes/             # API route handlers
│   │   ├── bid_comp.py    # Bid comparison endpoints
│   │   ├── s3.py          # Presigned URL generation
│   │   └── marketing.py   # Marketing endpoints
│   ├── bid_comp/           # Bid comparison engine
│   │   ├── core.py        # Main comparison logic
│   │   ├── export_xlsx.py # XLSX generation
│   │   ├── identity.py    # Category matching
│   │   └── normalize.py   # Data normalization
│   ├── llm/                # LLM integration
│   │   ├── adapter.py     # Adapter interface
│   │   └── templates.py   # Prompt templates
│   ├── integrations/       # External services
│   │   ├── sendgrid_client.py
│   │   └── supabase.py
│   ├── prompts/            # LLM prompt JSON files
│   ├── utils/              # Utilities
│   │   └── s3_client.py   # S3/R2 client
│   ├── workers/            # Worker utilities
│   ├── tasks.py            # RQ job handlers
│   └── main.py             # Module entry for gunicorn
├── parse/                   # PDF parsing modules
│   └── xactimate/          # Xactimate parser
│       ├── parser.py       # Main parser class
│       ├── helpers.py      # Helper functions
│       └── constants.py    # Parser constants
├── tests/                   # Python tests
│   ├── test_xactimate_parser.py
│   ├── test_pdf_preflight.py
│   └── test_bid_comp_normalize.py
├── data/                    # Local data files
└── documents/               # Sample PDFs
```

## Shared Package (packages/shared/)

```
shared/
└── src/
    └── index.ts            # Shared TypeScript types
```

## Naming Conventions

### Files
- **TypeScript/React**: `camelCase.tsx` for components, `camelCase.ts` for modules
- **React Components**: PascalCase exports (e.g., `NavAuth.tsx` exports `NavAuth`)
- **Next.js Pages**: `page.tsx` (App Router convention)
- **Python**: `snake_case.py` for all modules
- **Tests**: `test_*.py` (Python), `*.test.tsx` (TypeScript)

### Functions
- **TypeScript**: `camelCase` (e.g., `handleSubmit`, `makeStore`)
- **React Components**: `PascalCase` (e.g., `LandingSignupForm`)
- **Python**: `snake_case` (e.g., `normalize_money`, `get_bucket`)

### Variables
- **TypeScript**: `camelCase` for variables, `UPPER_CASE` for constants
- **Python**: `snake_case`, leading underscore for private (e.g., `_redis_url`)

### Types
- **TypeScript**: `PascalCase` for types and interfaces
- **Python**: Type hints using `typing` module

## Where to Add New Code

### New Backend Feature
1. Create route handler: `apps/vip-parse/src/routes/{feature}.py`
2. Create business logic: `apps/vip-parse/src/{feature}/`
3. Register router in: `apps/vip-parse/src/api/main.py`

### New Frontend Feature
1. Create page: `apps/vipclaims-saas/app/{feature}/page.tsx`
2. Create components: `apps/vipclaims-saas/components/{ComponentName}.tsx`
3. Add Redux slice (if needed): `apps/vipclaims-saas/redux/features/{feature}Slice.ts`

### New Background Job
1. Add job handler to: `apps/vip-parse/src/tasks.py`
2. Enqueue from route in: `apps/vip-parse/src/routes/`

### New Parser
1. Create parser module: `apps/vip-parse/parse/{format_name}/`
2. Export from: `apps/vip-parse/parse/{format_name}/__init__.py`

### New LLM Prompt
1. Create template: `apps/vip-parse/src/prompts/{template_name}.json`

### Utilities
- **Python**: `apps/vip-parse/src/utils/{utility}.py`
- **TypeScript**: `packages/shared/src/{utility}.ts`

### Tests
- **TypeScript**: `apps/vipclaims-saas/components/__tests__/{Component}.test.tsx`
- **Python**: `apps/vip-parse/tests/test_{module}.py`

## Import Path Aliases

- `@/*` → App root (Next.js apps)
- `@shared/*` → `packages/shared/*`

## Special Directories

- `.planning/` - GSD planning documents (committed)
- `.next/` - Next.js build output (not committed)
- `.venv/` - Python virtual environments (not committed)
- `.pnpm-store/` - pnpm package cache (not committed)
- `node_modules/` - npm dependencies (not committed)
