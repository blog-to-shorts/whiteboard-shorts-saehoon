#!/usr/bin/env bash
# 로컬 실행: 의존성 설치 확인 후 블로그 1건 → final.mp4
# 사용: scripts/run_local.sh <블로그 URL> [placeholder]
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync >/dev/null
[ -d remotion/node_modules ] || (cd remotion && npm install --no-audit --no-fund)
if [ "${2:-}" = "placeholder" ]; then
  uv run wbs run --url "$1" --image placeholder
else
  uv run wbs run --url "$1"
fi
