#!/usr/bin/env sh
set -e

# 启动虚拟显示（Xvfb）+ VNC（x11vnc），使容器内可使用有头模式运行 UI/AI 自动化
if command -v Xvfb >/dev/null 2>&1; then
  export DISPLAY=:99

  # 如果上次异常退出留下了锁文件，先清理掉，避免 "Server is already active for display 99"
  if [ -f /tmp/.X99-lock ]; then
    echo "Removing stale /tmp/.X99-lock ..."
    rm -f /tmp/.X99-lock
  fi

  # 后台启动 Xvfb 提供 :99 显示
  Xvfb :99 -screen 0 1280x720x24 -ac </dev/null >>/tmp/xvfb.log 2>&1 &
  sleep 2
  echo "Xvfb started on DISPLAY=${DISPLAY} (see /tmp/xvfb.log if headed mode fails)"

  # 启动 x11vnc，将 DISPLAY=:99 暴露到 5900 端口，方便使用 VNC 查看浏览器界面
  if command -v x11vnc >/dev/null 2>&1; then
    # 开发环境直接使用无密码连接（仅本机 5900 端口映射）
    x11vnc -display :99 -rfbport 5900 -forever -shared -nopw </dev/null >>/tmp/x11vnc.log 2>&1 &
    echo "x11vnc started on port 5900 (no password, dev use only)"
  fi
fi

echo "Ensuring database driver packages are available ..."
# 注：cryptography 不锁版本，避免覆盖 daphne/pyopenssl 所需的新版本
pip install --no-cache-dir SQLAlchemy==2.0.51 pymysql==1.1.0 cryptography >/tmp/pip_db_drivers.log 2>&1 || echo "db driver install warning, see /tmp/pip_db_drivers.log"

echo "Waiting for MySQL at ${DB_HOST:-127.0.0.1}:${DB_PORT:-3306} ..."
python - <<'PY'
import os, time
import pymysql

host = os.getenv("DB_HOST", "127.0.0.1")
port = int(os.getenv("DB_PORT", "3306"))
user = os.getenv("DB_USER", "root")
password = os.getenv("DB_PASSWORD", "")
db = os.getenv("DB_NAME", "testhub")

deadline = time.time() + 120
last_err = None
while time.time() < deadline:
  try:
    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db, connect_timeout=3)
    conn.close()
    print("MySQL is ready.")
    raise SystemExit(0)
  except Exception as e:
    last_err = e
    time.sleep(2)

print("MySQL not ready after 120s:", last_err)
raise SystemExit(1)
PY

echo "Running migrations..."
python manage.py migrate --noinput

if [ "$#" -gt 0 ]; then
  echo "Starting Django with custom command: $*"
  exec "$@"
fi

# --------------------------------------------------------------------------- #
# 启动方式：默认用 Daphne（ASGI）启动，以同时支持 MCP 协议端点与 WebSocket；
# 设置 USE_DAPHNE=false 回退到 runserver（仅 HTTP，MCP 协议端点由 DRF 兜底）。
# daphne 未安装时自动回退 runserver，保证服务可起。
# --------------------------------------------------------------------------- #
if [ "${USE_DAPHNE:-true}" = "true" ] && command -v daphne >/dev/null 2>&1; then
  echo "Starting Daphne (ASGI) on 0.0.0.0:8000 (MCP 协议端点 + WebSocket 已启用) ..."
  exec daphne -b 0.0.0.0 -p 8000 backend.asgi:application
fi

if [ "${USE_DAPHNE:-true}" = "true" ]; then
  echo "WARNING: USE_DAPHNE=true 但 daphne 未安装，回退到 runserver（MCP 协议端点不可用）"
fi

echo "Starting Django dev server (auto-reload enabled)..."
exec python manage.py runserver 0.0.0.0:8000

