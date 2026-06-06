@echo off
REM adb_sync.cmd — Windows wrapper for adb_sync.sh (uses adb directly).
REM
REM Usage:
REM   tools\android\adb_sync.cmd push   <local>   <android>
REM   tools\android\adb_sync.cmd pull   <android> <local>
REM   tools\android\adb_sync.cmd reverse <port>
REM   tools\android\adb_sync.cmd devices

set "OP=%~1"
if "%OP%"=="" goto :usage
shift

where adb >nul 2>&1
if errorlevel 1 (
  echo ERROR: adb not found in PATH. Install Android platform-tools. 1>&2
  exit /b 2
)

if /i "%OP%"=="push" (
  if "%~2"=="" goto :usage
  adb push "%~1" "%~2"
  exit /b %ERRORLEVEL%
)
if /i "%OP%"=="pull" (
  if "%~2"=="" goto :usage
  adb pull "%~1" "%~2"
  exit /b %ERRORLEVEL%
)
if /i "%OP%"=="reverse" (
  set "PORT=%~1"
  if "%PORT%"=="" set "PORT=8765"
  adb reverse tcp:%PORT% tcp:%PORT%
  echo Phone can now reach PC at http://127.0.0.1:%PORT%/ (while USB is connected)
  exit /b %ERRORLEVEL%
)
if /i "%OP%"=="devices" (
  adb devices -l
  exit /b %ERRORLEVEL%
)

:usage
echo Usage:
echo   adb_sync.cmd push   ^<local^>   ^<android^>
echo   adb_sync.cmd pull   ^<android^> ^<local^>
echo   adb_sync.cmd reverse ^<port^>
echo   adb_sync.cmd devices
exit /b 2
