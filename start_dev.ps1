$ErrorActionPreference = "Stop"

# 启动 / 重启 开发环境（docker-compose.dev.yml）

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

$ComposeFile = "docker-compose.dev.yml"

if (-not (Test-Path $ComposeFile)) {
  Write-Host "❌ 找不到 $ComposeFile（请在项目根目录执行）"
  exit 1
}

Write-Host "==> 启动开发环境（project: testhub_dev）"
docker compose -p testhub_dev -f $ComposeFile up -d
docker compose -p testhub_dev -f $ComposeFile ps

Write-Host "✅ 开发环境已启动："
Write-Host "  前端：http://<你的IP>:5173/"
Write-Host "  后端：http://<你的IP>:8000/api/"

