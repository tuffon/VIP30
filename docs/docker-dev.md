# Running vipclaims-saas in Docker

## Prerequisites
- Docker Desktop 4.0+ (or any recent Docker Engine with Compose v2)
- Optional: backend API reachable at `http://host.docker.internal:4000/health`

## First-time setup
```bash
docker compose build vipclaims-web
```

## Start the dev server
```bash
docker compose up vipclaims-web
```

This command will:
- Install workspace dependencies inside the container (using pnpm)
- Start `pnpm --filter vipclaims-saas dev` on port 3000
- Bind mount the repo so file changes on the host trigger hot reloads

Access the app at <http://localhost:3000>.

## Environment variables
- The container exports `NEXT_PUBLIC_API_BASE_URL=http://host.docker.internal:4000` by default
- Override via `.env.local` or by editing `docker-compose.yml`

## Stopping and cleaning up
```bash
docker compose down
```

If dependencies get out of sync, remove the named volumes:
```bash
docker compose down -v
docker compose up vipclaims-web
```

