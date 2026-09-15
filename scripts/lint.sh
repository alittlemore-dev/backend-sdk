#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
    lint) uv run --locked ruff check . ;;
    format-check) uv run --locked ruff format --check . ;;
    format) uv run --locked ruff format . ;;
    fix) uv run --locked ruff check --fix . ;;
    *) printf 'Usage: %s {lint|format-check|format|fix}\n' "$0" >&2; exit 2 ;;
esac
