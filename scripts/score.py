"""Compute per-run recall from scoring/scores-<batch>.csv.

Usage: python3 -I scripts/score.py scoring/scores-pilot-2026-11-09.csv 38
Rows with section=finding count toward strict recall; section=question rows only toward "noticed".
"""
import csv
import sys
from collections import defaultdict

path, ceiling = sys.argv[1], int(sys.argv[2])
strict, noticed, tp, fp, dup = defaultdict(set), defaultdict(set), defaultdict(int), defaultdict(int), defaultdict(int)
for row in csv.DictReader(open(path)):
    run, keys = row["run"], [k for k in row["key_ids"].split(";") if k]
    if row["section"] == "finding":
        {"TP": tp, "FP": fp, "DUP": dup}[row["verdict"]][run] += 1
        strict[run].update(keys)
    noticed[run].update(keys)

runs = sorted(noticed)
print("| Run | Findings | FP | Key items in findings | Recall (findings) | Key items noticed (findings + questions) | Recall (noticed) |")
print("| --- | --- | --- | --- | --- | --- | --- |")
for r in runs:
    n = tp[r] + fp[r] + dup[r]
    print(f"| {r} | {n} | {fp[r]} | {len(strict[r])} | {len(strict[r])/ceiling:.0%} | {len(noticed[r] | strict[r])} | {len((noticed[r] | strict[r]))/ceiling:.0%} |")
us = set().union(*strict.values()); un = set().union(*noticed.values())
print(f"| union of all runs | | | {len(us)} | {len(us)/ceiling:.0%} | {len(un)} | {len(un)/ceiling:.0%} |")
allk = {f"K{i:02d}" for i in range(1, ceiling + 1)}
print("\nNever noticed by any run:", ", ".join(sorted(allk - un)))
print("Only in questions, never in findings:", ", ".join(sorted(un - us)))
for r in runs:
    print(f"{r} strict: {', '.join(sorted(strict[r]))}")
