# Build the SPA, then run FastAPI serving /api + the built frontend.
FROM node:22-bookworm AS frontend
WORKDIR /app/webapp/frontend
COPY webapp/frontend/package.json webapp/frontend/package-lock.json ./
RUN npm ci
COPY webapp/frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UPFRONT_FRONTEND_DIST=/app/webapp/frontend/dist \
    UPFRONT_DB=/tmp/upfront.db

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/ ./engine/
COPY integration/ ./integration/
COPY webapp/api/ ./webapp/api/
COPY --from=frontend /app/webapp/frontend/dist ./webapp/frontend/dist/

EXPOSE 8017
# Railway injects PORT; default 8017 for local docker runs.
CMD ["sh", "-c", "python -m uvicorn main:app --app-dir webapp/api --host 0.0.0.0 --port ${PORT:-8017}"]
