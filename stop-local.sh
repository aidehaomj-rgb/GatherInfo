#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
for pid_file in "$DIR/logs/"*.pid; do
    [ -f "$pid_file" ] || continue
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        echo "Stopping $pid (from $pid_file)"
        kill "$pid" || true
    fi
    rm -f "$pid_file"
done
echo "GatherInfo stopped"
