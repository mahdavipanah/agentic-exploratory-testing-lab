"""Check a skill folder against the Agent Skills specification (https://agentskills.io/specification).

A dependency-free stand-in for the official `skills-ref validate`; use that too if you can.
Checks: frontmatter fields and limits, name rules and folder match, body under 500 lines,
and that every relative link in SKILL.md points to an existing file one level deep.

Usage (from lab/): python3 -I scripts/validate-skill.py ../skills/exploratory-testing
"""
import os
import re
import sys

ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, text
    fields, current = {}, None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) and current == "metadata":
            k, _, v = line.strip().partition(":")
            fields["metadata"][k.strip()] = v.strip().strip('"')
            continue
        k, _, v = line.partition(":")
        current = k.strip()
        fields[current] = {} if current == "metadata" and not v.strip() else v.strip().strip('"')
    return fields, m.group(2)


def main(folder):
    errors = []
    path = os.path.join(folder, "SKILL.md")
    if not os.path.isfile(path):
        sys.exit(f"FAIL: {path} not found")
    fields, body = parse_frontmatter(open(path, encoding="utf-8").read())
    if fields is None:
        sys.exit("FAIL: SKILL.md must start with YAML frontmatter between --- lines")

    for key in fields:
        if key not in ALLOWED:
            errors.append(f"unknown frontmatter field: {key}")
    name = fields.get("name", "")
    if not name:
        errors.append("name is required")
    elif not (len(name) <= 64 and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)):
        errors.append("name: 1-64 chars, lowercase letters, digits and single hyphens, no leading or trailing hyphen")
    if name and name != os.path.basename(os.path.normpath(folder)):
        errors.append(f"name '{name}' must match the folder name '{os.path.basename(os.path.normpath(folder))}'")
    desc = fields.get("description", "")
    if not 1 <= len(desc) <= 1024:
        errors.append(f"description must be 1-1024 characters (has {len(desc)})")
    if "compatibility" in fields and not 1 <= len(fields["compatibility"]) <= 500:
        errors.append("compatibility must be 1-500 characters")
    if "metadata" in fields and not isinstance(fields["metadata"], dict):
        errors.append("metadata must be a map of string keys to string values")

    lines = body.count("\n") + 1
    if lines >= 500:
        errors.append(f"SKILL.md body should stay under 500 lines (has {lines})")
    for link in re.findall(r"\]\((?!https?://|#)([^)]+)\)", body):
        target = os.path.join(folder, link)
        if not os.path.isfile(target):
            errors.append(f"broken link: {link}")
        elif link.count("/") > 1:
            errors.append(f"reference more than one level deep: {link}")

    words = len(body.split())
    if errors:
        print("FAIL")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"OK: {name} (description {len(desc)} chars, body {lines} lines, ~{words} words)")


if __name__ == "__main__":
    main(sys.argv[1])
