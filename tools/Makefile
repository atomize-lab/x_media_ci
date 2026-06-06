# x_media_ci tools - unified Makefile
#
# Works on:
#   * Ubuntu / WSL / macOS (GNU make)
#   * Windows + GnuWin make (still GNU make)
# For Windows native cmd.exe users, see make.cmd in this directory.
#
# Targets:
#   make help            - show this help
#   make install         - install Python dependencies (Pillow, reportlab)
#   make dev             - install dev deps (pyflakes)
#   make md  DIR=...     - generate *full.md* for a single tweet dir
#   make pdf DIR=...     - generate *full.pdf* for a single tweet dir
#   make ocr DIR=...     - run OCR pipeline for a single tweet dir
#   make all DIR=...     - md + pdf (+ ocr if OCR=1)
#   make batch ROOT=...  - batch process every tweet dir under ROOT
#   make validate ROOT=. - validate tweet.json files
#   make lint            - run pyflakes over the scripts
#   make fix  ROOT=...   - normalize tweet.json (dry-run by default; FIX_APPLY=1 to write)
#   make transcode ROOT=. - transcode media/* to phone-friendly MP4 (dry-run by default; TC_APPLY=1 to run)
#   make ci              - same as `make lint && make validate ROOT=../accounts`
#   make server          - start the FastAPI wrapper around x_media_ci (port 8765)
#   make app-bootstrap   - `flutter create .` over the existing tools/app dir
#   make app-run         - `flutter run` on the current device
#   make app-apk         - `flutter build apk --release`
#   make dist-win        - PyInstaller -> dist/x_media_ci_server.exe (Windows)
#   make dist-linux      - portable venv tarball -> dist/x_media_ci_server-linux-x64.tar.gz
#   make dist-android    - docs only (Android needs Flutter SDK; see tools/app/BUILDING.md)
#   make dist            - whatever this OS can produce
#   make dist-gui        - PyInstaller -> dist/x_media_ci_app.exe (desktop GUI)

PY      ?= python
ROOT    ?= ../accounts
DIR     ?=
OP      ?= all
OCR     ?= 0
FORCE   ?= 0
FIX_APPLY ?= 0
TC_APPLY  ?= 0
PORT    ?= 8765

ifeq ($(OS),Windows_NT)
  PY ?= py -3
endif

PYFLAGS :=
ifeq ($(FORCE),1)
  PYFLAGS += --force
endif

.DEFAULT_GOAL := help

.PHONY: help install dev md pdf ocr all batch validate lint fix transcode ci server app-bootstrap app-run app-apk dist-win dist-linux dist-android dist dist-gui clean

help:
	@echo "Targets:"
	@echo "  make install        - pip install -r requirements.txt"
	@echo "  make dev            - pip install pyflakes"
	@echo "  make md DIR=<tweet> - generate full.md"
	@echo "  make pdf DIR=<tweet>- generate full.pdf"
	@echo "  make ocr DIR=<tweet>- run OCR pipeline"
	@echo "  make all DIR=<tweet>- md + pdf (+ ocr if OCR=1)"
	@echo "  make batch ROOT=... - batch all tweet dirs under ROOT (OP=md|pdf|all)"
	@echo "  make validate ROOT=. - validate tweet.json files"
	@echo "  make lint           - run pyflakes"
	@echo "  make fix   ROOT=.   - normalize tweet.json (FIX_APPLY=1 to write)"
	@echo "  make transcode ROOT=. - transcode media/* (TC_APPLY=1 to run; needs ffmpeg)"
	@echo "  make ci             - lint + validate (used by GitHub Actions)"
	@echo "  make server         - FastAPI wrapper around x_media_ci (port 8765)"
	@echo "  make app-bootstrap  - flutter create . into the existing tools/app"
	@echo "  make app-run        - flutter run on the current device"
	@echo "  make app-apk        - flutter build apk --release"
	@echo "  make dist-win       - PyInstaller -> dist/x_media_ci_server.exe"
	@echo "  make dist-linux     - portable venv tarball -> dist/*-linux-x64.tar.gz"
	@echo "  make dist-android   - print Android build steps (needs Flutter SDK)"
	@echo "  make dist           - whatever this OS can produce"
	@echo "  make dist-gui       - PyInstaller -> dist/x_media_ci_app.exe (desktop GUI)"

