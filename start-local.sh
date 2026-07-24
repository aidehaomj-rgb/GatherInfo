#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
mkdir -p "$DIR/logs"
export PATH="/Users/m4max/.nvm/versions/node/v20.20.1/bin:/opt/homebrew/bin:$PATH"

# Backend
source "$DIR/backend/.venv/bin/activate"
echo "[start] Starting backend on 8109..."
nohup python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8109 --app-dir backend   > "$DIR/logs/backend.log" 2>&1 &
echo $! > "$DIR/logs/backend.pid"

# Frontend
cd "$DIR/frontend"
echo "[start] Starting frontend on 5178..."
nohup npm run dev -- --host 127.0.0.1 --port 5178   > "$DIR/logs/frontend.log" 2>&1 &
echo $! > "$DIR/logs/frontend.pid"

echo "[start] GatherInfo started. Backend: http://127.0.0.1:8109, Frontend: http://127.0.0.1:5178"
