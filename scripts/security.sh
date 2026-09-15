#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
    bandit) uv run --locked bandit -c pyproject.toml -r src ;;
    audit)
        requirements=$(mktemp)
        trap 'rm -f "$requirements"' EXIT
        uv export --locked --all-groups --no-emit-project --format requirements-txt > "$requirements"
        uv run --locked pip-audit --require-hashes --disable-pip -r "$requirements"
        ;;
    security)
        bash scripts/security.sh bandit
        bash scripts/security.sh audit
        ;;
    *) printf 'Usage: %s {bandit|audit|security}\n' "$0" >&2; exit 2 ;;
esac
