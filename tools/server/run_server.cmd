@echo off
REM Start the x_media CI HTTP server (FastAPI wrapper around x_media_ci.py).
REM
REM Usage:
REM   run_server.cmd                          REM default 0.0.0.0:8765
REM   set X_MEDIA_CI_PORT=9000 ^&^& run_server.cmd
setlocal
set "HERE=%~dp0"
set "PORT=8765"
if not "%X_MEDIA_CI_PORT%"=="" set "PORT=%X_MEDIA_CI_PORT%"
set "HOST=0.0.0.0"
if not "%X_MEDIA_CI_HOST%"=="" set "HOST=%X_MEDIA_CI_HOST%"

cd /d "%HERE%.."
py -3 -m uvicorn server.app:app --host %HOST% --port %PORT% --app-dir "%HERE%"
endlocal
