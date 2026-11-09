#!/usr/bin/env bash
# Clone Restful-booker at the pinned commit and install its dependencies.
# Usage: scripts/setup-target.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="619d03162c050baae7d22fdcf983a22f9da6faed"   # 23 Oct 2026, in-memory (LokiJS) storage
DEST="$ROOT/target/restful-booker"

if [ ! -d "$DEST/.git" ]; then
  git clone https://github.com/mwinteringham/restful-booker.git "$DEST"
fi
git -C "$DEST" fetch --quiet origin
git -C "$DEST" checkout --quiet "$COMMIT"
(cd "$DEST" && npm ci --no-audit --no-fund)

# Rebuild the explorer-facing API doc from the pinned version's apidoc data.
python3 -I "$ROOT/scripts/build_api_doc.py" "$DEST/public/apidoc/api_data.json" > "$ROOT/target/api.md"
sed -i.bak '1s/.*/# Booking API documentation/' "$ROOT/target/api.md"
sed -i.bak 's#^Base URL: http://localhost:3001$#Base URL: http://localhost:3001 (see your run instructions for the actual port)#' "$ROOT/target/api.md"
rm -f "$ROOT/target/api.md.bak"
echo "Target ready at $DEST (commit $COMMIT)"
