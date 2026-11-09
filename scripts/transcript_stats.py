"""Measure a claude stream-json transcript instead of trusting the agent's own count.

Prints key=value lines for meta.txt: curl commands run, tool calls, denied tool calls, turns, cost.
Usage: python3 -I scripts/transcript_stats.py results/<label>/<run>/transcript.jsonl
"""
import json
import re
import sys

curl_calls = tool_calls = denied = 0
curl_requests = 0
result = {}

for line in open(sys.argv[1]):
    try:
        event = json.loads(line)
    except ValueError:
        continue
    if event.get("type") == "assistant":
        for block in event.get("message", {}).get("content", []) or []:
            if block.get("type") == "tool_use":
                tool_calls += 1
                cmd = (block.get("input") or {}).get("command", "")
                if block.get("name") == "Bash" and "curl" in cmd:
                    curl_calls += 1
                    # one Bash call can hold several curl invocations
                    curl_requests += len(re.findall(r"(?:^|[;&|(\s])curl\s", cmd)) or 1
    elif event.get("type") == "user":
        for block in event.get("message", {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                text = json.dumps(block.get("content", ""))
                if "permission" in text.lower() or "denied" in text.lower():
                    denied += 1
    elif event.get("type") == "result":
        result = event

print(f"bash_calls_with_curl={curl_calls}")
print(f"curl_invocations_counted={curl_requests}")
print(f"tool_calls={tool_calls}")
print(f"denied_tool_calls={denied}")
for key in ("num_turns", "duration_ms", "total_cost_usd", "is_error", "subtype"):
    if key in result:
        print(f"{key}={result[key]}")
