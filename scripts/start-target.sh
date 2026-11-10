#!/usr/bin/env bash
# Start (or restart) a fresh target on a port. Restarting resets all data to the seed.
# Usage: scripts/start-target.sh [port]     (default 3001)
#        scripts/start-target.sh stop [port]
# The target is chosen by AET_TARGET (default restful-booker; see scripts/target-env.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/scripts/target-env.sh"

stop_port() {
  local port="$1" pidfile="/tmp/aet-target-$1.pid"
  if [ -f "$pidfile" ]; then
    kill "$(cat "$pidfile")" 2>/dev/null || true
    rm -f "$pidfile"
  fi
  # Kill anything still listening on the port (works on macOS and Linux).
  for pid in $(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null || true); do
    kill "$pid" 2>/dev/null || true
  done
  for _ in $(seq 1 40); do
    curl -s -o /dev/null "http://localhost:$port/ping" || return 0
    sleep 0.25
  done
  echo "Port $port is still in use; cannot guarantee a fresh target" >&2
  return 1
}

if [ "${1:-}" = "stop" ]; then
  PORT="${2:-3001}"
  stop_port "$PORT"
  echo "Stopped target on port $PORT"
  exit 0
fi

PORT="${1:-3001}"
PIDFILE="/tmp/aet-target-$PORT.pid"
LOG="/tmp/aet-target-$PORT.log"

stop_port "$PORT"

# target_exec ends in exec, so the background subshell becomes the server and $! is its pid.
( target_exec "$PORT" ) > "$LOG" 2>&1 &
echo $! > "$PIDFILE"

for _ in $(seq 1 40); do
  if ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Target exited during start; see $LOG" >&2
    exit 1
  fi
  if curl -s -o /dev/null "http://localhost:$PORT/ping"; then
    echo "Target $AET_TARGET up on http://localhost:$PORT (pid $(cat "$PIDFILE"), log $LOG)"
    exit 0
  fi
  sleep 0.25
done
echo "Target failed to start; see $LOG" >&2
exit 1
