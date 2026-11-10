#!/usr/bin/env bash
# Run the Claimdesk API in the foreground with fresh seed data.
# Usage: start.sh <port>
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <port>" >&2
  exit 2
fi

DIR="$(cd "$(dirname "$0")" && pwd)"
export PORT="$1"
export TZ=UTC
exec node "$DIR/server.js"
