# Frontend build stage
FROM node:24-slim AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# Runtime stage: serve static files with nonroot user
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/dist /app/dist
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:80/')" || exit 1
CMD ["python3", "-m", "http.server", "80", "--directory", "dist"]