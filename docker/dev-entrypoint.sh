#!/bin/sh
set -e

echo "[entrypoint] installing pnpm workspace dependencies"
pnpm install --recursive --ignore-scripts --reporter=append-only --force

echo "[entrypoint] starting vipclaims-saas dev server"
exec pnpm --filter vipclaims-saas dev --hostname 0.0.0.0 --port 3000

