# iPhone research preview: serve React and FastAPI from one HTTPS origin.
FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS server
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_DIST_DIR=/app/frontend/dist
WORKDIR /app
COPY backend/ /app/backend/
# NumPy is needed at API import time; Torch is intentionally omitted from this
# evaluation-only web service (offline neural workers are a separate concern).
RUN pip install --no-cache-dir -e '/app/backend[postgres]' 'numpy>=1.26,<3'
COPY --from=frontend /build/frontend/dist/ /app/frontend/dist/
COPY scripts/preview_start.sh /app/scripts/preview_start.sh
EXPOSE 8080
CMD ["/bin/sh", "/app/scripts/preview_start.sh"]
