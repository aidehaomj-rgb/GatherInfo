#!/bin/bash
# Dev Dashboard 停止脚本 — 人工停止优先。
# 无论面板是否还跟踪着启动进程（managed/external/orphan），都能可靠停掉
# GatherInfo 的前端 (5178) 与后端 (8109)，并清理遗留的 PID 文件与 dev.sh 守护。
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

FRONTEND_PORT=5178
BACKEND_PORT=8109
PID_FILE="$PROJECT_DIR/.dev-pids"

# 杀掉占用指定端口的监听进程（含其子进程组）
kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    echo "[stop] port $port: no listener"
    return 0
  fi
  for pid in $pids; do
    # 先尝试整组杀，覆盖 vite/uvicorn 可能派生的 worker
    kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
  echo "[stop] port $port: killed $pids"
}

# 停掉 dev.sh 守护进程本身（否则它的 while 循环会立刻把后端/前端拉起来）
stop_devsh() {
  local pids
  pids=$(pgrep -f "scripts/dev\.sh" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    for pid in $pids; do
      kill -KILL "$pid" 2>/dev/null || true
    done
    echo "[stop] dev.sh launcher killed: $pids"
  fi
}

# 先停守护，再停端口服务，避免守护循环重启
stop_devsh
kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

# 清理 PID 文件（dev.sh 与 start-local.sh 两套机制）
rm -f "$PID_FILE"
for pid_file in "$PROJECT_DIR/logs/"*.pid; do
  [[ -f "$pid_file" ]] || continue
  pid=$(cat "$pid_file" 2>/dev/null || true)
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
done

echo "[stop] GatherInfo stopped (backend $BACKEND_PORT, frontend $FRONTEND_PORT)"