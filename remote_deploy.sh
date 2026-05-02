#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# remote_deploy.sh
#
# Syncs the project to the home server and rebuilds the Docker container.
#
# Usage
# ─────
#   bash remote_deploy.sh              # full deploy
#   bash remote_deploy.sh --dry-run    # preview rsync without transferring
#
# What it does
# ────────────
#   1. Pre-flight: verifies rsync + ssh are available locally.
#   2. Connectivity: checks the server is reachable via SSH.
#   3. Remote prep: ensures the target directory and .env file exist.
#   4. rsync: transfers all project files, excluding secrets and venv.
#   5. Deploy: SSHs into the server and runs docker compose up -d --build.
#   6. Status: prints live container status and the public API URL.
#
# .env handling
# ─────────────
#   .env is intentionally excluded from rsync because it contains database
#   credentials. If it doesn't already exist on the server, this script
#   prints instructions and exits before deploying.
#   To create it manually (once):
#
#     ssh skyie@192.168.29.100 \
#       "cp ~/house_price_production/.env.example \
#            ~/house_price_production/.env"
#     # then edit it with your Neon.tech credentials
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────
SERVER_USER="skyie"
SERVER_HOST="192.168.29.100"
REMOTE_DIR="~/house_price_production"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false

# ── Colour helpers ─────────────────────────────────────────────────────────
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${CYAN}${BOLD}[$(date +%H:%M:%S)] $*${NC}"; }
ok()    { echo -e "${GREEN}  ✔  $*${NC}"; }
warn()  { echo -e "${YELLOW}  ⚠  $*${NC}"; }
fail()  { echo -e "${RED}  ✖  $*${NC}" >&2; exit 1; }
info()  { echo -e "     $*"; }

# ── Argument parsing ───────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *) fail "Unknown argument: $arg. Usage: bash remote_deploy.sh [--dry-run]" ;;
    esac
done

if [[ "$DRY_RUN" == "true" ]]; then
    warn "DRY-RUN mode: rsync will simulate the transfer without copying files."
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Pre-flight checks
# ─────────────────────────────────────────────────────────────────────────────
step "1/5  Pre-flight checks"

command -v rsync &>/dev/null || fail "'rsync' not found. Install it (e.g. brew install rsync / apt install rsync)."
ok "rsync found: $(rsync --version | head -1)"

command -v ssh &>/dev/null || fail "'ssh' not found."
ok "ssh found"

# Verify the source directory looks like the project root.
if [[ ! -f "${SCRIPT_DIR}/docker-compose.yml" ]]; then
    fail "docker-compose.yml not found in ${SCRIPT_DIR}. Run this script from the project root."
fi
ok "Project root verified: ${SCRIPT_DIR}"

# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Server connectivity check
# ─────────────────────────────────────────────────────────────────────────────
step "2/5  Checking connectivity to ${SERVER_USER}@${SERVER_HOST}"

if ! ssh -o ConnectTimeout=10 -o BatchMode=yes \
        "${SERVER_USER}@${SERVER_HOST}" "echo ok" &>/dev/null; then
    # BatchMode=yes means it will fail immediately if a password is required
    # without a key. Disable BatchMode so the user can enter their password
    # for the actual operations.
    warn "SSH key authentication is not configured (password will be prompted)."
    warn "To avoid repeated prompts, copy your key: ssh-copy-id ${SERVER_USER}@${SERVER_HOST}"
fi
ok "Server is reachable"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Remote directory and .env pre-checks
# ─────────────────────────────────────────────────────────────────────────────
step "3/5  Preparing remote directory"

# Ensure the target directory exists before rsync.
ssh "${SERVER_USER}@${SERVER_HOST}" "mkdir -p ${REMOTE_DIR}"
ok "Remote directory ready: ${REMOTE_DIR}"

