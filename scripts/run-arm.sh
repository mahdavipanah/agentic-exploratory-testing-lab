#!/usr/bin/env bash
# Run one exploration session: fresh target, isolated run directory, one agent CLI.
#
# Usage: scripts/run-arm.sh <A|B|C> <run-number> [agent] [port] [results-label]
#   agent: claude (default) | codex | gemini
#   port:  3001 by default; use different ports to run arms in parallel
#   label: results folder name, default "runs-<date>"
#
# The agent only gets: the composed prompt and a copy of target/api.md in a temp directory.
# It never sees this repo, the answer key or other runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARM="$1"; RUN="$2"; AGENT="${3:-claude}"; PORT="${4:-3001}"
LABEL="${5:-runs-$(date +%Y-%m-%d)}"

OUT="$ROOT/results/$LABEL/$ARM-run$RUN-$AGENT"
RUN_DIR="$(mktemp -d /tmp/aet-run-XXXXXX)"
mkdir -p "$OUT"

"$ROOT/scripts/start-target.sh" "$PORT"
cp "$ROOT/target/api.md" "$RUN_DIR/api.md"
"$ROOT/scripts/compose-prompt.sh" "$ARM" "$PORT" "$RUN_DIR" > "$OUT/prompt.md"
PROMPT="$(cat "$OUT/prompt.md")"
START=$(date +%s)

cd "$RUN_DIR"
case "$AGENT" in
  claude)
    # Only curl, reading the docs and writing the report are allowed; everything else is denied in -p mode.
    claude -p "$PROMPT" \
      --allowedTools "Bash(curl:*)" "Read(./api.md)" "Write(./report.md)" "Edit(./report.md)" \
      --disallowedTools "WebFetch" "WebSearch" "Task" \
      --max-turns 150 \
      --output-format stream-json --verbose > "$OUT/transcript.jsonl"
    ;;
  codex)
    # Untested adapter: network must be allowed inside the sandbox for curl to reach localhost.
    codex exec --skip-git-repo-check --sandbox workspace-write \
      -c sandbox_workspace_write.network_access=true \
      "$PROMPT" > "$OUT/transcript.txt" 2>&1
    ;;
  gemini)
    # Untested adapter.
    gemini -p "$PROMPT" --yolo > "$OUT/transcript.txt" 2>&1
    ;;
  *) echo "Unknown agent: $AGENT" >&2; exit 1 ;;
esac

END=$(date +%s)
cp "$RUN_DIR/report.md" "$OUT/report.md" 2>/dev/null || echo "No report.md written" > "$OUT/report.md"
printf 'arm=%s\nrun=%s\nagent=%s\nport=%s\nseconds=%s\n' "$ARM" "$RUN" "$AGENT" "$PORT" "$((END-START))" > "$OUT/meta.txt"
"$ROOT/scripts/start-target.sh" stop "$PORT"
echo "Done: $OUT"
