#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ $# -lt 1 ]]; then
  echo "usage: ./start.sh <csv> [count]" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  sudo apt install -y python3.12-venv
  python3.12 -m venv .venv
fi

if [[ -f .venv/Scripts/activate ]]; then
  source .venv/Scripts/activate
else
  source .venv/bin/activate
fi

python -m pip install -r requirements.txt
python collect_round.py "$@"
