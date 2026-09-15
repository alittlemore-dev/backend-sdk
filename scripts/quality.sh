#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/install.sh lock-check
bash scripts/lint.sh format-check
bash scripts/lint.sh lint
bash scripts/types.sh
bash scripts/test.sh test
bash scripts/security.sh security
bash scripts/build.sh package-check
