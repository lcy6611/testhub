#!/usr/bin/env bash
set -euo pipefail

# 启动 / 重启 开发环境（docker-compose.dev.yml）

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="docker-compose.dev.yml"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "❌ 找不到 $COMPOSE_FILE（请在项目根目录执行）"
  exit 1
fi

echo "==> 启动开发环境（project: testhub_dev）"
docker compose -p testhub_dev -f "$COMPOSE_FILE" up -d
docker compose -p testhub_dev -f "$COMPOSE_FILE" ps

echo "✅ 开发环境已启动："
echo "  前端：http://<你的IP>:5173/"
echo "  后端：http://<你的IP>:8000/api/"

