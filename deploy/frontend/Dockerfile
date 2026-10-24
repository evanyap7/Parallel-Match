# Front end (React match viewer) served by nginx: the link the judges open.
# Build context is the repo root (the build copies ../fixtures into public/):
#   az acr build --file deploy/frontend/Dockerfile \
#     --build-arg VITE_API_BASE_URL=https://pm-api.<env-domain> .
# and run with AGENTS_UPSTREAM=https://pm-agents.<env-domain>.
# Vite inlines VITE_* at build time, so a new API URL means a rebuild
# (deploy/deploy.sh web does this with the live URLs). The agents API is
# called directly at VITE_AGENTS_BASE_URL (deploy.sh sets it; CORS is open).
# Without it the app falls back to /agents, proxied by nginx to AGENTS_UPSTREAM.
FROM node:22-alpine AS build
WORKDIR /src
COPY fixtures ./fixtures
COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /src/frontend
RUN npm ci --no-audit --no-fund
COPY frontend ./
ARG VITE_API_BASE_URL=""
ARG VITE_AGENTS_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_AGENTS_BASE_URL=$VITE_AGENTS_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/frontend/default.conf.template /etc/nginx/templates/default.conf.template
# Placeholder so nginx starts even before the agents app exists.
ENV AGENTS_UPSTREAM=http://127.0.0.1:9
COPY --from=build /src/frontend/dist /usr/share/nginx/html
EXPOSE 80
