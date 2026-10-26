# syntax=docker/dockerfile:1

# =========================================================================
# Stage 1: Build the Next.js frontend as a static export
# =========================================================================
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

# Install dependencies first for better layer caching
COPY frontend/package*.json ./
RUN npm install

# Copy the rest of the frontend source and build the static export
COPY frontend/ ./
RUN npm run build

# NOTE (scaffold assumption): `next.config.js` is expected to set
# `output: 'export'`, producing the static export in `frontend/out/`.
# If the Frontend Engineer agent configures a different output directory,
# update the COPY path in Stage 2 below accordingly.

# =========================================================================
# Stage 2: Python backend (FastAPI via uv) serving API + static frontend
# =========================================================================
FROM python:3.12-slim AS backend

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app/backend

# Copy dependency manifests first for better layer caching
COPY backend/pyproject.toml backend/uv.lock ./

# Install production dependencies only (no dev/test extras), excluding the
# project itself so this layer caches independently of source changes
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the backend source
COPY backend/ ./

# Final sync to install the project itself
RUN uv sync --frozen --no-dev

# Copy the frontend static export into the directory the backend serves
# NOTE (scaffold assumption): backend is expected to serve static files
# from /app/backend/static — update if the Backend Engineer agent chooses
# a different static mount path in app/main.py.
COPY --from=frontend-build /app/frontend/out ./static

# Runtime volume mount point for the SQLite database (see docker-compose.yml)
VOLUME ["/app/db"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

# NOTE (scaffold assumption): backend entrypoint module is expected to be
# `app/main.py` exposing a FastAPI instance named `app`
# (i.e. `app.main:app`). Update this CMD if that changes.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
