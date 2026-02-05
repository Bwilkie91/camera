#!/usr/bin/env sh
# Start the surveillance backend. Optionally build and serve React when USE_REACT_APP=1.

set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "Python not found. Install Python 3.8+ and run: pip install -r requirements.txt"
  exit 1
fi

PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python

if [ "$USE_REACT_APP" = "1" ] || [ "$USE_REACT_APP" = "true" ]; then
  if [ ! -d "frontend/dist" ]; then
    echo "Building React app (frontend/dist missing)..."
    (cd frontend && npm install && npm run build)
  fi
fi

# Prefer venv if present (pip install -r requirements.txt there)
if [ -d ".venv/bin" ]; then
  . .venv/bin/activate
  PYTHON=python
fi
PORT=${PORT:-5000}
# Allow auto sign-in on login page when using React dev server (dev/local)
export AUTO_LOGIN=${AUTO_LOGIN:-1}
echo "Starting Flask on http://0.0.0.0:$PORT"
export PORT
exec $PYTHON app.py
