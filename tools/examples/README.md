# 一键跑通（单条 tweet）
1. 准备一个 tweet 目录（包含 `tweet.json`、`media/images/`、可选 `exports/article_*_extract.json`）。
2. 运行：

```bash
python tools/x_media_ci.py all --tweet-dir <tweet_dir> --keep-going
```

等价于：

```bash
python tools/x_media_ci.py md  --tweet-dir <tweet_dir>
python tools/x_media_ci.py pdf --tweet-dir <tweet_dir>
python tools/x_media_ci.py ocr --tweet-dir <tweet_dir>   # 可选
```

# 一键跑通（整个 accounts 目录）

```bash
python tools/x_media_ci.py batch --root ../accounts --op all
```

# 校验 tweet.json

```bash
python tools/x_media_ci.py validate --root ../accounts           # 普通
python tools/x_media_ci.py validate --root ../accounts --strict  # 警告也算错
```

# 静态检查（pyflakes）

```bash
python x_media_ci.py lint
# 或者
bash examples/run_pyflakes.sh
```

# 归一化 tweet.json（路径、@ 前缀）

```bash
python x_media_ci.py fix --root ../accounts             # dry-run（默认）
python x_media_ci.py fix --root ../accounts --apply     # 实际写回磁盘
```

# 转码为手机友好 MP4（需要 ffmpeg）

```bash
python x_media_ci.py transcode --root ../accounts          # dry-run
python x_media_ci.py transcode --tweet-dir <...> --apply   # 写 *_transcoded.mp4
python x_media_ci.py transcode --in foo.mov --out foo.mp4 --probe
```

# Makefile / make.cmd（Windows / Ubuntu 通吃）

```bash
# Ubuntu / WSL / macOS
make help
make install
make md   DIR="<tweet_dir>"
make pdf  DIR="<tweet_dir>"
make all  DIR="<tweet_dir>" OCR=1   # 加 OCR
make batch ROOT="../accounts" OP=all
make validate ROOT="../accounts"
make lint
make fix   ROOT="../accounts"                       # dry-run
make fix   ROOT="../accounts" FIX_APPLY=1           # 写回
make transcode ROOT="../accounts"                   # dry-run
make transcode ROOT="../accounts" TC_APPLY=1        # 实际转码
make ci                                             # = lint + validate
```

```cmd
:: Windows 原生 cmd（无需 make）
make.cmd help
make.cmd install
make.cmd md   DIR="<tweet_dir>"
make.cmd pdf  DIR="<tweet_dir>"
make.cmd all  DIR="<tweet_dir>" OCR=1
make.cmd batch ROOT="..\accounts" OP=all
make.cmd validate ROOT="..\accounts"
make.cmd lint
make.cmd fix        ROOT="..\accounts"               :: dry-run
make.cmd fix        ROOT="..\accounts" FIX_APPLY=1   :: 写回
make.cmd transcode  ROOT="..\accounts"               :: dry-run
make.cmd transcode  ROOT="..\accounts" TC_APPLY=1    :: 实际转码
make.cmd ci                                          :: = lint + validate
make.cmd server                                      :: 启 FastAPI 包装层（默认 0.0.0.0:8765）
make.cmd app-bootstrap                               :: flutter create . 初始化 tools/app
make.cmd app-run                                     :: flutter run
make.cmd app-apk                                     :: flutter build apk --release
make.cmd dist-win                                    :: PyInstaller -> dist\x_media_ci_server.exe
make.cmd dist-linux                                  :: 产 portable venv tar.gz
make.cmd dist-android                                :: 打印 Android 构建步骤
make.cmd dist                                        :: 当前 OS 能产的全产
```

# PC ↔ 跨端 App（Flutter）

PC 端启 HTTP 服务（包装 `x_media_ci.py`）：

```bash
bash tools/server/run_server.sh
# 或
make server    # Windows 等价：make.cmd server
```

App 端在 `tools/app/`，先 bootstrap（一次性）：

```bash
cd tools/app
flutter create . --project-name x_media_ci_app --platforms=android,linux,windows
flutter pub get
```

然后按平台跑：

```bash
flutter run -d emulator-5554     # Android 模拟器（自动指向 10.0.2.2:8765）
adb reverse tcp:8765 tcp:8765    # 真机 USB：把手机的 127.0.0.1 转到 PC
flutter run -d linux             # Ubuntu22
flutter run -d windows           # Win11
```

打 release 包：

```bash
make app-apk        # Android APK
cd app && flutter build linux --release    # Ubuntu AppImage
cd app && flutter build windows --release  # Win11 MSIX
```
