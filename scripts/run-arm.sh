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
#   AET_ISOLATION      claude only: "fresh", "login" or "bare". Default: fresh when CLAUDE_CODE_OAUTH_TOKEN or
#                      ANTHROPIC_API_KEY is set, otherwise login.
#                      fresh: --safe-mode with a brand-new, empty Claude Code home (CLAUDE_CONFIG_DIR), deleted
#                             after the run, and auto-memory off (CLAUDE_CODE_DISABLE_AUTO_MEMORY=1). Nothing is
#                             shared between runs. Needs CLAUDE_CODE_OAUTH_TOKEN (`claude setup-token`) or
#                             ANTHROPIC_API_KEY, because the empty home has no login.
#                      login: --safe-mode with your normal Claude Code login (no token needed), auto-memory off
#                             (CLAUDE_CODE_DISABLE_AUTO_MEMORY=1) and no session saved. The home is shared, so
#                             every run audits it: memory files new or changed during the run are counted in
#                             meta.txt (expected 0). Don't use Claude Code yourself while a batch runs.
#                      bare:  claude --bare (no CLAUDE.md, auto-memory, hooks, plugins, LSP or keychain);
#                             needs ANTHROPIC_API_KEY.
#   CLAUDE_CODE_OAUTH_TOKEN  subscription token for fresh mode (optional)
#   ANTHROPIC_API_KEY        API key for bare or fresh mode (optional)
#   AET_ORDER          set by run-batch.sh: this session's position in the shuffled schedule
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

CONFIG_HOME=""
if [ "$AGENT" = "claude" ]; then
  if [ -n "${AET_ISOLATION:-}" ]; then
    ISOLATION="$AET_ISOLATION"
  elif [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] || [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    ISOLATION="fresh"
  else
    ISOLATION="login"
  fi
  [ "$ISOLATION" = "safe" ] && ISOLATION="login"   # older name
  case "$ISOLATION" in
    fresh)
      if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        echo "Fresh isolation starts each run with an empty Claude Code home, so it has no saved login." >&2
        echo "Export CLAUDE_CODE_OAUTH_TOKEN (from 'claude setup-token') or ANTHROPIC_API_KEY," >&2
        echo "or use AET_ISOLATION=login to run with your normal Claude Code login." >&2
        exit 2
      fi
      ISO_FLAG="--safe-mode" ;;
    login) ISO_FLAG="--safe-mode" ;;
    bare)
      if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        echo "Bare isolation needs ANTHROPIC_API_KEY: claude --bare does not use a subscription login." >&2
        exit 2
      fi
      ISO_FLAG="--bare" ;;
    *) echo "AET_ISOLATION must be fresh, login or bare, not '$ISOLATION'" >&2; exit 2 ;;
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
# Resolve the real path (pwd -P). On macOS $TMPDIR is under /var, a symlink to /private/var, and the CLI
# matches its permission rules against the resolved path: a prompt that names the /var spelling gets the
# report write denied (this happened in batch-1; see results/batch-1/README.md).
RUN_DIR="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/aet-run-XXXXXX")" && pwd -P)"
mkdir -p "$OUT"

if [ "$ISOLATION" = "fresh" ]; then
  CONFIG_HOME="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/aet-home-XXXXXX")" && pwd -P)"
fi

# Always stop the target and remove the temp dirs, even if the agent fails.
trap '"$ROOT/scripts/start-target.sh" stop "$PORT" >/dev/null 2>&1 || true; rm -rf "$RUN_DIR" "$RUN_DIR".home-*.json; [ -z "$CONFIG_HOME" ] || rm -rf "$CONFIG_HOME"' EXIT

[ "$ARM" = "M" ] || "$ROOT/scripts/start-target.sh" "$PORT"
cp "$ROOT/target/api.md" "$RUN_DIR/api.md"
"$ROOT/scripts/compose-prompt.sh" "$ARM" "$PORT" "$RUN_DIR" > "$OUT/prompt.md"
PROMPT="$(cat "$OUT/prompt.md")"
START=$(date +%s)
AGENT_VERSION="n/a"

# A clean environment for the agent: only what it needs to run and authenticate.
CLEAN_ENV=(env -i "HOME=$HOME" "PATH=$PATH" "LANG=${LANG:-en_US.UTF-8}" "TERM=${TERM:-dumb}" "TMPDIR=${TMPDIR:-/tmp}")
for var in USER ANTHROPIC_API_KEY ANTHROPIC_BASE_URL CLAUDE_CODE_OAUTH_TOKEN HTTPS_PROXY HTTP_PROXY NO_PROXY \
           https_proxy http_proxy no_proxy NODE_EXTRA_CA_CERTS SSL_CERT_FILE OPENAI_API_KEY GEMINI_API_KEY GOOGLE_API_KEY; do
  val="$(printenv "$var" || true)"
  if [ -n "$val" ]; then CLEAN_ENV+=("$var=$val"); fi
