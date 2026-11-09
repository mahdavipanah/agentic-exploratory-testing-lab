#!/usr/bin/env bash
# Start (or restart) a fresh Restful-booker on a port. Restarting resets all data to the seed.
# Usage: scripts/start-target.sh [port]     (default 3001)
#        scripts/start-target.sh stop [port]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/target/restful-booker"

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

# exec makes the background subshell become node, so $! is node's pid.
# TZ is pinned to UTC: the target formats dates in local time, so in timezones
# west of UTC every date shifts back a day (see scoring/answer-key.md, "Environment-dependent").
( cd "$DEST" && PORT="$PORT" SEED=true TZ=UTC exec node ./bin/www ) > "$LOG" 2>&1 &
echo $! > "$PIDFILE"

for _ in $(seq 1 40); do
  if ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Target exited during start; see $LOG" >&2
    exit 1
  fi
  if curl -s -o /dev/null "http://localhost:$PORT/ping"; then
    echo "Target up on http://localhost:$PORT (pid $(cat "$PIDFILE"), log $LOG)"
    exit 0
  fi
  sleep 0.25
done
echo "Target failed to start; see $LOG" >&2
exit 1
