@echo off
REM Windows native wrapper for the citeseal Makefile.
REM
REM Why this exists:
REM   `make` is not always available on a vanilla Windows install.
REM   This .cmd file gives the same targets as Makefile via cmd.exe.
REM
REM Examples:
REM   make.cmd install
REM   make.cmd md   DIR="..\accounts\0x_Discover\tweets\2026\2026-04\20260417T081047Z_2045052337996157219"
REM   make.cmd batch ROOT="..\accounts" OP=all FORCE=1
REM   make.cmd validate ROOT="..\accounts"
REM   make.cmd lint

setlocal enabledelayedexpansion
set "CMD=%~1"
if "%CMD%"=="" set "CMD=help"

set "DIR="
set "ROOT=..\accounts"
set "OP=all"
set "OCR=0"
set "FORCE=0"
set "FIX_APPLY=0"
set "TC_APPLY=0"
set "PORT=8765"
set "PY=py -3"

REM parse remaining args as KEY=VALUE
shift
:parse_args
if "%~1"=="" goto :parsed
for /f "tokens=1,2 delims==" %%a in ("%~1") do (
  set "k=%%a"
  set "v=%%b"
  if /i "!k!"=="DIR"       set "DIR=!v!"
  if /i "!k!"=="ROOT"      set "ROOT=!v!"
  if /i "!k!"=="OP"        set "OP=!v!"
  if /i "!k!"=="OCR"       set "OCR=!v!"
  if /i "!k!"=="FORCE"     set "FORCE=!v!"
  if /i "!k!"=="FIX_APPLY" set "FIX_APPLY=!v!"
  if /i "!k!"=="TC_APPLY"  set "TC_APPLY=!v!"
  if /i "!k!"=="PORT"      set "PORT=!v!"
)
shift
goto :parse_args
:parsed

set "PYFLAGS="
if /i "%FORCE%"=="1" set "PYFLAGS=--force"

if /i "%CMD%"=="help" goto :help
if /i "%CMD%"=="install" goto :install
if /i "%CMD%"=="dev" goto :dev
if /i "%CMD%"=="md" goto :md
if /i "%CMD%"=="pdf" goto :pdf
if /i "%CMD%"=="ocr" goto :ocr
if /i "%CMD%"=="all" goto :all
if /i "%CMD%"=="batch" goto :batch
if /i "%CMD%"=="validate" goto :validate
if /i "%CMD%"=="lint" goto :lint
if /i "%CMD%"=="fix" goto :fix
if /i "%CMD%"=="transcode" goto :transcode
if /i "%CMD%"=="ci" goto :ci
if /i "%CMD%"=="server" goto :server
if /i "%CMD%"=="app-bootstrap" goto :app_bootstrap
if /i "%CMD%"=="app-run" goto :app_run
if /i "%CMD%"=="app-apk" goto :app_apk
if /i "%CMD%"=="dist-win" goto :dist_win
if /i "%CMD%"=="dist-linux" goto :dist_linux
if /i "%CMD%"=="dist-android" goto :dist_android
if /i "%CMD%"=="dist" goto :dist
if /i "%CMD%"=="dist-gui" goto :dist_gui
if /i "%CMD%"=="clean" goto :clean

echo Unknown target: %CMD%
echo Run: make.cmd help
exit /b 2

