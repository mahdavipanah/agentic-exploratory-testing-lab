"""Make an arm-blind scoring document from a batch, for a scorer who must not know which arm wrote what.

Usage: python3 -I scripts/blind-sheet.py results/<label> <seed> <out.md> <codes.txt>

out.md     every run's Findings (verbatim) and Questions (numbered Q1, Q2, ... as extract-findings.py
           counts them), under a random code R01..Rnn; charters, risks and coverage are left out,
           because they name the arm's instructions
codes.txt  the code -> run table, kept away from the scorer until scoring is done
Prediction reports (arm M) are recognisable by their fields; the scorer is told how to score them.
"""
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
batch, seed, out_path, codes_path = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]

import importlib.util
spec = importlib.util.spec_from_file_location("ef", os.path.join(os.path.dirname(__file__), "extract-findings.py"))
ef = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ef)

runs = sorted(r for r in os.listdir(batch) if os.path.isfile(os.path.join(batch, r, "report.md")))
order = runs[:]
random.Random(seed).shuffle(order)
codes = {run: f"R{i + 1:02d}" for i, run in enumerate(order)}

with open(out_path, "w", encoding="utf-8") as out:
    out.write("# Blind scoring sheet\n\nOne section per run, in random order. Items are F<n> (findings) and Q<n> (questions).\n")
    for run in order:
        s = ef.sections(open(os.path.join(batch, run, "report.md"), encoding="utf-8").read())
        out.write(f"\n\n# {codes[run]}\n\n## Findings\n\n{s.get('findings', '').strip()}\n\n## Questions\n\n")
        n = 0
        for line in s.get("questions", "").splitlines():
            m = re.match(r"^[-*]\s+(.+)$", line)
            if m:
                n += 1
                out.write(f"- Q{n}. {m.group(1).strip()}\n")
        if n == 0:
            out.write("(none)\n")

with open(codes_path, "w", encoding="utf-8") as f:
    for run in runs:
        f.write(f"{codes[run]} {re.sub(r'-[a-z]+$', '', run)}\n")
print(f"{len(runs)} runs -> {out_path}; codes in {codes_path}")
