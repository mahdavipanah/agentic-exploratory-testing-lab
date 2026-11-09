#!/usr/bin/env bash
# Run one exploration session: fresh target, isolated run directory, one agent CLI.
#
# Usage: scripts/run-arm.sh <A|B|C|D|M> <run-number> [agent] [port] [results-label]
#   arm:   A-D explore the API; M is the memory check (docs only, no API access)
#   agent: claude (default) | codex | gemini | dry
#          "dry" runs the whole pipeline without an LLM, to check your setup.
#   port:  3001 by default; use different ports to run arms in parallel
#   label: results folder name, default "runs-<date>"
#
# Environment:
#   ANTHROPIC_API_KEY  required for claude in bare mode (the default)
#   AET_ISOLATION      claude only: "bare" (default) or "safe"
#                      bare: claude --bare. No CLAUDE.md, auto-memory, hooks, plugins, LSP or keychain;
#                            authenticates only with ANTHROPIC_API_KEY. Use this for results you report.
#                      safe: claude --safe-mode. Works with a subscription login, but auto-memory is not
#                            explicitly disabled. Runs are marked isolation=safe in meta.txt.
#   AET_MODEL          model to pass to the agent CLI (claude/codex), e.g. "claude-opus-5-5"
#   AET_MAX_TURNS      claude only, default 150
#
# The agent only gets: the composed prompt and a copy of target/api.md in a temp directory, started with a
# clean environment (no variables inherited from a parent Claude Code session).
# It never sees this repo, the answer key or other runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARM="$1"; RUN="$2"; AGENT="${3:-claude}"; PORT="${4:-3001}"
LABEL="${5:-runs-$(date +%Y-%m-%d)}"
MODEL="${AET_MODEL:-}"
ISOLATION="n/a"

[ -f "$ROOT/target/api.md" ] || { echo "target/api.md missing: run scripts/setup-target.sh first" >&2; exit 1; }

if [ "$AGENT" = "claude" ]; then
  ISOLATION="${AET_ISOLATION:-bare}"
  case "$ISOLATION" in
    bare)
      if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        echo "Bare isolation needs ANTHROPIC_API_KEY: claude --bare does not use a subscription login." >&2
        echo "Set it, or run with AET_ISOLATION=safe (those runs are marked isolation=safe)." >&2
        exit 2
      fi
      ISO_FLAG="--bare" ;;
    safe) ISO_FLAG="--safe-mode" ;;
    *) echo "AET_ISOLATION must be bare or safe, not '$ISOLATION'" >&2; exit 2 ;;
  esac
fi

# Arm M (memory check) never touches the API, so it gets no curl and no target.
if [ "$ARM" = "M" ]; then
  TOOLS="Read,Write,Edit"
  ALLOWED=("Read(./api.md)" "Write(./report.md)" "Edit(./report.md)")
else
  TOOLS="Bash,Read,Write,Edit"
  ALLOWED=("Bash(curl:*)" "Read(./api.md)" "Write(./report.md)" "Edit(./report.md)")
fi

OUT="$ROOT/results/$LABEL/$ARM-run$RUN-$AGENT"
RUN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aet-run-XXXXXX")"
mkdir -p "$OUT"

# Always stop the target and remove the temp dir, even if the agent fails.
trap '"$ROOT/scripts/start-target.sh" stop "$PORT" >/dev/null 2>&1 || true; rm -rf "$RUN_DIR"' EXIT

[ "$ARM" = "M" ] || "$ROOT/scripts/start-target.sh" "$PORT"
cp "$ROOT/target/api.md" "$RUN_DIR/api.md"
"$ROOT/scripts/compose-prompt.sh" "$ARM" "$PORT" "$RUN_DIR" > "$OUT/prompt.md"
PROMPT="$(cat "$OUT/prompt.md")"
START=$(date +%s)
AGENT_VERSION="n/a"

