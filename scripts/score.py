"""Compute recall per run and per arm from a filled-in score sheet, with simple statistics.

Usage: python3 -I scripts/score.py scoring/scores-<batch>.csv 38 [--schedule results/<batch>/schedule.txt]

Rows with section=finding count toward "findings" recall; section=question rows count only toward
"noticed". A run's arm is the first letter of its run id (A, B, C, D, M).

With several runs per arm it also prints:
  - per-arm mean, standard deviation and range;
  - pairwise permutation tests on findings recall (exact when small, otherwise 20,000 shuffles);
  - with --schedule, a carry-over check: do sessions that ran later score better than their arm's average?
"""
import csv
import itertools
import random
import re
import sys
from collections import defaultdict
from statistics import mean, stdev

args = sys.argv[1:]
schedule_path = None
if "--schedule" in args:
    i = args.index("--schedule")
    schedule_path = args[i + 1]
    del args[i:i + 2]
path, ceiling = args[0], int(args[1])

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
recall = {r: len(strict[r]) / ceiling for r in runs}
recall_noticed = {r: len(noticed[r] | strict[r]) / ceiling for r in runs}

print("| Run | Findings | FP | Key items in findings | Recall (findings) | Key items noticed (findings + questions) | Recall (noticed) |")
print("| --- | --- | --- | --- | --- | --- | --- |")
for r in runs:
    c = counts[r]
    print(f"| {r} | {sum(c.values())} | {c['FP']} | {len(strict[r])} | {recall[r]:.0%} | {len(noticed[r] | strict[r])} | {recall_noticed[r]:.0%} |")
us = set().union(*strict.values()) if strict else set()
un = (set().union(*noticed.values()) if noticed else set()) | us
print(f"| union of all runs | | | {len(us)} | {len(us) / ceiling:.0%} | {len(un)} | {len(un) / ceiling:.0%} |")

by_arm = defaultdict(list)
for r in runs:
    by_arm[r[0]].append(r)
arms = sorted(by_arm)
multi = any(len(v) > 1 for v in by_arm.values())

if multi:
    print("\n## Per arm\n")
    print("| Arm | Runs | Mean recall (findings) | SD | Range | Mean recall (noticed) |")
    print("| --- | --- | --- | --- | --- | --- |")
    for a in arms:
        f = [recall[r] for r in by_arm[a]]
        n = [recall_noticed[r] for r in by_arm[a]]
        sd = stdev(f) if len(f) > 1 else 0.0
        print(f"| {a} | {len(f)} | {mean(f):.0%} | {sd:.0%} | {min(f):.0%} to {max(f):.0%} | {mean(n):.0%} |")

    def perm_test(x, y, rng):
        """Two-sided permutation test on the difference in means."""
        observed = abs(mean(x) - mean(y))
        pooled, nx = x + y, len(x)
        combos = list(itertools.combinations(range(len(pooled)), nx)) if len(pooled) <= 20 else None
        if combos is not None and len(combos) <= 200000:
            hits = 0
            for idx in combos:
                s = set(idx)
                gx = [pooled[i] for i in idx]
                gy = [pooled[i] for i in range(len(pooled)) if i not in s]
                hits += abs(mean(gx) - mean(gy)) >= observed - 1e-12
            return hits / len(combos), "exact"
        hits = 0
        for _ in range(20000):
            rng.shuffle(pooled)
            hits += abs(mean(pooled[:nx]) - mean(pooled[nx:])) >= observed - 1e-12
        return (hits + 1) / 20001, "20k shuffles"

    rng = random.Random(1)
    print("\n## Arm comparisons (findings recall, permutation test)\n")
    print("| Comparison | Mean difference | p | Method | Note |")
    print("| --- | --- | --- | --- | --- |")
    for a, b in itertools.combinations(arms, 2):
        x, y = [recall[r] for r in by_arm[a]], [recall[r] for r in by_arm[b]]
        if len(x) < 2 or len(y) < 2:
            continue
        p, method = perm_test(x, y, rng)
        floor = 2 / len(list(itertools.combinations(range(len(x) + len(y)), len(x)))) if len(x) + len(y) <= 20 else 0
        note = "too few runs to reach p<0.05" if floor >= 0.05 else ""
        print(f"| {b} vs {a} | {mean(y) - mean(x):+.0%} | {p:.3f} | {method} | {note} |")

    if schedule_path:
        order = {}
        for line in open(schedule_path):
            if line.startswith("#") or not line.strip():
                continue
            o, arm, run = line.split()[:3]
            order[(arm, run)] = int(o)
        points = []
        for r in runs:
            m = re.match(r"^([A-Z])-run(\d+)", r)
            if m and (m.group(1), m.group(2)) in order and len(by_arm[r[0]]) > 1:
                arm_mean = mean(recall[x] for x in by_arm[r[0]])
                points.append((order[(m.group(1), m.group(2))], recall[r] - arm_mean, r))
        print("\n## Carry-over check\n")
        if len(points) < 4:
            print("Not enough scheduled runs to check.")
        else:
            def ranks(v):
                srt = sorted(range(len(v)), key=lambda i: v[i])
                rk = [0.0] * len(v)
                i = 0
                while i < len(srt):
                    j = i
                    while j + 1 < len(srt) and v[srt[j + 1]] == v[srt[i]]:
                        j += 1
                    for k in range(i, j + 1):
                        rk[srt[k]] = (i + j) / 2 + 1
                    i = j + 1
                return rk

            def spearman(a, b):
                ra, rb = ranks(a), ranks(b)
                ma, mb = mean(ra), mean(rb)
                num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
                den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
                return num / den if den else 0.0

            xs, ys = [p[0] for p in points], [p[1] for p in points]
            rho = spearman(xs, ys)
            shuffled, hits = ys[:], 0
            for _ in range(20000):
                rng.shuffle(shuffled)
                hits += abs(spearman(xs, shuffled)) >= abs(rho) - 1e-12
            p = (hits + 1) / 20001
            print("Each session's recall minus its arm's mean, against the order sessions ran in.\n")
            print("| Order | Run | Recall minus arm mean |\n| --- | --- | --- |")
            for o, d, r in sorted(points):
                print(f"| {o} | {r} | {d:+.0%} |")
            verdict = ("later sessions scored higher: possible carry-over, investigate" if rho > 0 and p < 0.05
                       else "no sign that later sessions did better")
            print(f"\nSpearman rho = {rho:+.2f}, permutation p = {p:.3f}: {verdict}.")

allk = {f"K{i:02d}" for i in range(1, ceiling + 1)}
print("\nNever noticed by any run:", ", ".join(sorted(allk - un)) or "none")
print("Only in questions, never in findings:", ", ".join(sorted(un - us)) or "none")
if unscored:
    print(f"\nWarning: {unscored} finding(s) have no verdict yet (TP, DUP or FP).")
