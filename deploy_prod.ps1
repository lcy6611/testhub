$ErrorActionPreference = "Stop"

# Production deploy script (Windows PowerShell)
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\deploy_prod.ps1

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

$ComposeFile = "docker-compose.prod.yml"
$EnvFile = ".env.prod"
$DevEnvFile = "docker/.env.docker"

function Get-EnvValue {
  param(
    [string]$FilePath,
    [string]$Key
  )
  if (-not (Test-Path $FilePath)) {
    return $null
  }
  $line = Get-Content $FilePath | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -First 1
  if (-not $line) {
    return $null
  }
  return ($line -split "=", 2)[1].Trim()
}

if (-not (Test-Path $ComposeFile)) {
  Write-Host "ERROR: $ComposeFile not found."
  exit 1
}

if (-not (Test-Path $EnvFile)) {
  Write-Host "ERROR: $EnvFile not found."
  exit 1
}

$ProdDbHost = Get-EnvValue -FilePath $EnvFile -Key "DB_HOST"
$ProdDbPort = Get-EnvValue -FilePath $EnvFile -Key "DB_PORT"
$ProdDbName = Get-EnvValue -FilePath $EnvFile -Key "DB_NAME"
$DevDbName = Get-EnvValue -FilePath $DevEnvFile -Key "DB_NAME"

if ($ProdDbName -and $DevDbName -and ($ProdDbName -eq $DevDbName)) {
  Write-Host "ERROR: dev/prod DB_NAME is the same: $ProdDbName"
  Write-Host "Please use different names, e.g. testhub_dev / testhub_prod."
  exit 1
}

if ($ProdDbHost -and $ProdDbPort) {
  Write-Host "Current prod DB: $ProdDbHost`:$ProdDbPort / $ProdDbName"
}

Write-Host "Step 1/5: git pull"
git rev-parse --is-inside-work-tree *> $null
git pull

Write-Host "Step 2/5: build frontend assets via frontend_build"
docker compose -p testhub_prod -f $ComposeFile --env-file $EnvFile up --build frontend_build

Write-Host "Step 3/5: rebuild backend/worker/beat"
docker compose -p testhub_prod -f $ComposeFile --env-file $EnvFile up -d --build backend worker beat

Write-Host "Step 4/5: rebuild nginx"
docker compose -p testhub_prod -f $ComposeFile --env-file $EnvFile up -d --build nginx

Write-Host "Step 5/5: run migrations"
docker compose -p testhub_prod -f $ComposeFile --env-file $EnvFile exec -T backend python manage.py migrate --noinput

Write-Host "Service status:"
docker compose -p testhub_prod -f $ComposeFile --env-file $EnvFile ps

Write-Host "Done."