# A clean environment for the agent: only what it needs to run and authenticate.
CLEAN_ENV=(env -i "HOME=$HOME" "PATH=$PATH" "LANG=${LANG:-en_US.UTF-8}" "TERM=${TERM:-dumb}" "TMPDIR=${TMPDIR:-/tmp}")
for var in USER ANTHROPIC_API_KEY ANTHROPIC_BASE_URL HTTPS_PROXY HTTP_PROXY NO_PROXY https_proxy http_proxy no_proxy \
           NODE_EXTRA_CA_CERTS SSL_CERT_FILE OPENAI_API_KEY GEMINI_API_KEY GOOGLE_API_KEY; do
  if [ -n "${!var:-}" ]; then CLEAN_ENV+=("$var=${!var}"); fi
done

cd "$RUN_DIR"
set +e   # record a failing agent instead of aborting
case "$AGENT" in
  claude)
    AGENT_VERSION="$(claude --version 2>/dev/null | head -1)"
    # --bare / --safe-mode: none of your own CLAUDE.md, skills, hooks or plugins.
    # --setting-sources project: settings only from the (empty) run directory, so your
    #   personal permission rules can't widen what the agent may do.
    # --tools: only these built-in tools exist; --allowedTools: and only these uses are permitted.
    # Anything else is denied in -p mode.
    "${CLEAN_ENV[@]}" claude -p "$PROMPT" \
      ${MODEL:+--model "$MODEL"} \
      "$ISO_FLAG" --setting-sources project --strict-mcp-config --no-session-persistence \
      --tools "$TOOLS" \
      --allowedTools "${ALLOWED[@]}" \
      --max-turns "${AET_MAX_TURNS:-150}" \
      --output-format stream-json --verbose < /dev/null > "$OUT/transcript.jsonl"
    ;;
  codex)
    # Untested adapter: network must be allowed inside the sandbox for curl to reach localhost.
    AGENT_VERSION="$(codex --version 2>/dev/null | head -1)"
    "${CLEAN_ENV[@]}" codex exec --skip-git-repo-check --sandbox workspace-write \
      -c sandbox_workspace_write.network_access=true \
      ${MODEL:+-m "$MODEL"} \
      "$PROMPT" < /dev/null > "$OUT/transcript.txt" 2>&1
    ;;
  gemini)
    # Untested adapter.
    AGENT_VERSION="$(gemini --version 2>/dev/null | head -1)"
    "${CLEAN_ENV[@]}" gemini -p "$PROMPT" --yolo < /dev/null > "$OUT/transcript.txt" 2>&1
    ;;
  dry)
    # No LLM: touch the API once (if this arm has one) and write a placeholder report.
    code="n/a"
    [ "$ARM" = "M" ] || code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/ping")
    printf '# Exploration report\n\n## Charters\nnone (dry run)\n\n## Findings\n\n## Questions\n\n## Coverage\nDry run: GET /ping returned %s.\n' "$code" > "$RUN_DIR/report.md"
    echo "dry run, no transcript" > "$OUT/transcript.txt"
    ;;
  *) echo "Unknown agent: $AGENT" >&2; exit 1 ;;
esac
AGENT_EXIT=$?
set -e

END=$(date +%s)
cp "$RUN_DIR/report.md" "$OUT/report.md" 2>/dev/null || echo "No report.md written" > "$OUT/report.md"
{
  printf 'arm=%s\nrun=%s\nagent=%s\nagent_version=%s\nisolation=%s\nmodel=%s\nport=%s\nseconds=%s\n' \
    "$ARM" "$RUN" "$AGENT" "$AGENT_VERSION" "$ISOLATION" "${MODEL:-cli default}" "$PORT" "$((END-START))"
  printf 'agent_exit=%s\ntarget_commit=%s\n' "$AGENT_EXIT" "$(git -C "$ROOT/target/restful-booker" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  [ -f "$OUT/transcript.jsonl" ] && python3 -I "$ROOT/scripts/transcript_stats.py" "$OUT/transcript.jsonl"
} > "$OUT/meta.txt"
[ "$AGENT_EXIT" -eq 0 ] || echo "warning: $AGENT exited with status $AGENT_EXIT; see $OUT" >&2
echo "Done: $OUT"
