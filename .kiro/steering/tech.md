# Technology Stack

## Build System

- **Monorepo Manager**: Turborepo 2.0.0
- **Package Manager**: pnpm 9.0.0 (specified in package.json)
- **Workspace**: pnpm workspace with apps/* and packages/*

## Frontend Stack

- **Framework**: Next.js 14.2.13 with App Router
- **UI Library**: React 18.3.1
- **State Management**: Redux Toolkit 2.2.7 + RTK Query
- **Styling**: TailwindCSS 3.4.13
- **Authentication**: next-auth 4.24.8 (pinned)
- **Testing**: Vitest 1.1.3 + Testing Library

## Backend Stack

- **API Framework**: FastAPI 0.110.0
- **Server**: Gunicorn 21.2.0 + Uvicorn 0.29.0 (ASGI)
- **Job Queue**: RQ 1.15.1 (Redis Queue)
- **LLM Integration**: OpenAI API (gpt-4o-mini default)
- **PDF Processing**: pdfplumber 0.10.0, pypdfium2 4.30.0
- **Data Processing**: pandas 2.2.3, openpyxl 3.1.5
- **Testing**: pytest

## Infrastructure

- **Deployment**: Render.com (frontend, API, worker, Redis)
- **Storage**: Cloudflare R2 (S3-compatible)
- **Cache/Queue**: Redis 5.0.1
- **Vector DB**: Qdrant (for costbook search)

## Common Commands

### Development

```bash
# Install dependencies
pnpm install

# Start all services in dev mode
pnpm dev

# Start specific app
cd apps/vipclaims-saas && pnpm dev
cd apps/vip-parse && source .venv/bin/activate && uvicorn src.api.main:app --reload

# Start worker
cd apps/vip-parse && source .venv/bin/activate && python -m src.worker_parse_helper
```

### Building

```bash
# Build all apps
pnpm build

# Build specific app
turbo run build --filter=vipclaims-saas
```

### Testing

```bash
# Run all tests
pnpm test

# Frontend tests
cd apps/vipclaims-saas && pnpm test

# Backend tests
cd apps/vip-parse && pytest
cd apps/vip-parse && pytest tests/test_xactimate_parser.py -v
```

### Linting & Formatting

```bash
# Lint all
pnpm lint

# Format with Prettier
pnpm prettier --write .
```

### Cleanup

```bash
# Clean build artifacts
pnpm clean
```

## Python Environment

```bash
# Create virtual environment
cd apps/vip-parse
python -m venv .venv

# Activate
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt        # Full
pip install -r requirements-web.txt    # Web service only
pip install -r requirements-worker.txt # Worker only
```

## Docker

```bash
# Start local services (Redis, etc.)
docker-compose up -d

# Build frontend image
docker build -t vip30-frontend .
```

## Environment Variables

Required for local development:

**Frontend (.env.local):**
- NEXT_PUBLIC_API_BASE_URL
- NEXTAUTH_URL
- NEXTAUTH_SECRET
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET

**Backend (.env):**
- OPENAI_API_KEY
- REDIS_URL
- S3_ENDPOINT / CLOUDFLARE_ACCOUNT_ID
- S3_ACCESS_KEY_ID / CLOUDFLARE_R2_ACCESS_KEY_ID
- S3_SECRET_ACCESS_KEY / CLOUDFLARE_R2_SECRET_ACCESS_KEY
- S3_BUCKET / CLOUDFLARE_BUCKET
