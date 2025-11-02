#!/bin/sh
set -e

echo "[entrypoint] Starting vipclaims-saas dev server on http://localhost:3000"
exec pnpm --filter vipclaims-saas dev --hostname 0.0.0.0 --port 3000

