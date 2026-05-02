#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_env.sh — Isolated Python 3.10 environment for House Price Prediction
#
# Usage:  bash setup_env.sh
# ---------------------------------------------------------------------------

set -euo pipefail   # exit on error, unset var, or pipe failure

ENV_NAME="house_price_env"
REQUIRED_PYTHON="3.10"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 1. Locate Python 3.10 ──────────────────────────────────────────────────
echo "[1/5] Checking for Python ${REQUIRED_PYTHON}..."

PYTHON_BIN=""
for candidate in python3.10 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+')
        if [[ "$version" == "$REQUIRED_PYTHON" ]]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: Python ${REQUIRED_PYTHON} not found. Install it first:"
    echo "  sudo apt install python3.10 python3.10-venv python3.10-dev"
    exit 1
fi

echo "  Found: $PYTHON_BIN ($($PYTHON_BIN --version))"

# ── 2. Guard: abort if ANY other venv is already active ───────────────────
echo "[2/5] Checking for conflicting active virtual environments..."

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "ERROR: A virtual environment is already active: ${VIRTUAL_ENV}"
    echo "  Run 'deactivate' first to avoid cross-contamination."
    exit 1
fi

# ── 3. Create the isolated virtual environment ────────────────────────────
echo "[3/5] Creating isolated venv: ${ENV_NAME}..."

VENV_PATH="${SCRIPT_DIR}/${ENV_NAME}"

if [[ -d "$VENV_PATH" ]]; then
    echo "  WARNING: ${VENV_PATH} already exists. Skipping creation."
    echo "  Delete it manually with 'rm -rf ${VENV_PATH}' to start fresh."
else
    "$PYTHON_BIN" -m venv \
        --copies \
        --prompt "${ENV_NAME}" \
        "$VENV_PATH"
    echo "  Created: ${VENV_PATH}"
fi

# ── 4. Upgrade pip in isolation (never touches system pip) ─────────────────
echo "[4/5] Upgrading pip, setuptools, wheel inside venv..."

"${VENV_PATH}/bin/python" -m pip install --quiet --upgrade \
    pip setuptools wheel

# ── 5. Install project dependencies ───────────────────────────────────────
echo "[5/5] Installing dependencies from requirements.txt..."

"${VENV_PATH}/bin/pip" install \
    --no-cache-dir \
    --require-virtualenv \
    -r "${SCRIPT_DIR}/requirements.txt"

echo ""
echo "================================================================"
echo " Environment ready: ${VENV_PATH}"
echo " Activate with:"
echo "   source ${VENV_PATH}/bin/activate"
echo "================================================================"
