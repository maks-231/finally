#!/usr/bin/env bash
# Stop and remove the FinAlly Docker container (macOS/Linux).
# Does NOT remove the named volume — portfolio/trade data persists.
#
# Usage:
#   ./scripts/stop_mac.sh
#
# Idempotent: safe to run multiple times, including when the container
# doesn't exist or is already stopped.

set -euo pipefail

CONTAINER_NAME="finally"

if docker inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
  echo "Stopping container '${CONTAINER_NAME}'..."
  docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  echo "Removing container '${CONTAINER_NAME}'..."
  docker rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  echo "Container stopped and removed. Data volume 'finally-data' is preserved."
else
  echo "Container '${CONTAINER_NAME}' does not exist. Nothing to do."
fi
