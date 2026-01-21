FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy workspace package files
COPY package.json package-lock.json ./
COPY ui/package.json ./ui/package.json
RUN npm ci --workspace=ui

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app/ui

# Copy node_modules from workspace
COPY --from=deps /app/node_modules /app/node_modules
COPY --from=deps /app/ui/node_modules ./node_modules

# Copy UI source files and prisma
COPY ui/ ./
COPY prisma/ /app/prisma/

# Generate Prisma JavaScript client only (skip Python client)
RUN cd /app && npx prisma generate --generator client

# Build Next.js
ENV NEXT_TELEMETRY_DISABLED 1
RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy necessary files for standalone build
COPY --from=builder --chown=nextjs:nodejs /app/ui/.next/standalone ./
# Static files must be at .next/static relative to server.js location
COPY --from=builder --chown=nextjs:nodejs /app/ui/.next/static ./.next/static

# For workspace setups, Next.js standalone doesn't bundle node_modules
# Copy node_modules from the workspace
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/ui/node_modules ./ui/node_modules

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]
