#!/usr/bin/env bash
# Run one exploration session: fresh target, isolated run directory, one agent CLI.
#
# Usage: scripts/run-arm.sh <A|B|C> <run-number> [agent] [port] [results-label]
#   agent: claude (default) | codex | gemini | dry
#          "dry" runs the whole pipeline without an LLM, to check your setup.
#   port:  3001 by default; use different ports to run arms in parallel
#   label: results folder name, default "runs-<date>"
#
# Environment:
#   AET_MODEL      model to pass to the agent CLI (claude/codex), e.g. "claude-opus-5-5"
#   AET_MAX_TURNS  claude only, default 150
#
# The agent only gets: the composed prompt and a copy of target/api.md in a temp directory.
# It never sees this repo, the answer key or other runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARM="$1"; RUN="$2"; AGENT="${3:-claude}"; PORT="${4:-3001}"
LABEL="${5:-runs-$(date +%Y-%m-%d)}"
MODEL="${AET_MODEL:-}"

[ -f "$ROOT/target/api.md" ] || { echo "target/api.md missing: run scripts/setup-target.sh first" >&2; exit 1; }

OUT="$ROOT/results/$LABEL/$ARM-run$RUN-$AGENT"
RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aet-run-XXXXXX")"
mkdir -p "$OUT"

# Always stop the target and remove the temp dir, even if the agent fails.
trap '"$ROOT/scripts/start-target.sh" stop "$PORT" >/dev/null 2>&1 || true; rm -rf "$RUN_DIR"' EXIT

"$ROOT/scripts/start-target.sh" "$PORT"
cp "$ROOT/target/api.md" "$RUN_DIR/api.md"
"$ROOT/scripts/compose-prompt.sh" "$ARM" "$PORT" "$RUN_DIR" > "$OUT/prompt.md"
PROMPT="$(cat "$OUT/prompt.md")"
START=$(date +%s)
AGENT_VERSION="n/a"

cd "$RUN_DIR"
set +e   # record a failing agent instead of aborting
case "$AGENT" in
  claude)
    AGENT_VERSION="$(claude --version 2>/dev/null | head -1)"
    # --safe-mode: no CLAUDE.md, skills, plugins, hooks, MCP servers or custom agents from your setup.
    # --tools: only these built-in tools exist; --allowedTools: and only these uses are permitted.
    # Anything else is denied in -p mode, so the agent can run curl, read api.md and write report.md.
    claude -p "$PROMPT" \
      ${MODEL:+--model "$MODEL"} \
      --safe-mode --strict-mcp-config --no-session-persistence \
      --tools "Bash,Read,Write,Edit" \
      --allowedTools "Bash(curl:*)" "Read(./api.md)" "Write(./report.md)" "Edit(./report.md)" \
      --max-turns "${AET_MAX_TURNS:-150}" \
      --output-format stream-json --verbose < /dev/null > "$OUT/transcript.jsonl"
    ;;
  codex)
    # Untested adapter: network must be allowed inside the sandbox for curl to reach localhost.
    AGENT_VERSION="$(codex --version 2>/dev/null | head -1)"
    codex exec --skip-git-repo-check --sandbox workspace-write \
      -c sandbox_workspace_write.network_access=true \
      ${MODEL:+-m "$MODEL"} \
      "$PROMPT" < /dev/null > "$OUT/transcript.txt" 2>&1
    ;;
  gemini)
    # Untested adapter.
    AGENT_VERSION="$(gemini --version 2>/dev/null | head -1)"
    gemini -p "$PROMPT" --yolo < /dev/null > "$OUT/transcript.txt" 2>&1
    ;;
  dry)
    # No LLM: touch the API once and write a placeholder report, to test the pipeline.
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/ping")
    printf '# Exploration report\n\n## Charters\nnone (dry run)\n\n## Findings\n\n## Questions\n\n## Coverage\nDry run: GET /ping returned %s. 1 request.\n' "$code" > "$RUN_DIR/report.md"
    echo "dry run, no transcript" > "$OUT/transcript.txt"
    ;;
  *) echo "Unknown agent: $AGENT" >&2; exit 1 ;;
esac
AGENT_EXIT=$?
set -e

END=$(date +%s)
cp "$RUN_DIR/report.md" "$OUT/report.md" 2>/dev/null || echo "No report.md written" > "$OUT/report.md"
{
  printf 'arm=%s\nrun=%s\nagent=%s\nagent_version=%s\nmodel=%s\nport=%s\nseconds=%s\n' \
    "$ARM" "$RUN" "$AGENT" "$AGENT_VERSION" "${MODEL:-cli default}" "$PORT" "$((END-START))"
  printf 'agent_exit=%s\ntarget_commit=%s\n' "$AGENT_EXIT" "$(git -C "$ROOT/target/restful-booker" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  [ -f "$OUT/transcript.jsonl" ] && python3 -I "$ROOT/scripts/transcript_stats.py" "$OUT/transcript.jsonl"
} > "$OUT/meta.txt"
[ "$AGENT_EXIT" -eq 0 ] || echo "warning: $AGENT exited with status $AGENT_EXIT; see $OUT" >&2
echo "Done: $OUT"
