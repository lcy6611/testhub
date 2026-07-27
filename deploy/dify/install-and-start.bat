@echo off
chcp 65001 >nul
cd /d "%~dp0\..\.."
set REPO=deploy\dify-repo
set DOCKER_DIR=

echo ========== Dify 安装脚本 ==========

REM 优先使用已下载的 dify-main（项目根目录下）
if exist "dify-main\docker" (
  set DOCKER_DIR=%CD%\dify-main\docker
  echo [1/4] 使用已下载的 dify-main，跳过克隆
  goto :config
)

REM 其次使用 deploy\dify-repo
if exist "%REPO%\docker" (
  set DOCKER_DIR=%CD%\%REPO%\docker
  echo [1/4] 使用已存在的 %REPO%，跳过克隆
  goto :config
)

REM 否则尝试克隆
echo [1/4] 克隆 Dify 仓库（默认分支）...
git clone --depth 1 https://github.com/langgenius/dify.git "%REPO%"
if errorlevel 1 (
  echo.
  echo 克隆失败。可将下载的 ZIP 解压到项目根目录，文件夹名为 dify-main，再运行本脚本。
  pause
  exit /b 1
)
echo [2/4] 切换到发布版本 v1.12.1 ...
cd /d "%REPO%"
git fetch --depth 1 origin tag v1.12.1 2>nul
if not errorlevel 1 (git checkout v1.12.1) else (echo 使用默认分支继续。)
cd /d "%~dp0\..\.."
set DOCKER_DIR=%CD%\%REPO%\docker

:config
if not exist "%DOCKER_DIR%" (
  echo 错误：未找到 docker 目录。请确认 dify-main 或 deploy\dify-repo 下存在 docker 文件夹。
  pause
  exit /b 1
)

cd /d "%DOCKER_DIR%"

if not exist .env (
  echo [3/4] 生成 .env ...
  copy .env.example .env
) else (
  echo [3/4] 已存在 .env，跳过
)

echo [4/4] 检查 Docker ...
docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo 错误：无法连接 Docker。
  echo 请先安装并启动 Docker Desktop，等托盘图标显示为“运行中”后再运行本脚本。
  echo 下载地址: https://www.docker.com/products/docker-desktop/
  echo.
  pause
  exit /b 1
)

echo [4/4] 启动 Dify 容器 ...
docker compose up -d
if errorlevel 1 (
  echo 尝试 docker-compose ...
  docker-compose up -d
)
if errorlevel 1 (
  echo.
  echo 启动失败，请确认 Docker Desktop 已完全启动（托盘图标无转圈）。
  pause
  exit /b 1
)

echo.
echo ========== 完成 ==========
echo 请打开浏览器访问: http://localhost/install
echo 按提示创建管理员账号后即可使用。
pause
