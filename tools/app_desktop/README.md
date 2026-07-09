# CiteSeal — Desktop app

A real, double-clickable desktop app (Tkinter, single-file exe) that
drives the existing `tools/citeseal.py` pipeline.

## What you get

| File | What it does |
|------|--------------|
| `tweet_gui.py`   | The Tkinter app (entry point) |
| `tweet_fetcher.py` | URL parsing + delegation to `citeseal.py` |
| `tweet_gui.spec` | PyInstaller spec for `citeseal_app.exe` |
| `start_app.cmd`  | One-click launcher that prefers the bundled exe |

## Run from source (dev)

```bash
python tools/app_desktop/tweet_gui.py
```

You should see a window with:

```
Tweet URL: [_____________________________] [Fetch]
Save to:   [C:\...\CI\accounts]            [Browse…]
Status:    Idle
Log:       (empty)
[ Save Markdown ]  [ Save PDF ]
[ Save Media   ]  [ Save ALL ]  [ Open Folder ]
```

## Build a Windows .exe

```bash
pyinstaller --noconfirm --clean tools/app_desktop/tweet_gui.spec
# -> tools/dist/citeseal_app.exe   (~10 MB, no Python needed on target)
```

## Build a Linux binary

Same spec, on Ubuntu 22+:

```bash
pyinstaller --noconfirm --clean tools/app_desktop/tweet_gui.spec
# -> tools/dist/citeseal_app
```

## How "Fetch" works

When you paste a tweet URL and click **Fetch**, the app does:

1. Parses the URL → `handle` and `tweet_id`.
2. Walks the chosen *Save to* folder for an existing
   `<save_to>/<handle>/tweets/.../<ts>_<tweet_id>` directory.
3. If found: runs `citeseal.py validate` to surface any issues.
4. If not found and you have a fetcher script configured (see below),
   the app calls it to create the CI-shaped folder and then runs
   `citeseal.py fix --apply` to normalize it.
5. If not found and there is no fetcher, the app creates a directory
   skeleton (`media/{images,video,audio,raw}/`, `exports/`,
   `tweet.json`) so you can drop the media files in by hand.

The 4 "Save" buttons (Markdown / PDF / Media / ALL) all run the
matching `citeseal.py` sub-commands on the resolved tweet_dir.

## The "fetcher" plug-in (optional)

If you have your own X scraper / downloader script (the kind of thing
you mentioned in your Solo workflow), point the app at it with one of:

| How | Where the app looks |
|-----|---------------------|
| `set X_MEDIA_FETCHER=...` env var | that exact path |
| `<save_to>/../tools/fetch_tweet.py` | conventional layout |
| `<save_to>/../fetch_tweet.py` | same, root level |
| `~/Documents/Solo/fetch_tweet.py` | your existing Solo script |

The script is invoked as:

```bash
python fetch_tweet.py <tweet_url> --out <tweet_dir>
```

It should create `<tweet_dir>/tweet.json` + `media/{images,video,audio,raw}/`
+ `exports/` (i.e. the CI layout). The app will then run `citeseal
fix --apply` to normalize the result.

If the script isn't there, the app falls back to creating a skeleton
and tells you in the log — useful if you just want to organize files
you already downloaded by hand.

## Quick test (no X account needed)

Use any URL you've already downloaded into `accounts/`:

1. `Save to` = `<your_local_path>/citeseal/accounts`
2. Paste: `https://x.com/0x_Discover/status/2045052337996157219`
3. Click **Fetch** — the log should say "found existing dir"
4. Click **Save ALL** — it produces a fresh `*_full.md` / `*_full.pdf`
5. Click **Open Folder** — Windows Explorer opens the tweet directory

## Troubleshooting

* "No such file: citeseal.py" in the log — the bundled exe cannot
  find `citeseal.py`. Copy `citeseal.py` + the `scripts/` folder
  next to the exe, or set `CITESEAL_ROOT` to point at the parent
  directory.
* Tk window flashes and disappears — the launcher is a `windowed` exe;
  the GUI logs to `citeseal_app.log` next to it. Add `console=True`
  to the `EXE()` block in `tweet_gui.spec` and rebuild to see what's
  happening.

## Android 14+ (APK)

Tkinter does not run on Android. The cleanest path to an Android app
is the Flutter project at `tools/app/`:

```bash
cd tools/app
flutter create . --platforms=android
flutter pub get
flutter build apk --release
# -> tools/app/build/app/outputs/flutter-apk/app-release.apk
```

The Flutter app has the same "URL → save" workflow and talks to the
citeseal server (or runs standalone). See `tools/app/README.md`.
