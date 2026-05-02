# ─────────────────────────────────────────────────────────────────────────────
# Stage: runtime
# Base image : python:3.10-slim  (Debian Bookworm, ~130 MB uncompressed)
# Target port: 8085
# Module     : src.api:app  (FastAPI / uvicorn)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.10-slim

# ── OS-level packages ─────────────────────────────────────────────────────
# curl       — required by the Docker HEALTHCHECK and docker-compose healthcheck
# libgomp1   — GNU OpenMP runtime; scikit-learn links against it at import time
# Both are installed in a single layer and the apt cache is wiped immediately
# to keep the layer as small as possible.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root application user ─────────────────────────────────────────────
# Running as root inside a container is a security anti-pattern.
# UID/GID 1001 avoids collisions with common system UIDs on the host.
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# ── Working directory ─────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependency layer (cached until requirements.txt changes) ────────
# Copying requirements.txt before the rest of the source exploits Docker's
# layer cache: a code-only change will not re-trigger a full pip install.
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────
# Only the src/ package is needed at runtime; the .dockerignore file prevents
# the venv, scripts, and secrets from ever reaching this build context.
COPY src/ ./src/

# ── MLflow artifact cache directory ──────────────────────────────────────
# This directory is mounted as a named volume in docker-compose so that
# model artifacts downloaded from the MLflow server survive container
# restarts and do not need to be re-fetched on every startup.
RUN mkdir -p /app/models \
    && chown -R appuser:appgroup /app

# ── Drop privileges ───────────────────────────────────────────────────────
USER appuser

# ── Expose the application port ───────────────────────────────────────────
# Port 8085 is used to avoid conflicts with other live services on the host.
EXPOSE 8085

# ── Image-level healthcheck ───────────────────────────────────────────────
# docker-compose overrides this with its own healthcheck section, but having
# it here means `docker run` also knows how to assess container health.
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
    CMD curl -f -s http://localhost:8085/api/v1/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────
# --workers 1      : single worker; the model lives in process memory, so
#                    multiple workers would each load their own copy. Scale
#                    horizontally at the container level instead.
# --timeout-keep-alive 75 : keeps ALB / reverse-proxy connections alive.
CMD ["uvicorn", "src.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8085", \
     "--workers", "1", \
     "--timeout-keep-alive", "75", \
     "--access-log"]
