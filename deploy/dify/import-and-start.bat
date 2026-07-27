@echo off
chcp 65001 >nul
cd /d "%~dp0\..\.."

set OFFLINE_DIR=%~dp0offline
if "%~1" neq "" set OFFLINE_DIR=%~1
set TAR=%OFFLINE_DIR%\dify-images.tar
set DOCKER_DIR=%OFFLINE_DIR%\docker

echo ========== 离线环境：导入镜像并启动 Dify ==========

if not exist "%TAR%" (
  echo 错误：未找到镜像包 dify-images.tar
  echo 用法：import-and-start.bat [离线包路径]
  echo 默认路径：deploy\dify\offline
  echo 请先将「有网络机器」上 export-images.bat 生成的 offline 文件夹拷到本机后再运行。
  pause
  exit /b 1
)

if not exist "%DOCKER_DIR%\docker-compose.yaml" (
  if not exist "%DOCKER_DIR%\docker-compose.yml" (
    echo 错误：未找到 %DOCKER_DIR%\docker-compose 文件。
    echo 请确保离线包内包含 docker 文件夹（由 export-images.bat 生成）。
    pause
    exit /b 1
  )
)

echo [1/3] 检查 Docker ...
docker info >nul 2>&1
if errorlevel 1 (
  echo 错误：Docker 未运行。请先安装并启动 Docker Desktop。
  pause
  exit /b 1
)

echo [2/3] 导入镜像（不联网）...
docker load -i "%TAR%"
if errorlevel 1 (
  echo 导入失败。
  pause
  exit /b 1
)

echo [3/3] 启动 Dify 容器 ...
cd /d "%DOCKER_DIR%"
if not exist .env copy .env.example .env
docker compose up -d
if errorlevel 1 docker-compose up -d
if errorlevel 1 (
  echo 启动失败。
  pause
  exit /b 1
)

echo.
echo ========== 完成 ==========
echo 请打开浏览器访问: http://localhost/install
pause
