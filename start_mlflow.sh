#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start_mlflow.sh — Launch MLflow tracking server on port 5055
#
# Backend store : Neon.tech serverless PostgreSQL (avoids port 5000 clash)
# Artifact store: Local ./mlflow-artifacts directory
#
# Usage:
#   1. Copy .env.example -> .env and fill in your Neon credentials
#   2. source house_price_env/bin/activate
#   3. bash start_mlflow.sh
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# ── 1. Require active venv ─────────────────────────────────────────────────
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    echo "ERROR: No virtual environment active."
    echo "  Run: source ${SCRIPT_DIR}/house_price_env/bin/activate"
    exit 1
fi

# ── 2. Load .env credentials ───────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: .env file not found at ${ENV_FILE}"
    echo "  Copy .env.example -> .env and fill in your Neon.tech credentials."
    exit 1
fi

# shellcheck disable=SC1090
set -a && source "$ENV_FILE" && set +a

# ── 3. Validate required variables ────────────────────────────────────────
REQUIRED_VARS=(
    NEON_DB_USER NEON_DB_PASSWORD
    NEON_DB_HOST NEON_DB_NAME NEON_DB_PORT
    MLFLOW_HOST  MLFLOW_PORT
    MLFLOW_ARTIFACT_ROOT
)

for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: Required variable '${var}' is not set in .env"
        exit 1
    fi
done

# ── 4. Build the PostgreSQL connection URI ─────────────────────────────────
#
# Format : postgresql+psycopg2://<user>:<password>@<host>:<port>/<dbname>
# Neon   : SSL is mandatory — ?sslmode=require is appended
#
BACKEND_STORE_URI="postgresql+psycopg2://${NEON_DB_USER}:${NEON_DB_PASSWORD}@${NEON_DB_HOST}:${NEON_DB_PORT}/${NEON_DB_NAME}?sslmode=require"

# ── 5. Create local artifact directory if it doesn't exist ────────────────
mkdir -p "${SCRIPT_DIR}/${MLFLOW_ARTIFACT_ROOT}"

# ── 6. Launch MLflow server ───────────────────────────────────────────────
echo "Starting MLflow Tracking Server..."
echo "  Backend store : PostgreSQL @ ${NEON_DB_HOST}/${NEON_DB_NAME}"
echo "  Artifact root : ${SCRIPT_DIR}/${MLFLOW_ARTIFACT_ROOT}"
echo "  Listening on  : http://${MLFLOW_HOST}:${MLFLOW_PORT}"
echo ""
echo "  Access UI at  : http://localhost:${MLFLOW_PORT}"
echo "  Stop with     : Ctrl+C"
echo ""

mlflow server \
    --backend-store-uri "${BACKEND_STORE_URI}" \
    --default-artifact-root "${SCRIPT_DIR}/${MLFLOW_ARTIFACT_ROOT}" \
    --host "${MLFLOW_HOST}" \
    --port "${MLFLOW_PORT}" \
    --serve-artifacts
