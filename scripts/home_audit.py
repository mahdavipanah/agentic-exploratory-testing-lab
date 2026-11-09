"""Audit memory files in a Claude Code home before and after a run (login isolation).

Usage:
  python3 -I scripts/home_audit.py snapshot <claude-home> <snapshot.json>
  python3 -I scripts/home_audit.py diff <before.json> <after.json>     # prints new or changed paths

Only paths whose name contains "memory" are recorded, by relative path and modification time.
File contents are never read.
"""
import json
import os
import sys


def snapshot(home, out):
    found = {}
    if os.path.isdir(home):
        for root, dirs, files in os.walk(home):
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, home)
                if "memory" in rel.lower():
                    try:
                        found[rel] = os.stat(full).st_mtime
                    except OSError:
                        pass
    json.dump(found, open(out, "w"))


def diff(before, after):
    a, b = json.load(open(before)), json.load(open(after))
    for rel, mtime in sorted(b.items()):
        if rel not in a or a[rel] != mtime:
            print(rel)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "snapshot":
        snapshot(sys.argv[2], sys.argv[3])
    elif cmd == "diff":
        diff(sys.argv[2], sys.argv[3])
    else:
        sys.exit("usage: home_audit.py snapshot <home> <out> | diff <before> <after>")
