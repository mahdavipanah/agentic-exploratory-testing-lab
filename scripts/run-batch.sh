#!/usr/bin/env bash
# Run a whole batch: every arm, N runs each. Arms run in parallel (one port each); runs go one after another.
#
# Usage: scripts/run-batch.sh <label> [runs=3] [agent=claude] [arms="A B C"]
# Example: AET_MODEL=claude-opus-5-5 scripts/run-batch.sh batch-2026-11-10 3
#
# Results: results/<label>/<arm>-run<n>-<agent>/  (prompt.md, transcript, report.md, meta.txt)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="$1"; RUNS="${2:-3}"; AGENT="${3:-claude}"; ARMS="${4:-A B C}"

[ -f "$ROOT/target/api.md" ] || "$ROOT/scripts/setup-target.sh"

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
