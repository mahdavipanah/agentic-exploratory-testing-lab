#!/usr/bin/env bash
# Start (or restart) a fresh Restful-booker on a port. Restarting resets all data to the seed.
# Usage: scripts/start-target.sh [port]     (default 3001)
#        scripts/start-target.sh stop [port]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/target/restful-booker"

if [ "${1:-}" = "stop" ]; then
  PORT="${2:-3001}"
  PIDFILE="/tmp/aet-target-$PORT.pid"
  [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null || true
  rm -f "$PIDFILE"
  echo "Stopped target on port $PORT"
  exit 0
fi

PORT="${1:-3001}"
PIDFILE="/tmp/aet-target-$PORT.pid"
LOG="/tmp/aet-target-$PORT.log"

[ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null || true
sleep 1

(cd "$DEST" && PORT="$PORT" SEED=true nohup node ./bin/www > "$LOG" 2>&1 & echo $! > "$PIDFILE")

for _ in $(seq 1 20); do
  if curl -s -o /dev/null "http://localhost:$PORT/ping"; then
    echo "Target up on http://localhost:$PORT (pid $(cat "$PIDFILE"), log $LOG)"
    exit 0
  fi
  sleep 0.5
done
echo "Target failed to start; see $LOG" >&2
exit 1
