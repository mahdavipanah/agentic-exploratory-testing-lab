"""Fill a score sheet's key_ids, verdict and note columns from a mapping file.

Usage: python3 -I scripts/apply-map.py <sheet.csv from extract-findings.py> <map.txt> > scoring/scores-<batch>.csv

Map lines: "<run> <item> <keys|-|FP> [| note]", where <run> is the run id without the agent suffix
(A-run1 for A-run1-claude). Verdicts for findings are computed in report order: TP if the finding claims
a key item no earlier finding in the same report claimed, DUP if all its items were already claimed,
FP if mapped to FP. Questions get key ids only. Fails if a row has no mapping or a mapping has no row.
"""
import csv
import re
import sys

sheet, map_path = sys.argv[1], sys.argv[2]
mapping = {}
for n, line in enumerate(open(map_path, encoding="utf-8"), 1):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    head, _, note = line.partition("|")
    parts = head.split()
    if len(parts) != 3:
        sys.exit(f"{map_path}:{n}: expected '<run> <item> <keys>', got {line!r}")
    run, item, keys = parts
    if (run, item) in mapping:
        sys.exit(f"{map_path}:{n}: {run} {item} mapped twice")
    if keys not in ("-", "FP") and not re.fullmatch(r"[A-Z]\d\d(;[A-Z]\d\d)*", keys):
        sys.exit(f"{map_path}:{n}: bad key list {keys!r}")
    mapping[(run, item)] = (keys, note.strip())

rows = list(csv.DictReader(open(sheet, encoding="utf-8")))
writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()), lineterminator="\n")
writer.writeheader()
claimed, used, missing = {}, set(), []
for row in rows:
    run = re.sub(r"-[a-z]+$", "", row["run"])
    key = (run, row["item"])
    if key not in mapping:
        missing.append(f"{run} {row['item']}")
        continue
    used.add(key)
    keys, note = mapping[key]
    ids = [] if keys in ("-", "FP") else keys.split(";")
    row["key_ids"] = ";".join(ids)
    row["note"] = note
    if row["section"] == "finding":
        seen = claimed.setdefault(run, set())
        if keys == "FP":
            row["verdict"] = "FP"
        elif not ids:
            row["verdict"] = ""
        else:
            row["verdict"] = "TP" if set(ids) - seen else "DUP"
            seen.update(ids)
    writer.writerow(row)

extra = sorted(set(mapping) - used)
if missing or extra:
    sys.exit(f"unmapped rows: {missing}\nmappings with no row: {extra}")
