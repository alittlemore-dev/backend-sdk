#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
    build)
        uv sync --locked
        rm -rf dist
        build_python=$(uv run --locked python -c 'import sys; print(sys.executable)')
        uv build --python "$build_python" --no-sources --no-build-isolation
        uv run --locked twine check --strict dist/*
        ;;
    package-check)
        bash scripts/build.sh build
        uv run --locked python scripts/check_package.py
        ;;
    *) printf 'Usage: %s {build|package-check}\n' "$0" >&2; exit 2 ;;
esac
