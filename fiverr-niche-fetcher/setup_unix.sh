#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

echo "=========================================="
echo "Fiverr Gig Growth System - macOS/Linux Setup"
echo "=========================================="

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 was not found. Install Python 3.11 or newer."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

echo "Updating pip..."
.venv/bin/python -m pip install --upgrade pip

echo "Installing dependencies..."
.venv/bin/python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi

chmod +x run.sh setup_unix.sh
.venv/bin/python doctor.py

echo "Setup complete. Run ./run.sh and open http://127.0.0.1:8000"
