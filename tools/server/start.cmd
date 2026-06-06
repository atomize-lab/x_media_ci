@echo off
REM start.cmd — the one-click launcher for the x_media CI server.
REM
REM What it does (in this order):
REM   1) Picks a free PORT (default 18765; falls back to 18766, 18767, ...)
REM   2) Picks a CI_ROOT automatically: <this dir>\accounts, then
REM      <tools>\..\accounts, then %USERPROFILE%\Documents\Solo\x_media\CI\accounts
REM   3) Opens the default browser to http://127.0.0.1:<port>/docs
REM   4) Runs the bundled server in the *current* console so the user
REM      can see logs and Ctrl+C to stop.
REM
REM Override defaults by setting env vars before launching:
REM   set X_MEDIA_CI_PORT=9000 ^& start.cmd
REM   set X_MEDIA_CI_ROOT=D:\data\accounts ^& start.cmd
setlocal EnableDelayedExpansion
set "HERE=%~dp0"

REM ---- 1) pick a free port ---------------------------------------------------
if not "%X_MEDIA_CI_PORT%"=="" goto :ci_root_step
set "PORT=18765"
:port_probe
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  set /a PORT+=1
  if !PORT! gtr 18865 (
    echo ERROR: no free port in 18765..18865. Set X_MEDIA_CI_PORT and retry.
    pause
    exit /b 1
  )
  goto :port_probe
)
set "X_MEDIA_CI_PORT=%PORT%"

:ci_root_step
if "%X_MEDIA_CI_HOST%"=="" set "X_MEDIA_CI_HOST=0.0.0.0"

REM ---- 2) pick a CI_ROOT automatically --------------------------------------
if "%X_MEDIA_CI_ROOT%"=="" (
  if exist "%HERE%accounts" (
    set "X_MEDIA_CI_ROOT=%HERE%accounts"
  ) else if exist "%HERE%..\accounts" (
    set "X_MEDIA_CI_ROOT=%HERE%..\accounts"
  ) else if exist "%USERPROFILE%\Documents\Solo\x_media\CI\accounts" (
    set "X_MEDIA_CI_ROOT=%USERPROFILE%\Documents\Solo\x_media\CI\accounts"
  ) else (
    set "X_MEDIA_CI_ROOT=%HERE%accounts"
  )
)

echo ====================================================
echo   x_media CI server
echo ====================================================
echo   PORT    : %X_MEDIA_CI_PORT%
echo   HOST    : %X_MEDIA_CI_HOST%
echo   CI_ROOT : %X_MEDIA_CI_ROOT%
echo   URL     : http://127.0.0.1:%X_MEDIA_CI_PORT%/docs
echo ====================================================
echo Press Ctrl+C in this window to stop the server.
echo.

REM Open the browser after a short delay (start /b is non-blocking).
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:%X_MEDIA_CI_PORT%/docs"

REM Prefer the bundled console exe; fall back to windowed.
if exist "%HERE%x_media_ci_server.exe" (
  "%HERE%x_media_ci_server.exe"
) else if exist "%HERE%x_media_ci_server_windowed.exe" (
  "%HERE%x_media_ci_server_windowed.exe"
) else (
  echo ERROR: no x_media_ci_server*.exe found in %HERE%
  echo        Run "make dist-win" first.
  pause
  exit /b 1
)
endlocal
