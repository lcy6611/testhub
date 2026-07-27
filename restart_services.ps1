# TestHub 服务重启脚本
# 功能：停止所有服务并重新启动Django和前端服务

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TestHub 服务重启脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 获取项目根目录
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "[1/5] 正在停止所有服务..." -ForegroundColor Yellow

# 停止Django服务（通过端口8000查找）
Write-Host "  正在查找占用8000端口的进程..." -ForegroundColor Yellow
$djangoPort = netstat -ano | Select-String ":8000.*LISTENING" | ForEach-Object {
    if ($_ -match '\s+(\d+)$') {
        $matches[1]
    }
}
if ($djangoPort) {
    $djangoPort | ForEach-Object {
        $pid = $_
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "  找到Django进程 PID: $pid ($($process.ProcessName))" -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 2
    Write-Host "  ✓ Django服务已停止" -ForegroundColor Green
} else {
    Write-Host "  ✓ 没有运行中的Django服务（端口8000未被占用）" -ForegroundColor Green
}

# 停止前端服务（通过端口3000查找）
Write-Host "  正在查找占用3000端口的进程..." -ForegroundColor Yellow
$frontendPort = netstat -ano | Select-String ":3000.*LISTENING" | ForEach-Object {
    if ($_ -match '\s+(\d+)$') {
        $matches[1]
    }
}
if ($frontendPort) {
    $frontendPort | ForEach-Object {
        $pid = $_
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "  找到前端进程 PID: $pid ($($process.ProcessName))" -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 2
    Write-Host "  ✓ 前端服务已停止" -ForegroundColor Green
} else {
    Write-Host "  ✓ 没有运行中的前端服务（端口3000未被占用）" -ForegroundColor Green
}

# 等待进程完全停止
Write-Host ""
Write-Host "[2/5] 等待进程完全停止..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

# 检查虚拟环境
Write-Host ""
Write-Host "[3/5] 检查虚拟环境..." -ForegroundColor Yellow
$venvPath = Join-Path $projectRoot "venv\Scripts\activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "  ✓ 找到虚拟环境" -ForegroundColor Green
    & $venvPath
} else {
    Write-Host "  ⚠ 未找到虚拟环境，将使用系统Python" -ForegroundColor Yellow
}

# 启动Django服务
Write-Host ""
Write-Host "[4/5] 正在启动Django服务..." -ForegroundColor Yellow
$djangoLogFile = Join-Path $projectRoot "logs\django_restart.log"
$djangoScript = @"
`$ErrorActionPreference = 'Continue'
Set-Location '$projectRoot'
if (Test-Path '$venvPath') {
    & '$venvPath'
}
python manage.py runserver > '$djangoLogFile' 2>&1
"@

# 创建启动Django的脚本
$djangoStartScript = Join-Path $env:TEMP "start_django_$(Get-Date -Format 'yyyyMMddHHmmss').ps1"
$djangoScript | Out-File -FilePath $djangoStartScript -Encoding UTF8

# 在新窗口中启动Django服务
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "& '$djangoStartScript'" -WindowStyle Normal
Start-Sleep -Seconds 3
Write-Host "  ✓ Django服务已启动（日志: $djangoLogFile）" -ForegroundColor Green

# 启动前端服务
Write-Host ""
Write-Host "[5/5] 正在启动前端服务..." -ForegroundColor Yellow
$frontendPath = Join-Path $projectRoot "frontend"
$frontendLogFile = Join-Path $projectRoot "logs\frontend_restart.log"

if (Test-Path $frontendPath) {
    $frontendScript = @"
`$ErrorActionPreference = 'Continue'
Set-Location '$frontendPath'
npm run dev > '$frontendLogFile' 2>&1
"@
    
    # 创建启动前端的脚本
    $frontendStartScript = Join-Path $env:TEMP "start_frontend_$(Get-Date -Format 'yyyyMMddHHmmss').ps1"
    $frontendScript | Out-File -FilePath $frontendStartScript -Encoding UTF8
    
    # 在新窗口中启动前端服务
    Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "& '$frontendStartScript'" -WindowStyle Normal
    Start-Sleep -Seconds 3
    Write-Host "  ✓ 前端服务已启动（日志: $frontendLogFile）" -ForegroundColor Green
} else {
    Write-Host "  ⚠ 未找到前端目录，跳过前端服务启动" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  服务重启完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Django服务: http://localhost:8000" -ForegroundColor Cyan
Write-Host "前端服务: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "提示: 服务已在新的PowerShell窗口中启动" -ForegroundColor Yellow
Write-Host "      可以查看这些窗口的输出和日志文件" -ForegroundColor Yellow
Write-Host ""
