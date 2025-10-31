#!/bin/sh
set -e

echo "[entrypoint] Step 1/2 – installing pnpm workspace dependencies"
pnpm install --recursive --ignore-scripts --reporter=append-only --force
echo "[entrypoint] Step 1/2 – pnpm install completed"

echo "[entrypoint] Step 2/2 – starting vipclaims-saas dev server on http://localhost:3000"
exec pnpm --filter vipclaims-saas dev --hostname 0.0.0.0 --port 3000