# Check that .env exists on the server — it must be created manually once.
# It is never synced by rsync (excluded below) to protect credentials.
if ! ssh "${SERVER_USER}@${SERVER_HOST}" "test -f ${REMOTE_DIR}/.env"; then
    echo ""
    warn ".env not found on the server at ${REMOTE_DIR}/.env"
    info "Create it once with:"
    info ""
    info "  ssh ${SERVER_USER}@${SERVER_HOST}"
    info "  cp ${REMOTE_DIR}/.env.example ${REMOTE_DIR}/.env"
    info "  nano ${REMOTE_DIR}/.env   # fill in Neon.tech credentials"
    info ""
    fail "Aborting deployment — .env is required for the container to start."
fi
ok ".env exists on server"

# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — rsync project files
# ─────────────────────────────────────────────────────────────────────────────
step "4/5  Syncing project files to ${SERVER_USER}@${SERVER_HOST}:${REMOTE_DIR}"

RSYNC_FLAGS=(-az --progress --delete --human-readable)
[[ "$DRY_RUN" == "true" ]] && RSYNC_FLAGS+=(--dry-run)

rsync "${RSYNC_FLAGS[@]}" \
    --exclude 'house_price_env/'     \  # Python virtual environment (~2 GB)
    --exclude '__pycache__/'         \  # Python bytecode cache
    --exclude '*.pyc'                \  # compiled Python files
    --exclude '*.pyo'                \
    --exclude '.env'                 \  # secrets — created manually on server
    --exclude '*.egg-info/'          \  # Python packaging metadata
    --exclude '.zenml/'              \  # ZenML local metadata store
    --exclude 'mlflow-artifacts/'    \  # local MLflow artifact cache
    --exclude '.git/'                \  # git history (not needed on server)
    --exclude '*.log'                \
    --exclude '.DS_Store'            \
    "${SCRIPT_DIR}/"                 \
    "${SERVER_USER}@${SERVER_HOST}:${REMOTE_DIR}/"

if [[ "$DRY_RUN" == "true" ]]; then
    warn "Dry-run complete. No files were transferred."
    exit 0
fi
ok "Files synced successfully"

# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Build and start the container on the remote server
# ─────────────────────────────────────────────────────────────────────────────
step "5/5  Building and deploying container on ${SERVER_HOST}"

# All commands run inside a single SSH session using a heredoc.
# Single-quoted 'REMOTE_EOF' prevents local shell from expanding variables —
# everything between the markers runs literally on the remote machine.
ssh "${SERVER_USER}@${SERVER_HOST}" bash << 'REMOTE_EOF'
set -euo pipefail

TARGET_DIR="${HOME}/house_price_production"
cd "${TARGET_DIR}"

echo ""
echo "=== Remote: $(hostname) | $(date) ==="
echo "=== Working directory: $(pwd) ==="

# Pull the latest base image so security patches in python:3.10-slim
# are included without waiting for a full cache-bust rebuild.
echo ""
echo "--- Pulling base image ---"
docker pull python:3.10-slim

# Build the image and start the container in detached mode.
# --build     : force a rebuild even if the image already exists.
# -d          : detached; does not block this SSH session.
# --remove-orphans: removes containers for services that were removed from compose.
echo ""
echo "--- Running docker compose up ---"
docker compose up -d --build --remove-orphans

# Give the container a moment to start before printing status,
# so the status output reflects the actual running state.
sleep 3

echo ""
echo "--- Container status ---"
docker compose ps

echo ""
echo "--- Recent logs (last 20 lines) ---"
docker compose logs --tail=20

REMOTE_EOF

# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════${NC}"
ok "Deployment complete!"
echo -e "${GREEN}${BOLD}════════════════════════════════════════${NC}"
echo ""
info "API endpoint  →  http://${SERVER_HOST}:8085/api/v1/predict"
info "Health check  →  http://${SERVER_HOST}:8085/api/v1/health"
info "Swagger docs  →  http://${SERVER_HOST}:8085/docs"
info ""
info "To tail live logs:"
info "  ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${REMOTE_DIR} && docker compose logs -f'"
info ""
info "To stop the service:"
info "  ssh ${SERVER_USER}@${SERVER_HOST} 'cd ${REMOTE_DIR} && docker compose stop'"
