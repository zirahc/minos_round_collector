#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ $# -lt 1 ]]; then
  echo "usage: ./start.sh <csv> [count]" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  if command -v python >/dev/null 2>&1; then
    python -m venv .venv
  elif command -v python3 >/dev/null 2>&1; then
    python3 -m venv .venv
  else
    echo "python is not installed" >&2
    exit 1
  fi
fi

if [[ -f .venv/Scripts/activate ]]; then
  source .venv/Scripts/activate
else
  source .venv/bin/activate
fi

python -m pip install -r requirements.txt
python collect_round.py "$@"
