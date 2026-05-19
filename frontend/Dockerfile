# =============================================================================
# LateD frontend — production container image
# =============================================================================
#
# PURPOSE
# -------
# Builds the Next.js SOC dashboard for production. Multi-stage to keep the
# runtime image small (no devDependencies in the final layer).
#
# RUNTIME ROLE
# ------------
# Serves the analyst UI. Connects to the backend over REST + WebSocket.
# Does NOT make outbound requests to the internet (CSP enforces).
# =============================================================================

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -g 1001 -S lated && adduser -S lated -u 1001
COPY --from=builder /app/public ./public
COPY --from=builder --chown=lated:lated /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
USER lated
EXPOSE 3000
CMD ["npm", "run", "start"]
