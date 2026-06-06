# x_media CI — Flutter App

Cross-platform client for the `x_media/CI` long-term tweet storage.
Targets **Win11 / Ubuntu22 / Android 14+** from a single Flutter codebase.

## Sections

| Tab    | Purpose                                                            | Backend used                                |
|--------|--------------------------------------------------------------------|---------------------------------------------|
| Browse | Walk the account/month/tweet tree (read-only)                      | `/api/accounts`, `/api/tweet/{id}`          |
| Remote | Fire `md / pdf / ocr / all / fix / transcode / validate` on the PC  | `/api/run`, `/api/jobs/{id}`                |
| Local  | Independent download to the device sandbox (WIP)                   | local only                                  |
| Edit   | Load + edit `tweet.json` + PUT back                                | `/api/tweet/{id}` (GET + PUT)               |
| ⚙      | Configure the server base URL                                      | n/a                                         |

## Prerequisites

* Flutter 3.19+ (Dart 3.3+)
* Android SDK 34 / NDK r26 if building for Android 14+
* Visual Studio 2022 (Win11) or `clang` + `libgtk-3-dev` (Ubuntu22) for desktop

## Bootstrap

```bash
cd tools/app
flutter create . --project-name x_media_ci_app --platforms=android,linux,windows
flutter pub get
```

`flutter create .` will reuse the existing `lib/`, `pubspec.yaml` and
`analysis_options.yaml` instead of overwriting them, and add the
platform folders (`android/`, `linux/`, `windows/`) that the new project
needs.

## Run (per platform)

```bash
# Start the server first (on the PC that owns the data):
bash tools/server/run_server.sh          # Ubuntu
tools\server\run_server.cmd              # Windows

# Then point the app at it (Settings tab) and:

# Android emulator -> host PC
flutter run -d emulator-5554

# Android device on USB (no WiFi):
adb reverse tcp:8765 tcp:8765
# Settings: http://127.0.0.1:8765

# Linux desktop
flutter run -d linux

# Windows desktop
flutter run -d windows
```

## Build release artifacts

```bash
flutter build apk --release              # Android 14+ AAB-ready APK
flutter build linux --release            # Ubuntu22 AppImage
flutter build windows --release          # Win11 MSIX
```

## What is *not* included yet (TODOs)

* `Local` tab: actual fetcher + media downloader (currently UI-only)
* Image preview widget in the `Browse` -> `Tweet` screen
* OAuth / token persistence for the "independent download" path

These are intentionally left as separate tasks so the rest of the app
is fully exercisable end-to-end on day one.
