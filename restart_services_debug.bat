@echo on
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM Debug version of restart script – shows every command and never closes automatically

title TestHub Restart Services (DEBUG)

set "DJANGO_PORT=8001"
set "FRONTEND_PORT=3000"

echo ========================================
echo   TestHub Restart Services (DEBUG)
echo ========================================
echo.

cd /d "%~dp0"
echo Current directory: %cd%
echo.

echo --- Existing processes on Django port %DJANGO_PORT% ---
netstat -ano | findstr ":%DJANGO_PORT%"
echo.

echo --- Existing processes on Frontend port %FRONTEND_PORT% ---
netstat -ano | findstr ":%FRONTEND_PORT%"
echo.

echo Stopping Django processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%DJANGO_PORT% .*LISTENING"') do (
  echo taskkill /F /PID %%a
  taskkill /F /PID %%a
)

echo Stopping Frontend processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%FRONTEND_PORT% .*LISTENING"') do (
  echo taskkill /F /PID %%a
  taskkill /F /PID %%a
)

echo.
echo Waiting 2 seconds...
timeout /t 2 /nobreak
echo.

echo Starting Django in this window...
if exist "venv\Scripts\activate.bat" (
  call venv\Scripts\activate.bat
) else (
  echo WARNING: venv\Scripts\activate.bat not found, using system python
)

python manage.py runserver 127.0.0.1:%DJANGO_PORT%

echo.
echo If Django stopped unexpectedly, please capture the above error and send it.
echo.
pause
endlocal

