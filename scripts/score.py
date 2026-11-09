"""Compute recall per run and per arm from a filled-in score sheet.

Usage: python3 -I scripts/score.py scoring/scores-<batch>.csv 38

Rows with section=finding count toward "findings" recall; section=question rows count only toward
"noticed". A run's arm is the first letter of its run id (A, B, C).
"""
import csv
import sys
from collections import defaultdict
from statistics import mean

path, ceiling = sys.argv[1], int(sys.argv[2])
strict, noticed = defaultdict(set), defaultdict(set)
counts = defaultdict(lambda: {"TP": 0, "FP": 0, "DUP": 0, "": 0})
unscored = 0
for row in csv.DictReader(open(path)):
    run, keys = row["run"], [k.strip() for k in row["key_ids"].split(";") if k.strip()]
    if row["section"] == "finding":
        verdict = row["verdict"].strip()
        counts[run][verdict if verdict in ("TP", "FP", "DUP") else ""] += 1
        unscored += verdict not in ("TP", "FP", "DUP")
        if verdict != "FP":
            strict[run].update(keys)
    noticed[run].update(keys)

runs = sorted(set(noticed) | set(counts))
print("| Run | Findings | FP | Key items in findings | Recall (findings) | Key items noticed (findings + questions) | Recall (noticed) |")
print("| --- | --- | --- | --- | --- | --- | --- |")
for r in runs:
    c = counts[r]
    n_found, n_noticed = len(strict[r]), len(noticed[r] | strict[r])
    print(f"| {r} | {sum(c.values())} | {c['FP']} | {n_found} | {n_found / ceiling:.0%} | {n_noticed} | {n_noticed / ceiling:.0%} |")
us = set().union(*strict.values()) if strict else set()
un = (set().union(*noticed.values()) if noticed else set()) | us
print(f"| union of all runs | | | {len(us)} | {len(us) / ceiling:.0%} | {len(un)} | {len(un) / ceiling:.0%} |")

arms = sorted({r[0] for r in runs})
if any(sum(1 for r in runs if r[0] == a) > 1 for a in arms):
    print("\n| Arm | Runs | Mean recall (findings) | Range | Mean recall (noticed) |")
    print("| --- | --- | --- | --- | --- |")
    for a in arms:
        rs = [r for r in runs if r[0] == a]
        f = [len(strict[r]) / ceiling for r in rs]
        n = [len(noticed[r] | strict[r]) / ceiling for r in rs]
        print(f"| {a} | {len(rs)} | {mean(f):.0%} | {min(f):.0%} to {max(f):.0%} | {mean(n):.0%} |")

allk = {f"K{i:02d}" for i in range(1, ceiling + 1)}
print("\nNever noticed by any run:", ", ".join(sorted(allk - un)) or "none")
print("Only in questions, never in findings:", ", ".join(sorted(un - us)) or "none")
if unscored:
    print(f"\nWarning: {unscored} finding(s) have no verdict yet (TP, DUP or FP).")
