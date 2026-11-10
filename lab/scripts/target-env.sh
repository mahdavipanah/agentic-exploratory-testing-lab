# Sourced by the other scripts (needs ROOT set). Resolves the target chosen by AET_TARGET.
#
#   AET_TARGET=restful-booker (default)  Restful-booker, cloned by scripts/setup-target.sh into target/
#   AET_TARGET=<name>                    targets/<name>/: start.sh <port> runs the server in the foreground,
#                                        api.md is the explorer-facing documentation, B-charters.md is
#                                        arm B's charters, target.conf may set RECORDS (what the data is called)
#
# Defines: TARGET_DIR TARGET_API_MD TARGET_B_CHARTERS TARGET_RECORDS
#          target_setup, target_exec <port> (replaces the current process), target_version
AET_TARGET="${AET_TARGET:-restful-booker}"
case "$AET_TARGET" in
  restful-booker)
    TARGET_DIR="$ROOT/target/restful-booker"
    TARGET_API_MD="$ROOT/target/api.md"
    TARGET_B_CHARTERS="$ROOT/arms/B-human-charters.md"
    TARGET_RECORDS="bookings"
    target_setup() { "$ROOT/scripts/setup-target.sh"; }
    # TZ is pinned to UTC: Restful-booker formats dates in local time, so west of UTC every date
    # shifts back a day (see scoring/answer-key.md, "Environment-dependent").
    target_exec() { cd "$TARGET_DIR" && PORT="$1" SEED=true TZ=UTC exec node ./bin/www; }
    target_version() { git -C "$TARGET_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown; }
    ;;
  *)
    TARGET_DIR="$ROOT/targets/$AET_TARGET"
    if [ ! -x "$TARGET_DIR/start.sh" ]; then
      echo "Unknown target '$AET_TARGET': $TARGET_DIR/start.sh is missing or not executable" >&2
      exit 1
    fi
    TARGET_API_MD="$TARGET_DIR/api.md"
    TARGET_B_CHARTERS="$TARGET_DIR/B-charters.md"
    TARGET_RECORDS="records"
    # shellcheck disable=SC1091
    [ -f "$TARGET_DIR/target.conf" ] && . "$TARGET_DIR/target.conf" && TARGET_RECORDS="${RECORDS:-$TARGET_RECORDS}"
    target_setup() { command -v node >/dev/null 2>&1 || { echo "node is required for $AET_TARGET" >&2; return 1; }; }
    target_exec() { TZ=UTC exec "$TARGET_DIR/start.sh" "$1"; }
    # The committed tree of targets/<name>: changes whenever the target's files change.
    target_version() { git -C "$ROOT" rev-parse --short "HEAD:targets/$AET_TARGET" 2>/dev/null || echo uncommitted; }
    ;;
esac
export AET_TARGET
