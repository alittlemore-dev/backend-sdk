#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
    install) uv sync --locked ;;
    lock) uv lock ;;
    lock-check) uv lock --check ;;
    *) printf 'Usage: %s {install|lock|lock-check}\n' "$0" >&2; exit 2 ;;
esac
