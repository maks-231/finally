#!/usr/bin/env bash
# Start the FinAlly Docker container (macOS/Linux).
#
# Usage:
#   ./scripts/start_mac.sh            # build if needed, then run
#   ./scripts/start_mac.sh --build    # force a rebuild of the image first
#
# Idempotent: safe to run multiple times. If the container is already
# running, this just prints the URL. If it exists but is stopped, it is
# started rather than recreated.

set -euo pipefail

IMAGE_NAME="finally"
IMAGE_TAG="latest"
CONTAINER_NAME="finally"
VOLUME_NAME="finally-data"
HOST_PORT="8000"
CONTAINER_PORT="8000"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

FORCE_BUILD=false
for arg in "$@"; do
  case "${arg}" in
    --build)
      FORCE_BUILD=true
      ;;
  esac
done

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Warning: ${ENV_FILE} not found. Copy .env.example to .env and fill in values first." >&2
fi

cd "${PROJECT_ROOT}"

IMAGE_EXISTS=false
if docker image inspect "${IMAGE_NAME}:${IMAGE_TAG}" >/dev/null 2>&1; then
  IMAGE_EXISTS=true
fi

if [[ "${FORCE_BUILD}" == "true" || "${IMAGE_EXISTS}" == "false" ]]; then
  echo "Building Docker image ${IMAGE_NAME}:${IMAGE_TAG}..."
  docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" -f "${PROJECT_ROOT}/Dockerfile" "${PROJECT_ROOT}"
fi

# Ensure the named volume exists (idempotent — no-op if already present)
docker volume create "${VOLUME_NAME}" >/dev/null

if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
  CONTAINER_STATE="$(docker inspect -f '{{.State.Status}}' "${CONTAINER_NAME}")"
else
  CONTAINER_STATE="missing"
fi

case "${CONTAINER_STATE}" in
  running)
    echo "Container '${CONTAINER_NAME}' is already running."
    ;;
  missing)
    echo "Starting new container '${CONTAINER_NAME}'..."
    RUN_ARGS=(run -d --name "${CONTAINER_NAME}" \
      -p "${HOST_PORT}:${CONTAINER_PORT}" \
      -v "${VOLUME_NAME}:/app/db" \
      --restart unless-stopped)
    if [[ -f "${ENV_FILE}" ]]; then
      RUN_ARGS+=(--env-file "${ENV_FILE}")
    fi
    RUN_ARGS+=("${IMAGE_NAME}:${IMAGE_TAG}")
    docker "${RUN_ARGS[@]}"
    ;;
  *)
    echo "Container '${CONTAINER_NAME}' exists (state: ${CONTAINER_STATE}). Starting it..."
    docker start "${CONTAINER_NAME}" >/dev/null
    ;;
esac

URL="http://localhost:${HOST_PORT}"
echo ""
echo "FinAlly is available at: ${URL}"

# Best-effort browser open; never fail the script if it's unavailable
# (e.g. on Linux without xdg-open, or in a headless environment).
if command -v open >/dev/null 2>&1; then
  open "${URL}" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "${URL}" >/dev/null 2>&1 || true
fi
