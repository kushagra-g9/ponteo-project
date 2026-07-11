# =============================================================================
# Multi-stage production Dockerfile — Node.js 22, non-root, minimal image
# =============================================================================

# --- Stage 1: production dependencies ---
FROM node:22-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --prefer-offline

# --- Stage 2: distroless runtime (minimal OS surface for Trivy) ---
FROM gcr.io/distroless/nodejs22-debian12:nonroot
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=deps /app/node_modules ./node_modules
COPY src ./src
COPY package.json ./

CMD ["src/index.js"]
