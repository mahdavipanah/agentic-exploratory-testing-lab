#!/usr/bin/env bash
# Print the full prompt for one arm: shared rules + arm text, with placeholders filled.
# Usage: scripts/compose-prompt.sh <A|B|C|D> <port> <run-dir>
#   D inlines skills/exploratory-testing (SKILL.md and its references).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARM="$1"; PORT="$2"; RUN_DIR="$3"

case "$ARM" in
  A) ARM_FILE="$ROOT/arms/A-baseline.md" ;;
  B) ARM_FILE="$ROOT/arms/B-human-charters.md" ;;
  C) ARM_FILE="$ROOT/arms/C-agent-charters.md" ;;
  D) ARM_FILE="$ROOT/arms/D-skill.md" ;;
  *) echo "Unknown arm: $ARM (use A, B, C or D)" >&2; exit 1 ;;
esac

python3 -I - "$ROOT" "$ARM_FILE" "$PORT" "$RUN_DIR" <<'EOF'
import glob
import os
import sys

root, arm, port, run_dir = sys.argv[1:5]
read = lambda p: open(p, encoding="utf-8").read()

skill_dir = os.path.join(root, "skills", "exploratory-testing")
skill = read(os.path.join(skill_dir, "SKILL.md")).strip()
for ref in sorted(glob.glob(os.path.join(skill_dir, "references", "*.md"))):
    rel = os.path.relpath(ref, skill_dir)
    skill += f"\n\n---\n\n<!-- file: {rel} -->\n\n" + read(ref).strip()

text = read(os.path.join(root, "arms", "shared-rules.md")).rstrip() + "\n\n" + read(arm).strip() + "\n"
text = text.replace("{{TOURS}}", read(os.path.join(root, "arms", "tours.md")).strip())
text = text.replace("{{SKILL}}", skill)
text = text.replace("{{PORT}}", port).replace("{{RUN_DIR}}", run_dir)
sys.stdout.write(text)
EOF
