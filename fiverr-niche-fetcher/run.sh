#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Virtual environment not found. Running setup first..."
  ./setup_unix.sh
fi

exec .venv/bin/python start.py
