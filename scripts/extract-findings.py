"""Turn the reports of a batch into a score-sheet CSV to fill in.

One row per finding (### F<n>: ...) and per top-level question bullet. Fill in key_ids
(answer-key ids, ;-separated) and, for findings, verdict (TP, DUP or FP). Then run score.py.

Usage: python3 -I scripts/extract-findings.py results/<label> [--all] > scoring/scores-<label>.csv
The run id is the run folder name, e.g. "B-run2-claude"; its first letter is the arm.

Only runs with isolation=bare in their meta.txt are included, because those are the runs statistics
should rest on. Pass --all to include the rest (pilot, safe-mode and dry runs); skipped runs are listed on stderr.
"""
import csv
import os
import re
import sys


def sections(text):
    """Split a report into {heading: body} on '## ' headings."""
    out, name = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            name = m.group(1).strip().lower()
            out[name] = []
        elif name:
            out[name].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def findings(body):
    for m in re.finditer(r"^###\s+(F\d+)\s*[:.\-–]\s*(.+)$", body, re.M):
        yield m.group(1), m.group(2).strip()


def questions(body):
    n = 0
    for line in body.splitlines():
        m = re.match(r"^[-*]\s+(.+)$", line)  # top-level bullets only
        if m:
            n += 1
            title = re.sub(r"\*\*(.+?)\*\*", r"\1", m.group(1)).strip()
            yield f"Q{n}", title[:120]


def isolation(run_dir):
    meta = os.path.join(run_dir, "meta.txt")
    if os.path.isfile(meta):
        for line in open(meta):
            if line.startswith("isolation="):
                return line.split("=", 1)[1].strip()
    return "unknown"


def main(batch_dir, include_all):
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["run", "section", "item", "title", "key_ids", "verdict", "note"])
    for run in sorted(os.listdir(batch_dir)):
        report = os.path.join(batch_dir, run, "report.md")
        if not os.path.isfile(report):
            continue
        iso = isolation(os.path.join(batch_dir, run))
        if iso != "bare" and not include_all:
            print(f"skipped {run}: isolation={iso} (use --all to include)", file=sys.stderr)
            continue
        s = sections(open(report).read())
        for item, title in findings(s.get("findings", "")):
            w.writerow([run, "finding", item, title, "", "", ""])
        for item, title in questions(s.get("questions", "")):
            w.writerow([run, "question", item, title, "", "", ""])


if __name__ == "__main__":
    main(sys.argv[1], "--all" in sys.argv[2:])
