#!/usr/bin/env bash
# Print the full prompt for one arm: shared rules + arm text, with placeholders filled.
# Usage: scripts/compose-prompt.sh <A|B|C> <port> <run-dir>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARM="$1"; PORT="$2"; RUN_DIR="$3"

case "$ARM" in
  A) ARM_FILE="$ROOT/arms/A-baseline.md" ;;
  B) ARM_FILE="$ROOT/arms/B-human-charters.md" ;;
  C) ARM_FILE="$ROOT/arms/C-agent-charters.md" ;;
  *) echo "Unknown arm: $ARM (use A, B or C)" >&2; exit 1 ;;
esac

python3 -I - "$ROOT/arms/shared-rules.md" "$ARM_FILE" "$ROOT/arms/tours.md" "$PORT" "$RUN_DIR" <<'EOF'
import sys
rules, arm, tours, port, run_dir = sys.argv[1:6]
text = open(rules).read().rstrip() + "\n\n" + open(arm).read().strip() + "\n"
text = text.replace("{{TOURS}}", open(tours).read().strip())
text = text.replace("{{PORT}}", port).replace("{{RUN_DIR}}", run_dir)
sys.stdout.write(text)
EOF