install:
	$(PY) -m pip install -r requirements.txt

dev:
	$(PY) -m pip install -r requirements.txt pyflakes

md:
	@test -n "$(DIR)" || (echo "DIR=<tweet_dir> is required" >&2; exit 2)
	$(PY) x_media_ci.py md --tweet-dir "$(DIR)" $(PYFLAGS)

pdf:
	@test -n "$(DIR)" || (echo "DIR=<tweet_dir> is required" >&2; exit 2)
	$(PY) x_media_ci.py pdf --tweet-dir "$(DIR)" $(PYFLAGS)

ocr:
	@test -n "$(DIR)" || (echo "DIR=<tweet_dir> is required" >&2; exit 2)
	$(PY) x_media_ci.py ocr --tweet-dir "$(DIR)"

all:
	@test -n "$(DIR)" || (echo "DIR=<tweet_dir> is required" >&2; exit 2)
	$(PY) x_media_ci.py all --tweet-dir "$(DIR)" --keep-going $(PYFLAGS) $(if $(filter 1,$(OCR)),--with-ocr,)

batch:
	$(PY) x_media_ci.py batch --root "$(ROOT)" --op "$(OP)" $(if $(filter 1,$(OCR)),--with-ocr,) $(PYFLAGS)

validate:
	$(PY) x_media_ci.py validate --root "$(ROOT)"

lint:
	$(PY) x_media_ci.py lint

fix:
	$(PY) x_media_ci.py fix --root "$(ROOT)" $(if $(filter 1,$(FIX_APPLY)),--apply,)

transcode:
	$(PY) x_media_ci.py transcode --root "$(ROOT)" $(if $(filter 1,$(TC_APPLY)),--apply,) --force

ci: lint
	$(PY) x_media_ci.py validate --root "$(ROOT)"

server:
	$(PY) -m pip install -q -r server/requirements.txt
	X_MEDIA_CI_PORT=$(PORT) $(PY) -m uvicorn server.app:app --host 0.0.0.0 --port $(PORT) --app-dir server

app-bootstrap:
	cd app && flutter create . --project-name x_media_ci_app --platforms=android,linux,windows
	cd app && flutter pub get

app-run:
	cd app && flutter run

app-apk:
	cd app && flutter build apk --release

dist-win:
	$(PY) -m pip install -q pyinstaller
	$(PY) -m PyInstaller --noconfirm --clean server/x_media_ci_server.spec
	@echo "Built: $(CURDIR)/dist/x_media_ci_server.exe"

dist-linux:
	bash server/build_linux.sh

dist-android:
	@echo "Android builds need the Flutter SDK. Options:"
	@echo "  1) Local:"
	@echo "       cd tools/app && flutter create . --platforms=android && flutter pub get"
	@echo "       cd tools/app && flutter build apk --release"
	@echo "  2) CI: push a tag like v0.1.0; .github/workflows/release.yml will"
	@echo "     produce app-release.apk and attach it to the GitHub release."

dist:
ifeq ($(OS),Windows_NT)
	$(MAKE) dist-win
	$(MAKE) dist-gui
else
	$(MAKE) dist-linux
endif

dist-gui:
	$(PY) -m pip install -q pyinstaller
	$(PY) -m PyInstaller --noconfirm --clean app_desktop/tweet_gui.spec
	@echo "Built: $(CURDIR)/dist/x_media_ci_app.exe"

clean:
	-@$(PY) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in [pathlib.Path('build'), pathlib.Path('dist'), pathlib.Path('__pycache__')]]"
	-@for /d /r . %%d in (__pycache__) do @rd /s /q "%%d" 2>nul || true
