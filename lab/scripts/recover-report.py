"""Rebuild an agent's report.md from its transcript when the file itself was not saved.

Why this exists: in batch-1 (macOS) the prompt named the report path through the /var -> /private/var
symlink, the permission rule did not match that spelling, and the Write was denied. Some agents retried
with the resolved path; others stopped and said the report was ready. The report text is still in the
transcript, as the input of the agent's own Write call. This script replays the agent's Write and Edit
calls to report.md, in order, whether or not they were permitted, and gives the text the agent meant
to save. Nothing is added or changed by hand.

Usage:
  python3 -I scripts/recover-report.py <run-dir>            recover if report.md is the placeholder
  python3 -I scripts/recover-report.py --check <run-dir>... replay runs that saved normally and
                                                            compare with the saved file (method test)
Prints key=value lines; with recovery, report.md is written and report_source=transcript is printed.
"""
import json
import os
import sys

PLACEHOLDER = "No report.md written"


def replay(transcript):
    """Return (text or None, number of Write/Edit calls to report.md, number that were denied)."""
    ops, errors = [], {}
    for line in open(transcript, encoding="utf-8"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") in ("Write", "Edit"):
                args = block.get("input") or {}
                if os.path.basename(args.get("file_path", "")) == "report.md":
                    ops.append((block["id"], block["name"], args))
            elif block.get("type") == "tool_result":
                errors[block.get("tool_use_id")] = bool(block.get("is_error"))
    text = None
    for _, name, args in ops:
        if name == "Write":
            text = args.get("content", "")
        elif text is not None:
            old, new = args.get("old_string", ""), args.get("new_string", "")
            text = text.replace(old, new) if args.get("replace_all") else text.replace(old, new, 1)
    denied = sum(1 for op_id, _, _ in ops if errors.get(op_id))
    return text, len(ops), denied


def main(argv):
    check = argv[:1] == ["--check"]
    runs = argv[1:] if check else argv
    if not runs:
        sys.exit(__doc__)
    failures = 0
    for run in runs:
        report = os.path.join(run, "report.md")
        saved = open(report, encoding="utf-8").read() if os.path.exists(report) else ""
        text, n_ops, n_denied = replay(os.path.join(run, "transcript.jsonl"))
        if check:
            if saved.strip() == PLACEHOLDER:
                continue
            same = text is not None and text.rstrip("\n") == saved.rstrip("\n")
            failures += not same
            print(f"{os.path.basename(run.rstrip('/'))}: replay {'matches' if same else 'DIFFERS FROM'} saved report")
            continue
        print(f"report_write_calls={n_ops}")
        print(f"report_write_denied={n_denied}")
        if saved.strip() != PLACEHOLDER:
            print("report_source=file")
        elif text:
            with open(report, "w", encoding="utf-8") as fh:
                fh.write(text if text.endswith("\n") else text + "\n")
            print("report_source=transcript")
        else:
            print("report_source=none")
    if check:
        print(f"{failures} mismatches")
        sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