:help
echo Targets:
echo   make.cmd install            - pip install -r requirements.txt
echo   make.cmd dev                - pip install -r requirements.txt pyflakes
echo   make.cmd md  DIR=^<tweet^>   - generate full.md
echo   make.cmd pdf DIR=^<tweet^>   - generate full.pdf
echo   make.cmd ocr DIR=^<tweet^>   - run OCR pipeline
echo   make.cmd all DIR=^<tweet^>   - md + pdf (^+ ocr if OCR=1)
echo   make.cmd batch ROOT=^<dir^>  - batch (OP=md|pdf|all)
echo   make.cmd validate ROOT=^<dir^> - validate tweet.json files
echo   make.cmd lint               - run pyflakes
echo   make.cmd fix   ROOT=^<dir^>  - normalize tweet.json (FIX_APPLY=1 to write)
echo   make.cmd transcode ROOT=^<dir^> - transcode media/* (TC_APPLY=1 to run; needs ffmpeg)
echo   make.cmd ci                 - lint + validate (GitHub Actions)
echo   make.cmd server             - FastAPI wrapper around citeseal (port 8765)
echo   make.cmd app-bootstrap      - flutter create . into the existing tools/app
echo   make.cmd app-run            - flutter run on the current device
echo   make.cmd app-apk            - flutter build apk --release
echo   make.cmd dist-win           - PyInstaller -^> dist\citeseal_server.exe
echo   make.cmd dist-linux         - portable venv tarball (needs WSL or git bash)
echo   make.cmd dist-android       - print Android build steps (needs Flutter SDK)
echo   make.cmd dist               - whatever this OS can produce
echo   make.cmd dist-gui           - PyInstaller -^> dist\citeseal_app.exe (desktop GUI)
echo   make.cmd clean              - remove build/dist/__pycache__
exit /b 0

:install
%PY% -m pip install -r requirements.txt
exit /b %ERRORLEVEL%

:dev
%PY% -m pip install -r requirements.txt pyflakes
exit /b %ERRORLEVEL%

:md
if "%DIR%"=="" ( echo DIR is required 1>&2 & exit /b 2 )
%PY% citeseal.py md --tweet-dir "%DIR%" %PYFLAGS%
exit /b %ERRORLEVEL%

:pdf
if "%DIR%"=="" ( echo DIR is required 1>&2 & exit /b 2 )
%PY% citeseal.py pdf --tweet-dir "%DIR%" %PYFLAGS%
exit /b %ERRORLEVEL%

:ocr
if "%DIR%"=="" ( echo DIR is required 1>&2 & exit /b 2 )
%PY% citeseal.py ocr --tweet-dir "%DIR%"
exit /b %ERRORLEVEL%

:all
if "%DIR%"=="" ( echo DIR is required 1>&2 & exit /b 2 )
if /i "%OCR%"=="1" (
  %PY% citeseal.py all --tweet-dir "%DIR%" --keep-going %PYFLAGS% --with-ocr
) else (
  %PY% citeseal.py all --tweet-dir "%DIR%" --keep-going %PYFLAGS%
)
exit /b %ERRORLEVEL%

:batch
set "BATCH_OCR_FLAG="
if /i "%OCR%"=="1" set "BATCH_OCR_FLAG=--with-ocr"
%PY% citeseal.py batch --root "%ROOT%" --op "%OP%" %BATCH_OCR_FLAG% %PYFLAGS%
exit /b %ERRORLEVEL%

:validate
%PY% citeseal.py validate --root "%ROOT%"
exit /b %ERRORLEVEL%

:lint
%PY% citeseal.py lint
exit /b %ERRORLEVEL%

:fix
set "FIX_FLAG="
if /i "%FIX_APPLY%"=="1" set "FIX_FLAG=--apply"
%PY% citeseal.py fix --root "%ROOT%" %FIX_FLAG%
exit /b %ERRORLEVEL%

:transcode
set "TC_FLAG="
if /i "%TC_APPLY%"=="1" set "TC_FLAG=--apply"
%PY% citeseal.py transcode --root "%ROOT%" %TC_FLAG% --force
exit /b %ERRORLEVEL%

:ci
call :lint || exit /b %ERRORLEVEL%
%PY% citeseal.py validate --root "%ROOT%"
exit /b %ERRORLEVEL%

:server
%PY% -m pip install -q -r server\requirements.txt
set "CITESEAL_PORT=%PORT%"
%PY% -m uvicorn server.app:app --host 0.0.0.0 --port %PORT% --app-dir server
exit /b %ERRORLEVEL%

:app_bootstrap
where flutter >nul 2>&1
if errorlevel 1 ( echo ERROR: flutter not on PATH 1>&2 & exit /b 2 )
pushd app
flutter create . --project-name citeseal_app --platforms=android,linux,windows
if errorlevel 1 ( popd & exit /b %ERRORLEVEL% )
flutter pub get
popd
exit /b %ERRORLEVEL%

:app_run
where flutter >nul 2>&1
if errorlevel 1 ( echo ERROR: flutter not on PATH 1>&2 & exit /b 2 )
pushd app
flutter run
popd
exit /b %ERRORLEVEL%

:app_apk
where flutter >nul 2>&1
if errorlevel 1 ( echo ERROR: flutter not on PATH 1>&2 & exit /b 2 )
pushd app
flutter build apk --release
popd
exit /b %ERRORLEVEL%

:dist_win
%PY% -m pip install -q pyinstaller
%PY% -m PyInstaller --noconfirm --clean server\citeseal_server.spec
if errorlevel 1 exit /b %ERRORLEVEL%
echo Built: %CD%\dist\citeseal_server.exe
exit /b 0

:dist_linux
where bash >nul 2>&1
if errorlevel 1 ( echo ERROR: bash not on PATH (install Git for Windows) 1>&2 & exit /b 2 )
bash server/build_linux.sh
exit /b %ERRORLEVEL%

:dist_android
echo Android builds need the Flutter SDK. Options:
echo   1^) Local:
echo        cd tools\app ^&^& flutter create . --platforms=android ^&^& flutter pub get
echo        cd tools\app ^&^& flutter build apk --release
echo   2^) CI: push a tag like v0.1.0; .github\workflows\release.yml will
echo      produce app-release.apk and attach it to the GitHub release.
exit /b 0

:dist
call :dist_win
if errorlevel 1 exit /b %ERRORLEVEL%
call :dist_gui
exit /b %ERRORLEVEL%

:dist_gui
%PY% -m pip install -q pyinstaller
%PY% -m PyInstaller --noconfirm --clean app_desktop\tweet_gui.spec
if errorlevel 1 exit /b %ERRORLEVEL%
echo Built: %CD%\dist\citeseal_app.exe
exit /b 0

:clean
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
for /d /r . %%d in (__pycache__) do @rd /s /q "%%d" 2>nul
exit /b 0
