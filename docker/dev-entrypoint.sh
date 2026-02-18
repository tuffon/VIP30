#!/bin/sh
set -e

echo "[entrypoint] Starting frontend dev server on http://localhost:3000"
exec pnpm --filter frontend dev --hostname 0.0.0.0 --port 3000

