#!/usr/bin/env bash
set -euo pipefail

# 一键更新生产环境（基于 docker-compose.prod.yml）
# 用法：
#   ./deploy_prod.sh
#
# 运行位置：项目根目录（包含 docker-compose.prod.yml 与 .env.prod）

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "❌ 找不到 $COMPOSE_FILE（请在项目根目录执行）"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ 找不到 $ENV_FILE（请先按 env.prod.example.txt 生成并填写）"
  exit 1
fi

echo "==> 1/4 拉取最新代码"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "❌ 当前目录不是 git 仓库"; exit 1; }
git pull

echo "==> 2/5 构建前端静态资源（frontend/dist）"
pushd frontend >/dev/null
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
npm run build
popd >/dev/null

echo "==> 3/5 重建并启动后端服务（backend/worker/beat）"
docker compose -p testhub_prod -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build backend worker beat

echo "==> 4/5 启动/更新 Nginx（挂载 dist，无需 build）"
docker compose -p testhub_prod -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d nginx

echo "==> 5/5 执行数据库迁移"
docker compose -p testhub_prod -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python manage.py migrate --noinput

echo "==> 基础健康检查（可选）"
docker compose -p testhub_prod -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

echo "✅ 完成：生产已更新"

