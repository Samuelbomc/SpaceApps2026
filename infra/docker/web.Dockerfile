FROM node:22-alpine AS build
WORKDIR /app/apps/web
COPY apps/web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web ./
COPY packages/contracts /app/packages/contracts
COPY packages/api-client /app/packages/api-client
ENV API_INTERNAL_URL=http://api:8000
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build
EXPOSE 3000
CMD ["node", "node_modules/next/dist/bin/next", "start", "-H", "0.0.0.0"]
