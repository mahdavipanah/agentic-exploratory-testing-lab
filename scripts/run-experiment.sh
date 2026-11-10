#!/usr/bin/env bash
# The whole experiment in one command, on your own machine, with your normal Claude Code login.
#
# Usage: scripts/run-experiment.sh [label=batch-<date>] [runs=5] [arms="A B C D M"]
#        AET_TARGET=<name> scripts/run-experiment.sh ...   (a target in targets/<name>/; default restful-booker)
#
# 1. checks prerequisites   2. sets up the target   3. verifies the answer key
# 4. runs one real test session and stops if anything looks wrong   5. runs the batch   6. prints a summary
#
# No token needed: without CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY it uses login isolation
# (see run-arm.sh). Don't use Claude Code yourself while it runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="${1:-batch-$(date +%Y-%m-%d)}"; RUNS="${2:-5}"; ARMS="${3:-A B C D M}"
cd "$ROOT"
. scripts/target-env.sh

step() { printf '\n== %s ==\n' "$1"; }
fail() { printf '\nStopped: %s\n' "$1" >&2; exit 1; }

step "1/5 Prerequisites"
for tool in claude node python3 git curl lsof; do
  command -v "$tool" >/dev/null 2>&1 || fail "'$tool' is not installed (on macOS: brew install $tool, or install Claude Code for 'claude')"
done
node_major=$(node -p 'process.versions.node.split(".")[0]')
[ "$node_major" -ge 20 ] || fail "Node 20 or newer is needed (found $(node -v))"
echo "claude $(claude --version 2>/dev/null | head -1), node $(node -v), $(python3 --version)"

step "2/5 Target: $AET_TARGET"
target_setup
scripts/start-target.sh 3001 >/dev/null || fail "the target did not start"
scripts/start-target.sh stop 3001 >/dev/null
echo "target $AET_TARGET, version $(target_version)"

step "3/5 Answer key"
if [ "$AET_TARGET" = "restful-booker" ]; then
  python3 -I scripts/verify-answer-key.py > "/tmp/aet-verify-$$.txt" || fail "the answer key no longer reproduces; see /tmp/aet-verify-$$.txt"
  tail -1 "/tmp/aet-verify-$$.txt"
else
  echo "sealed until scoring; commitment: $(cat "$TARGET_DIR/answer-key.sha256" 2>/dev/null || echo 'none (targets/'"$AET_TARGET"'/answer-key.sha256 missing)')"
fi

step "4/5 One real test session (about 5 minutes)"
SMOKE="smoke-$LABEL"
rm -rf "results/$SMOKE"
scripts/run-arm.sh A 0 claude 3001 "$SMOKE" || true
S="results/$SMOKE/A-run0-claude"
grep -q '^agent_exit=0$' "$S/meta.txt" || {
  echo "Last lines of the transcript:" >&2; tail -c 1500 "$S/transcript.jsonl" >&2 || true
  fail "the test session did not finish cleanly (see $S). If it says you're not logged in, run 'claude' once and log in."
}
grep -q '^### F' "$S/report.md" || fail "the test session wrote no findings (see $S/report.md)"
grep -q '^report_source=file$' "$S/meta.txt" || fail "the agent could not save report.md itself (permission problem; see $S/transcript.jsonl)"
if grep -q '^login_home_memory_changes=[1-9]' "$S/meta.txt" || grep -q '^fresh_home_memory_files=[1-9]' "$S/meta.txt"; then
  fail "memory files were written during the test session (see $S)"
fi
grep -E '^(isolation|agent_exit|model_used|curl_invocations_executed|report_source|num_turns|total_cost_usd|login_home_memory_changes|fresh_home_memory_files)=' "$S/meta.txt"
rm -rf "results/$SMOKE"

step "5/5 Batch: $RUNS runs of each arm in '$ARMS', shuffled, 4 at a time"
scripts/run-batch.sh "$LABEL" "$RUNS" claude "$ARMS"

step "Summary"
total=0; failed=0; mem=0; files=0; rebuilt=0
for meta in results/"$LABEL"/*/meta.txt; do
  total=$((total + 1))
  grep -q '^agent_exit=0$' "$meta" || failed=$((failed + 1))
  if grep -q -E '^(login_home_memory_changes|fresh_home_memory_files)=[1-9]' "$meta"; then mem=$((mem + 1)); fi
  if grep -q -E '^curl_file_urls=[1-9]' "$meta"; then files=$((files + 1)); fi
  if grep -q '^report_source=transcript$' "$meta"; then rebuilt=$((rebuilt + 1)); fi
done
echo "sessions: $total, failed: $failed, with memory-file changes: $mem, reading local files via curl: $files, reports rebuilt from transcripts: $rebuilt"
[ "$failed" -eq 0 ] || echo "Some sessions failed; rerun them later with AET_RUN_START or scripts/run-arm.sh."
echo
echo "Share the results:"
echo "  git add results/$LABEL && git commit -m \"$LABEL results\" && git push"
