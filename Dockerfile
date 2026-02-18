# syntax=docker/dockerfile:1.7

FROM node:20-bullseye AS base

ENV PNPM_HOME=/root/.local/share/pnpm \
    PATH=${PNPM_HOME}:/app/node_modules/.bin:${PATH}

RUN corepack enable pnpm

WORKDIR /app

# Copy workspace manifests to install dependencies
COPY package.json pnpm-workspace.yaml turbo.json tsconfig.base.json ./
COPY apps/frontend/package.json apps/frontend/
COPY apps/api/package.json apps/api/
COPY packages/shared/package.json packages/shared/

RUN pnpm install --recursive --ignore-scripts

FROM base AS dev

WORKDIR /app

COPY docker/dev-entrypoint.sh docker/dev-entrypoint.sh
RUN chmod +x docker/dev-entrypoint.sh

CMD ["pnpm", "--filter", "frontend", "dev", "--hostname", "0.0.0.0", "--port", "3000"]