done
case "$ISOLATION" in
  fresh) CLEAN_ENV+=("CLAUDE_CONFIG_DIR=$CONFIG_HOME" "CLAUDE_CODE_DISABLE_AUTO_MEMORY=1") ;;
  login) CLEAN_ENV+=("CLAUDE_CODE_DISABLE_AUTO_MEMORY=1")
         val="$(printenv CLAUDE_CONFIG_DIR || true)"
         if [ -n "$val" ]; then CLEAN_ENV+=("CLAUDE_CONFIG_DIR=$val"); fi
         LOGIN_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
         python3 -I "$ROOT/scripts/home_audit.py" snapshot "$LOGIN_HOME" "$RUN_DIR.home-before.json" ;;
esac

cd "$RUN_DIR"
set +e   # record a failing agent instead of aborting
case "$AGENT" in
  claude)
    AGENT_VERSION="$(claude --version 2>/dev/null | head -1)"
    # fresh: an empty Claude Code home just for this run, auto-memory off, deleted afterwards.
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
# Login isolation: which memory files in your Claude Code home appeared or changed during the run (expected none).
if [ "$ISOLATION" = "login" ]; then
  python3 -I "$ROOT/scripts/home_audit.py" snapshot "$LOGIN_HOME" "$RUN_DIR.home-after.json"
  python3 -I "$ROOT/scripts/home_audit.py" diff "$RUN_DIR.home-before.json" "$RUN_DIR.home-after.json" > "$OUT/login-home-memory-changes.txt"
  rm -f "$RUN_DIR.home-before.json" "$RUN_DIR.home-after.json"
fi
# Audit the fresh home before it is deleted: file names only, never contents (it may hold account data).
if [ -n "$CONFIG_HOME" ]; then
  (cd "$CONFIG_HOME" && find . -type f | sed 's|^\./||' | sort) > "$OUT/fresh-home-files.txt"
fi
{
  printf 'arm=%s\nrun=%s\nagent=%s\nagent_version=%s\nisolation=%s\nmodel=%s\nport=%s\nseconds=%s\n' \
    "$ARM" "$RUN" "$AGENT" "$AGENT_VERSION" "$ISOLATION" "${MODEL:-cli default}" "$PORT" "$((END-START))"
  printf 'agent_exit=%s\ntarget_commit=%s\norder=%s\n' "$AGENT_EXIT" "$(git -C "$ROOT/target/restful-booker" rev-parse --short HEAD 2>/dev/null || echo unknown)" "${AET_ORDER:-n/a}"
  if [ "$ISOLATION" = "login" ]; then
    printf 'auto_memory=disabled\nlogin_home_memory_changes=%s\n' "$(grep -c . "$OUT/login-home-memory-changes.txt" || true)"
  fi
  if [ -n "$CONFIG_HOME" ]; then
    printf 'auto_memory=disabled\nfresh_home_files=%s\nfresh_home_memory_files=%s\n' \
      "$(wc -l < "$OUT/fresh-home-files.txt" | tr -d ' ')" "$(grep -c -i 'memory' "$OUT/fresh-home-files.txt" || true)"
  fi
  if [ -f "$OUT/transcript.jsonl" ]; then
    python3 -I "$ROOT/scripts/transcript_stats.py" "$OUT/transcript.jsonl"
    # If the report was not saved, rebuild it from the agent's own Write/Edit calls (report_source=transcript).
    python3 -I "$ROOT/scripts/recover-report.py" "$OUT"
  fi
} > "$OUT/meta.txt"
if grep -q '^report_source=transcript$' "$OUT/meta.txt"; then
  echo "warning: the agent's report write was refused; report.md was rebuilt from the transcript." >&2
fi
[ "$AGENT_EXIT" -eq 0 ] || echo "warning: $AGENT exited with status $AGENT_EXIT; see $OUT" >&2
if [ "$ISOLATION" = "login" ] && grep -q . "$OUT/login-home-memory-changes.txt"; then
  echo "warning: memory files in your Claude Code home changed during this run (see $OUT/login-home-memory-changes.txt)." >&2
  echo "         If you used Claude Code yourself meanwhile, that may be the cause." >&2
fi
if [ -n "$CONFIG_HOME" ] && grep -q -i 'memory' "$OUT/fresh-home-files.txt"; then
  echo "warning: memory files appeared in the fresh home despite CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 (deleted now; see $OUT/fresh-home-files.txt)" >&2
fi
echo "Done: $OUT"
