"""Turn Restful-booker's generated apidoc (api_data.json) into one plain Markdown file.

This file is the only documentation explorer agents receive, so they work black-box:
running API + public docs, no source code.

Usage: python3 -I scripts/build_api_doc.py <path to api_data.json> > target/api.md
"""
import html
import json
import re
import sys

ORDER = ["HealthCheck", "CreateToken", "GetBookingIds", "GetBooking",
         "CreateBooking", "UpdateBooking", "PartialUpdateBooking", "DeleteBooking"]


def strip_html(text):
    text = re.sub(r"<br\s*/?>", "\n", text or "")
    text = re.sub(r"</p>\s*<p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def fields_table(group_name, fields):
    lines = [f"**{group_name}**", "", "| Field | Type | Optional | Description |", "| --- | --- | --- | --- |"]
    for f in fields:
        lines.append("| {} | {} | {} | {} |".format(
            f.get("field", ""), f.get("type", ""), "yes" if f.get("optional") else "no",
            strip_html(f.get("description", "")).replace("\n", " ")))
    return "\n".join(lines) + "\n"


def local(text):
    # The published docs point at the public Heroku instance; explorers use the local copy.
    return re.sub(r"https?://restful-booker\.herokuapp\.com", "http://localhost:3001", text)


def examples(title, items):
    out = []
    for ex in items or []:
        out.append(f"**{title}: {ex.get('title', '')}**\n\n```\n{local(ex.get('content', '').strip())}\n```\n")
    return "\n".join(out)


def main(path):
    data = json.load(open(path))
    data.sort(key=lambda e: ORDER.index(e["name"]) if e["name"] in ORDER else 99)
    print("# Restful-booker API documentation\n")
    print("Base URL: http://localhost:3001\n")
    print("This is the public documentation of the API under test, converted from its apidoc page.\n")
    for e in data:
        print(f"## {e.get('title')}: {e['type'].upper()} /{e['url'].lstrip('/')}\n")
        if e.get("description"):
            print(strip_html(e["description"]) + "\n")
        print(examples("Request example", e.get("examples")))
        for section, label in (("header", "Headers"), ("parameter", "Request"), ("success", "Response")):
            block = e.get(section) or {}
            for group, fields in (block.get("fields") or {}).items():
                print(fields_table(f"{label}: {group}", fields))
            print(examples(f"{label} example", block.get("examples")))
        if e.get("error"):
            for group, fields in (e["error"].get("fields") or {}).items():
                print(fields_table(f"Error: {group}", fields))
            print(examples("Error example", e["error"].get("examples")))


if __name__ == "__main__":
    main(sys.argv[1])
