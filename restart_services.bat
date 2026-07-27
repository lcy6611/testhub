@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Force UTF-8 to avoid garbled logs
chcp 65001 >nul

REM If double-clicked from Explorer, re-run in a cmd window that stays open
if /i "%~1" neq "__in_cmd__" (
  start "TestHub Restart Services" cmd /k call "%~f0" __in_cmd__
  exit /b
)

REM TestHub service restart script (ASCII-only, no unicode)

title TestHub Restart Services

REM >>> You can change these two ports if needed <<<
set "DJANGO_PORT=8001"
set "FRONTEND_PORT=3000"

echo ========================================
echo   TestHub Restart Services
echo ========================================
echo.

REM Switch to script directory
cd /d "%~dp0"

echo [1/5] Stopping services (ports %DJANGO_PORT%, %FRONTEND_PORT%)...
echo.

REM Stop Django service (port %DJANGO_PORT%)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%DJANGO_PORT% .*LISTENING"') do (
  echo Stopping Django PID: %%a
  taskkill /F /PID %%a >nul 2>&1
)

REM Stop Frontend service (port %FRONTEND_PORT%)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%FRONTEND_PORT% .*LISTENING"') do (
  echo Stopping Frontend PID: %%a
  taskkill /F /PID %%a >nul 2>&1
)

echo Waiting 2 seconds...
timeout /t 2 /nobreak >nul

echo.
echo [1.5/5] Verifying ports are free...

REM If Django port is still occupied, backend start will be unreliable
set "DJANGO_LISTEN_PID="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%DJANGO_PORT% .*LISTENING"') do (
  set "DJANGO_LISTEN_PID=%%a"
)
if defined DJANGO_LISTEN_PID (
  echo ERROR: Port %DJANGO_PORT% is still in use by PID !DJANGO_LISTEN_PID!
  netstat -ano ^| findstr ":%DJANGO_PORT%" ^| findstr "LISTENING"
  echo.
  echo Please close that process first or run this script as Administrator.
  echo If you cannot stop it, switch to another port (e.g. 8002) and update vite proxy.
  echo.
  pause
  exit /b 1
)

REM If frontend port is still occupied, frontend start will be unreliable
set "FRONTEND_LISTEN_PID="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%FRONTEND_PORT% .*LISTENING"') do (
  set "FRONTEND_LISTEN_PID=%%a"
)
if defined FRONTEND_LISTEN_PID (
  echo WARNING: Port %FRONTEND_PORT% is still in use by PID !FRONTEND_LISTEN_PID!
  netstat -ano ^| findstr ":%FRONTEND_PORT%" ^| findstr "LISTENING"
  echo You may have another frontend instance running.
  echo.
  pause
  exit /b 1
)

echo.
echo [2/5] Checking venv...
set "VENV_ACT=venv\Scripts\activate.bat"
if exist "%VENV_ACT%" (
  echo Found venv: %VENV_ACT%
) else (
  echo Venv not found, will use system python.
)

echo.
echo [3/5] Starting Django (new window)...
if exist "%VENV_ACT%" (
  start "Django Server" cmd /k "cd /d %~dp0 && call %VENV_ACT% && python manage.py runserver 127.0.0.1:%DJANGO_PORT%"
) else (
  start "Django Server" cmd /k "cd /d %~dp0 && python manage.py runserver 127.0.0.1:%DJANGO_PORT%"
)

echo.
echo [4/5] Starting Frontend (new window)...
if exist "frontend" (
  cd frontend
  start "Frontend Server" cmd /k "npm run dev"
  cd ..
) else (
  echo Frontend directory not found, skipping.
)

echo.
echo ========================================
echo   Done.
echo ========================================
echo Django:   http://localhost:%DJANGO_PORT%
echo Frontend: http://localhost:%FRONTEND_PORT%
echo.
echo If something closes immediately, run this .bat from an existing cmd window
echo so you can see the error output.
echo.
pause
endlocal
