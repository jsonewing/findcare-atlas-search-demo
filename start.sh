#!/usr/bin/env bash
# Compatibility alias. run.sh is the canonical portable launcher.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec "$SCRIPT_DIR/run.sh" "$@"
