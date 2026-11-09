#!/usr/bin/env bash
# Run a whole batch: every arm, N runs each, in a shuffled order.
#
# Usage: scripts/run-batch.sh <label> [runs=5] [agent=claude] [arms="A B C D"]
# Example (your normal Claude Code login, no token: login isolation):
#   AET_MODEL=claude-opus-5-5 scripts/run-batch.sh batch-1 5 claude "A B C D M"
# With CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY exported, runs use fresh isolation instead.
#
# All (arm, run) sessions are shuffled into one schedule, then run in waves of AET_PARALLEL
# (default 4) sessions at a time, each on its own port. Shuffling separates "when a session ran"
# from "which arm it was", so scripts/score.py can check that later sessions did not do better
# (which would hint at carry-over between runs).
#
# Environment:
#   AET_SEED       shuffle seed (default: random, recorded in schedule.txt)
#   AET_PARALLEL   sessions at a time (default 4)
#   AET_RUN_START  first run number (default 1); use it to add more runs to an existing label later
#   AET_ISOLATION, AET_MODEL, ...: passed through to run-arm.sh
#
# Results: results/<label>/<arm>-run<n>-<agent>/ plus results/<label>/schedule.txt
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="$1"; RUNS="${2:-5}"; AGENT="${3:-claude}"; ARMS="${4:-A B C D}"
PARALLEL="${AET_PARALLEL:-4}"; START="${AET_RUN_START:-1}"
SEED="${AET_SEED:-$RANDOM$RANDOM}"

[ -f "$ROOT/target/api.md" ] || "$ROOT/scripts/setup-target.sh"

ISOLATION="n/a"
if [ "$AGENT" = "claude" ]; then
  if [ -n "${AET_ISOLATION:-}" ]; then ISOLATION="$AET_ISOLATION"
  elif [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] || [ -n "${ANTHROPIC_API_KEY:-}" ]; then ISOLATION="fresh"
  else ISOLATION="login"; fi
  case "$ISOLATION" in
    fresh) if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
             echo "Fresh isolation needs CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY; or use AET_ISOLATION=login." >&2
             exit 2
           fi ;;
    bare)  if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
             echo "Bare isolation needs ANTHROPIC_API_KEY." >&2; exit 2
           fi ;;
    login|safe) ;;
    *) echo "AET_ISOLATION must be fresh, login or bare" >&2; exit 2 ;;
  esac
  if [ "$ISOLATION" = "login" ] || [ "$ISOLATION" = "safe" ]; then
    echo "Using your normal Claude Code login (login isolation). Please don't use Claude Code yourself until the batch ends."
  fi
fi

mkdir -p "$ROOT/results/$LABEL"
SCHEDULE="$ROOT/results/$LABEL/schedule.txt"
# Continue the order numbering if runs are being added to an existing batch.
OFFSET=0
[ -f "$SCHEDULE" ] && OFFSET=$(grep -c '^[0-9]' "$SCHEDULE" || true)
[ -f "$SCHEDULE" ] || printf '# order arm run port wave started_utc\n' > "$SCHEDULE"
printf '# seed=%s runs=%s-%s arms=%s agent=%s isolation=%s parallel=%s\n' \
  "$SEED" "$START" "$((START + RUNS - 1))" "$ARMS" "$AGENT" "$ISOLATION" "$PARALLEL" >> "$SCHEDULE"

# Build and shuffle the job list with a recorded seed (portable: no shuf on macOS).
JOBS=$(python3 -I - "$SEED" "$START" "$RUNS" $ARMS <<'EOF'
import random, sys
seed, start, runs, arms = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:]
jobs = [f"{a}:{r}" for r in range(start, start + runs) for a in arms]
random.Random(seed).shuffle(jobs)
print(" ".join(jobs))
EOF
)

order=$OFFSET; wave=0
set -- $JOBS
while [ "$#" -gt 0 ]; do
  wave=$((wave + 1)); port=3001; pids=()
  echo "== wave $wave =="
  for _ in $(seq 1 "$PARALLEL"); do
    [ "$#" -gt 0 ] || break
    job="$1"; shift
    arm="${job%%:*}"; run="${job##*:}"; order=$((order + 1))
    printf '%s %s %s %s %s %s\n' "$order" "$arm" "$run" "$port" "$wave" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$SCHEDULE"
    AET_ORDER="$order" "$ROOT/scripts/run-arm.sh" "$arm" "$run" "$AGENT" "$port" "$LABEL" \
      > "/tmp/aet-$LABEL-$arm-$run.log" 2>&1 &
    pids+=("$!")
    echo "  #$order arm $arm run $run on port $port (log /tmp/aet-$LABEL-$arm-$run.log)"
    port=$((port + 1))
  done
  status=0
  for pid in "${pids[@]}"; do wait "$pid" || status=1; done
  [ "$status" -eq 0 ] || echo "warning: a session in wave $wave failed; see the logs" >&2
done

echo
echo "Batch done: results/$LABEL (schedule: results/$LABEL/schedule.txt, seed $SEED)"
echo "Next: python3 -I scripts/extract-findings.py results/$LABEL > scoring/scores-$LABEL.csv"
echo "      fill key_ids and verdict for every finding, then"
echo "      python3 -I scripts/score.py scoring/scores-$LABEL.csv 38 --schedule results/$LABEL/schedule.txt"
