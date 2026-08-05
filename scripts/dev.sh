#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

cd "$PROJECT_DIR"

if [[ -f "$PROJECT_DIR/backend/.env" ]]; then
  set -a
  source "$PROJECT_DIR/backend/.env"
  set +a
fi

# ── Pre-flight checks ────────────────────────────────────────────────────────
if [[ ! -x backend/.venv/bin/python ]]; then
  echo "ERROR: backend/.venv is missing."
  echo "Run: python3.12 -m venv backend/.venv && pip install -r requirements.txt"
  exit 1
fi

# ── PID file for external cleanup (dashboard stop) ───────────────────────────
PID_FILE="$PROJECT_DIR/.dev-pids"
: > "$PID_FILE"   # 每次启动清空，避免堆积陈旧 PID

cleanup() {
  # 先停掉 wait 循环里记录的子进程，再删 PID 文件，避免孤儿占用端口
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      [[ -n "$pid" ]] || continue
      kill -TERM "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    wait 2>/dev/null || true
    # 兜底强杀仍在监听的端口进程
    for port in 8109 5178; do
      for pid in $(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true); do
        kill -KILL "$pid" 2>/dev/null || true
      done
    done
    rm -f "$PID_FILE"
  fi
}
trap cleanup EXIT INT TERM

# ── Start backend (uvicorn on port 8109) ─────────────────────────────────────
echo "[dev] Starting backend on port 8109 ..."
backend/.venv/bin/python -m uvicorn app.main:create_app \
  --factory --host 127.0.0.1 --port 8109 --app-dir backend \
  > "$PROJECT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" >> "$PID_FILE"

# ── Start frontend (vite on port 5178) ───────────────────────────────────────
echo "[dev] Starting frontend on port 5178 ..."
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5178 \
  > "$PROJECT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" >> "$PID_FILE"

echo "[dev] Backend PID=$BACKEND_PID  Frontend PID=$FRONTEND_PID"

# ── Wait loop (keeps parent alive so dashboard can track & kill it) ───────────
while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[dev] Backend exited — restarting ..."
    backend/.venv/bin/python -m uvicorn app.main:create_app \
      --factory --host 127.0.0.1 --port 8109 --app-dir backend \
      > "$PROJECT_DIR/logs/backend.log" 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" >> "$PID_FILE"
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "[dev] Frontend exited — restarting ..."
    npm --prefix frontend run dev -- --host 127.0.0.1 --port 5178 \
      > "$PROJECT_DIR/logs/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" >> "$PID_FILE"
  fi

  sleep 3
done
