#!/usr/bin/env bash
# 一键跑通：单条 tweet 的"结构化导出"流程
# 用法：
#   bash examples/run_one_tweet_pipeline.sh <tweet_dir>
# 示例：
#   bash examples/run_one_tweet_pipeline.sh ../accounts/example_user/tweets/2026/2026-04/20260417T081047Z_1234567890
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TWEET_DIR="${1:-}"

if [[ -z "$TWEET_DIR" ]]; then
  echo "Usage: $0 <tweet_dir>" >&2
  exit 2
fi

cd "$ROOT"
exec python citeseal.py all --tweet-dir "$TWEET_DIR" --keep-going
