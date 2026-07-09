# Android 联调说明

> 设计原则：让 **手机在本地浏览/复用** `citeseal` 里的内容，**不**在 Android 端做
> 登录/反爬。所有抓取/导出仍在 PC 上跑完，再把结果同步到手机。

## 1) 路线选型

| 方案 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| **adb push/pull（推荐起步）** | 单机调试、零依赖 | 无需装 App、走 adb 即可 | 要 USB 连线 |
| **本地 HTTP 服务 + 手机浏览器** | 同 WiFi 经常用 | 一次配置反复用 | 要写个最小 HTTP 服务 |
| **Syncthing / FolderSync** | 长期双向同步 | 增量、省心 | 多装一个 App |

这里默认走 **adb 同步 + 本地服务** 两套：脚本已放在 `tools/android/` 下。

## 2) 一次性准备

```bash
# 1) 在 Windows / Ubuntu 上安装 adb（Ubuntu: sudo apt install adb）
# 2) 手机打开 USB 调试
# 3) 验证设备
adb devices
# 4) 在手机上下载一个能打开 zip/md/pdf/json 的文件管理器
#    推荐：Material Files、MIUI 文件管理、Google Files
```

## 3) adb 同步（PC → 手机）

```bash
# 同步整棵 accounts 树到手机
bash tools/android/adb_sync.sh push ../accounts /sdcard/Download/citeseal/accounts
# 同步单条 tweet（用得最多）
bash tools/android/adb_sync.sh push \
  "../accounts/0x_Discover/tweets/2026/2026-04/20260417T081047Z_2045052337996157219" \
  /sdcard/Download/citeseal
```

PowerShell / cmd 等价：

```powershell
tools\android\adb_sync.cmd push ..\accounts /sdcard/Download/citeseal/accounts
```

## 4) 本地 HTTP 服务（在 PC 跑，手机浏览器访问）

启动：

```bash
bash tools/android/serve.sh ../accounts 8765
# 输出形如：Serving ../accounts at http://0.0.0.0:8765
# 手机浏览器打开：http://<PC_IP>:8765/
```

反查 PC IP：

```bash
# Ubuntu
hostname -I
# Windows
ipconfig | findstr IPv4
```

建议手机与 PC 在同一 WiFi；若不在同一网段，开一台支持 USB 反向共享的小工具（`adb reverse`）：

```bash
adb reverse tcp:8765 tcp:8765
# 然后手机浏览器访问 http://127.0.0.1:8765/
```

## 5) 在手机上「管理」

- **打开 MD / PDF**：手机自带或第三方阅读器都能直接打开同步过去的 `*_full.md` / `*_full.pdf`。
- **浏览 JSONL 索引**：
  - 启动 `serve.sh` 后访问 `http://<IP>:8765/indices/tweets.jsonl`
  - 或下载 `citeseal` 索引浏览 App（任意 JSON viewer）。
- **批量导出（可选）**：在 PC 上：

  ```bash
  python citeseal.py batch --root ../accounts --op all --force
  ```

  再 `adb_sync.sh push` 一次即可。

## 6) 进一步：把"遥控端"做成 App

当上面这套熟练了之后，可以做最小 Android 端（也可以继续用 Flutter 一份代码三端跑）：

- 主屏：账号/月份树
- 详情屏：展示 `tweet.json`、列出 `media/`，点开看图/视频
- 任务屏：把任务下发给 PC 上的本地服务（`/api/run`），看进度
- 关键：手机端 **永远不**接触 X 登录

## 7) 故障排查

| 现象 | 原因 | 处置 |
|------|------|------|
| `adb: no devices/emulators found` | 未授权 / 驱动未装 | 手机点"允许 USB 调试"；装厂商驱动 |
| `failed to copy ... Permission denied` | 目标目录不可写 | 改用 `/sdcard/Download/` 或 `/sdcard/Documents/` |
| 手机浏览器打不开 PC 服务 | 防火墙阻拦 | `sudo ufw allow 8765` 或 Windows 防火墙放行 `python.exe` |
| 视频在手机无法播放 | 容器/编码不兼容 | 复用 `ffmpeg` 转成 `H.264 + AAC + MP4`（后续在 `tools` 下加一个 `transcode.sh`） |
