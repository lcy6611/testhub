@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0\..\.."

set DOCKER_DIR=
if exist "dify-main\docker" set DOCKER_DIR=%CD%\dify-main\docker
if exist "deploy\dify-repo\docker" if "%DOCKER_DIR%"=="" set DOCKER_DIR=%CD%\deploy\dify-repo\docker

if "%DOCKER_DIR%"=="" (
  echo 错误：未找到 dify-main\docker 或 deploy\dify-repo\docker
  pause
  exit /b 1
)

set OUT_DIR=%~dp0offline
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

echo ========== 在有网络的机器上导出 Dify 镜像 ==========
cd /d "%DOCKER_DIR%"

echo [1/3] 拉取全部镜像（需能访问 Docker Hub: registry-1.docker.io）...
docker compose pull
if errorlevel 1 (
  echo.
  echo 拉取失败（多为无法访问 Docker Hub）。
  echo 建议：1. 先试 Docker Desktop 配置镜像加速（见 README「无法访问 Docker Hub 时的替代方案」）；
  echo       2. 或换一台能上外网的电脑运行本脚本生成 offline 包，拷回本机用 import-and-start.bat。
  echo 详见 deploy\dify\README.md
  pause
  exit /b 1
)

echo [2/3] 导出镜像到 %OUT_DIR%\dify-images.tar ...
set IMGS=
for /f "delims=" %%i in ('docker compose config --images 2^>nul') do set IMGS=!IMGS! %%i
if "!IMGS!"=="" (
  echo 无法获取镜像列表，请确认 docker compose 可用。
  pause
  exit /b 1
)
docker save !IMGS! -o "%OUT_DIR%\dify-images.tar"
if errorlevel 1 (
  echo 导出失败。
  pause
  exit /b 1
)

echo [3/3] 复制 docker 目录到离线包...
xcopy "%DOCKER_DIR%\*" "%OUT_DIR%\docker\" /E /I /Y >nul 2>&1
if not exist "%OUT_DIR%\docker\.env" copy "%DOCKER_DIR%\.env.example" "%OUT_DIR%\docker\.env"

echo.
echo ========== 导出完成 ==========
echo 请将整个文件夹复制到离线环境：
echo   %OUT_DIR%
echo 内含：dify-images.tar、docker\（含 .env 与 compose 文件）
echo 在离线机上运行 deploy\dify\import-and-start.bat 并指定该离线包路径。
pause
