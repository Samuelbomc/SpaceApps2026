FROM node:26-alpine AS build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend ./
COPY packages/contracts /app/packages/contracts
COPY packages/api-client /app/packages/api-client
ENV API_INTERNAL_URL=http://api:8000
ENV NG_CLI_ANALYTICS=false
ENV NG_BUILD_MAX_WORKERS=2
RUN npm run build
FROM nginx:alpine
COPY --from=build /app/frontend/dist/agrogeo/browser /usr/share/nginx/html
COPY infra/docker/frontend.conf /etc/nginx/conf.d/default.conf
COPY infra/docker/frontend-api.conf /etc/nginx/frontend-api.conf
EXPOSE 3000
