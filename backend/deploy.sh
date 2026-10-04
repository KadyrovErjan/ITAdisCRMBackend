#!/usr/bin/env bash
# Compatibility entry point. The safe Hetzner deployment script lives at the
# repository root and intentionally does not stop/remove the database volume.
set -Eeuo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIRECTORY/../scripts/deploy.sh" "$@"
