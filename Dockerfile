# =============================================================================
# Multi-stage production Dockerfile — Node.js 22, non-root, minimal image
# =============================================================================

# --- Stage 1: production dependencies ---
FROM node:22.11.0-alpine3.20 AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --prefer-offline

# --- Stage 2: production runtime ---
FROM node:22.11.0-alpine3.20 AS production
WORKDIR /app

RUN apk add --no-cache dumb-init wget \
    && addgroup -g 1001 -S nodejs \
    && adduser -S nodejs -u 1001 -G nodejs

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=deps --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --chown=nodejs:nodejs src ./src
COPY --chown=nodejs:nodejs package.json ./

USER nodejs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/health || exit 1

ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "src/index.js"]
