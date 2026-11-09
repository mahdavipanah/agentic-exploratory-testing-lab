#!/usr/bin/env bash
# Run a whole batch: every arm, N runs each. Arms run in parallel (one port each); runs go one after another.
#
# Usage: scripts/run-batch.sh <label> [runs=3] [agent=claude] [arms="A B C D"]
# Example: ANTHROPIC_API_KEY=... AET_MODEL=claude-opus-5-5 scripts/run-batch.sh batch-1 3 claude "A B C D M"
#   Arm M (memory check: docs only, no API) is opt-in; add it to the arms list.
#   claude runs in bare isolation by default (needs ANTHROPIC_API_KEY); see run-arm.sh.
#
# Results: results/<label>/<arm>-run<n>-<agent>/  (prompt.md, transcript, report.md, meta.txt)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="$1"; RUNS="${2:-3}"; AGENT="${3:-claude}"; ARMS="${4:-A B C D}"

[ -f "$ROOT/target/api.md" ] || "$ROOT/scripts/setup-target.sh"

if [ "$AGENT" = "claude" ] && [ "${AET_ISOLATION:-bare}" = "bare" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "Bare isolation needs ANTHROPIC_API_KEY (claude --bare does not use a subscription login)." >&2
  echo "Set it, or run with AET_ISOLATION=safe (those runs are marked isolation=safe)." >&2
  exit 2
fi

for run in $(seq 1 "$RUNS"); do
  echo "== run $run of $RUNS =="
  port=3001
  pids=()
  for arm in $ARMS; do
    "$ROOT/scripts/run-arm.sh" "$arm" "$run" "$AGENT" "$port" "$LABEL" > "/tmp/aet-$LABEL-$arm-$run.log" 2>&1 &
    pids+=("$!")
    echo "started arm $arm on port $port (log /tmp/aet-$LABEL-$arm-$run.log)"
    port=$((port + 1))
  done
  status=0
  for pid in "${pids[@]}"; do wait "$pid" || status=1; done
  [ "$status" -eq 0 ] || echo "warning: at least one session in run $run failed; see the logs" >&2
done

echo
echo "Batch done: results/$LABEL"
echo "Next: python3 -I scripts/extract-findings.py results/$LABEL > scoring/scores-$LABEL.csv"
echo "      fill key_ids and verdict for every finding, then"
echo "      python3 -I scripts/score.py scoring/scores-$LABEL.csv 38"
