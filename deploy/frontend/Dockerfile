# Front end (React match viewer) served by nginx: the link the judges open.
# Build context is the repo root (the build copies ../fixtures into public/):
#   az acr build --file deploy/frontend/Dockerfile \
#     --build-arg VITE_API_BASE_URL=https://pm-api.<env-domain> \
#     --build-arg VITE_AGENTS_BASE_URL=https://pm-agents.<env-domain> .
# Vite inlines VITE_* at build time, so a new URL means a rebuild
# (deploy/deploy.sh frontend does this with the live URLs).
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
COPY deploy/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/frontend/dist /usr/share/nginx/html
EXPOSE 80
