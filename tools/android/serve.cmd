@echo off
REM serve.cmd — Windows wrapper for serve.sh.
REM
REM Usage:
REM   tools\android\serve.cmd <dir> [port]
setlocal
set "DIR=%~1"
if "%DIR%"=="" set "DIR=..\accounts"
set "PORT=%~2"
if "%PORT%"=="" set "PORT=8765"

cd /d "%DIR%" || ( echo ERROR: cannot cd to "%DIR%" 1>&2 & exit /b 2 )

where py >nul 2>&1
if not errorlevel 1 (
  echo Serving %CD% at http://0.0.0.0:%PORT% ^(py -3 -m http.server^)
  py -3 -m http.server %PORT% --bind 0.0.0.0
  exit /b %ERRORLEVEL%
)
where python >nul 2>&1
if not errorlevel 1 (
  echo Serving %CD% at http://0.0.0.0:%PORT% ^(python -m http.server^)
  python -m http.server %PORT% --bind 0.0.0.0
  exit /b %ERRORLEVEL%
)
echo ERROR: no python interpreter found 1>&2
exit /b 2
