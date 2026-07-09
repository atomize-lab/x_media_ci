# CiteSeal HTTP Server

A thin FastAPI wrapper around `tools/citeseal.py`. It exposes every CLI
operation as JSON so the Flutter app on **Win11 / Ubuntu22 / Android 14+**
can drive the same scripts without re-implementing any logic.

## Install

```bash
python -m pip install -r tools/server/requirements.txt
```

## Run

```bash
# Ubuntu / WSL / macOS
bash tools/server/run_server.sh

# Windows
tools\server\run_server.cmd
```

Then open <http://localhost:8765/docs> for the interactive Swagger UI.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/api/health`                       | Liveness + CI root info |
| GET    | `/api/accounts`                     | List `{handle, tweet_count}` |
| GET    | `/api/accounts/{handle}`            | Months for that handle |
| GET    | `/api/index/tweets?handle=&limit=`  | Flat list from JSONL indices |
| GET    | `/api/tweet/{tweet_id}`             | Full `tweet.json` + media list |
| PUT    | `/api/tweet/{tweet_id}`             | Replace `tweet.json` |
| POST   | `/api/run`                          | Trigger `md / pdf / ocr / fix / transcode / ...` |
| GET    | `/api/jobs/{job_id}`                | Poll job status / output |
| GET    | `/media/{handle}/{tweet_dir}/{sub}/{filename}` | Serve local media |

### Triggering a job

```bash
curl -X POST http://localhost:8765/api/run \
  -H 'Content-Type: application/json' \
  -d '{"op": "pdf", "args": {"tweet_dir": "/abs/path/to/<tweet_dir>", "force": true}}'
```

`POST /api/run` returns `{job_id, status}`; poll `GET /api/jobs/{job_id}`
until `status` is `done` or `failed`.

## Environment variables

| Var | Default | Description |
|-----|---------|-------------|
| `CITESEAL_ROOT` | `<tools>/../accounts` | Where to look for tweet dirs |
| `CITESEAL_HOST` | `0.0.0.0`            | Bind host |
| `CITESEAL_PORT` | `8765`                | Bind port |

## Reachability from Android (most common gotcha)

* Same WiFi: phone can reach `http://<PC_IP>:8765/`.
* USB only: `adb reverse tcp:8765 tcp:8765` then phone uses
  `http://127.0.0.1:8765/`.
* Windows firewall: first run will pop up a permission dialog; allow
  `python.exe` on private networks.
