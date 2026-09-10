#!/bin/zsh
cd "$(dirname "$0")"
SCORE_PYTHON='/Users/shih-chiehliu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
if [[ ! -x "$SCORE_PYTHON" ]]; then
  SCORE_PYTHON=$(command -v python3)
fi
if [[ -z "$SCORE_PYTHON" ]]; then
  echo '找不到 Python 3，請安裝後再試。'
  read
  exit 1
fi
open 'http://127.0.0.1:8765'
exec "$SCORE_PYTHON" local/bridge.py
