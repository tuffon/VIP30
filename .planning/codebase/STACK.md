# Technology Stack

**Analysis Date:** 2026-01-15

## Languages

**Primary:**
- TypeScript 5.6.3 - Next.js frontend (`apps/vipclaims-saas/`)
- Python 3.x - Backend API and worker (`apps/vip-parse/`)

**Secondary:**
- JavaScript - Configuration files and scripts

## Runtime

**Frontend Environment:**
- Node.js 20 (specified in `render.yaml` and `Dockerfile`)
- pnpm 9.0.0 (specified in root `package.json` via `packageManager` field)
- Lockfile: pnpm-lock.yaml (present)

**Backend Environment:**
- Python 3.x with pip
- Virtual environment: `.venv/` (project-level and per-app)
- Gunicorn + Uvicorn (ASGI worker)

## Frameworks

**Frontend Core:**
- Next.js 14.2.13 - React framework with App Router
- React 18.3.1 - UI library
- React DOM 18.3.1 - DOM bindings

**State Management:**
- Redux Toolkit 2.2.7 - Global state management
- React Redux 9.1.2 - Redux bindings
- TanStack React Query 5.59.0 - Server state/data fetching

**Backend Core:**
- FastAPI 0.110.0 - Python API framework
- Uvicorn 0.29.0 - ASGI server
- Gunicorn 21.2.0 - Process manager
- RQ 1.15.1 - Redis queue for background jobs

**Styling:**
- TailwindCSS 3.4.13 - Utility-first CSS
- PostCSS 8.4.47 - CSS processing
- Autoprefixer 10.4.20 - CSS vendor prefixes

**Testing:**
- Vitest 1.1.3 - Frontend test runner
- Testing Library React 16.0.1 - React testing utilities
- Testing Library Jest DOM 6.5.0 - DOM matchers
- jsdom 25.0.1 - DOM environment for tests
- pytest - Python testing

**Build/Dev:**
- Turborepo 2.0.0 - Monorepo build orchestration
- ESLint 8.57.0 - JavaScript/TypeScript linting
- Prettier 3.3.3 - Code formatting
- rimraf 6.0.1 - Cross-platform file removal

## Key Dependencies

**Critical Frontend:**
- `next-auth` 4.24.8 - Authentication (pinned via pnpm override)
- `@vip/shared` workspace:* - Internal shared package

**Critical Backend:**
- `openai` 1.12.0 - LLM API client for embeddings and chat
- `qdrant-client` 1.15.1 - Vector database client
- `boto3` 1.35.24 - AWS S3-compatible storage (Cloudflare R2)
- `redis` 5.0.1 - Job queue backend
- `pandas` 2.2.3 - Data manipulation
- `openpyxl` 3.1.5 - Excel file generation
- `pdfplumber` 0.10.0 - PDF text extraction
- `pypdfium2` 4.30.0 - PDF rendering
- `rapidfuzz` 3.9.7 - Fuzzy string matching
- `httpx` 0.27.2 - HTTP client
- `lz4` 4.3.3 - Compression

**Infrastructure:**
- `python-dotenv` 1.0.0 - Environment variable loading
- `email-validator` 2.2.0 - Email validation
- `networkx` 3.2.0 - DAG execution for orchestration
- `python-multipart` 0.0.9 - Multipart form handling

## Configuration

**TypeScript:**
- Base config: `tsconfig.base.json`
- Target: ES2022
- Module: ESNext with Bundler resolution
- Strict mode enabled
- Path aliases: `@/*` for local imports, `@shared/*` for shared package

**Frontend TypeScript:**
- Config: `apps/vipclaims-saas/tsconfig.json`
- Extends base config
- JSX preserve mode
- Next.js plugin enabled

**Build Orchestration:**
- Config: `turbo.json`
- Pipeline: build, dev, lint, test, clean
- Output caching for `.next/**` and `dist/**`

**Monorepo Workspace:**
- Config: `pnpm-workspace.yaml`
- Packages: `apps/*`, `packages/*`

**Linting:**
- Config: `.eslintrc.cjs`
- Parser: @typescript-eslint/parser
- Extends: eslint:recommended, @typescript-eslint/recommended

**Formatting:**
- Config: `.prettierrc`
- Double quotes, semicolons, 100 char width

**Tailwind:**
- Config: `apps/vipclaims-saas/tailwind.config.ts`
- Content paths: `./app/**/*.{ts,tsx}`, `./components/**/*.{ts,tsx}`
- Custom brand colors defined

## Platform Requirements

**Development:**
- Node.js 20+
- pnpm 9.0.0+
- Python 3.10+ (inferred from dependencies)
- Docker (optional, for local development via docker-compose)

**Production Deployment:**
- Render.com (specified in `render.yaml`)
  - `vip30-frontend`: Node.js web service (Next.js)
  - `vip30-web`: Python web service (FastAPI)
  - `vip30-worker`: Python worker service (RQ)
  - `vip30-redis`: Managed Redis instance

**Docker:**
- Base image: `node:20-bullseye`
- Multi-stage build for dev target
- Volume mounts for pnpm store and node_modules

## Environment Variables

**Required for Frontend:**
- `NEXT_PUBLIC_API_BASE_URL` - Backend API URL
- `NEXTAUTH_URL` - NextAuth callback URL
- `NEXTAUTH_SECRET` - NextAuth secret key
- `GOOGLE_CLIENT_ID` - OAuth client ID
- `GOOGLE_CLIENT_SECRET` - OAuth client secret

**Required for Backend:**
- `OPENAI_API_KEY` - OpenAI API key for LLM
- `QDRANT_API_KEY` - Qdrant vector DB key
- `QDRANT_URL` - Qdrant endpoint
- `REDIS_URL` - Redis connection string
- `S3_ENDPOINT` / `CLOUDFLARE_ACCOUNT_ID` - Storage endpoint
- `S3_ACCESS_KEY_ID` / `CLOUDFLARE_R2_ACCESS_KEY_ID` - Storage credentials
- `S3_SECRET_ACCESS_KEY` / `CLOUDFLARE_R2_SECRET_ACCESS_KEY` - Storage secret
- `S3_BUCKET` / `CLOUDFLARE_BUCKET` - Storage bucket name

**Optional:**
- `SENDGRID_API_KEY` - Email notifications
- `SENDGRID_FROM_EMAIL` - Sender email
- `SUPABASE_URL` - Marketing signups database
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase admin key
- `DOWNSTREAM_API_URL` - Webhook for job completion
- `LOG_LEVEL` - Logging verbosity (default: INFO)
- `PARSE_CONCURRENCY` - Worker concurrency (default: 1)
- `OPENAI_MODEL` - LLM model (default: gpt-4o-mini)

---

*Stack analysis: 2026-01-15*
