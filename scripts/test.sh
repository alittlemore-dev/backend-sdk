#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
    test) uv run --locked pytest ;;
    coverage) uv run --locked pytest --cov --cov-report=term-missing --cov-report=xml ;;
    *) printf 'Usage: %s {test|coverage}\n' "$0" >&2; exit 2 ;;
esac
