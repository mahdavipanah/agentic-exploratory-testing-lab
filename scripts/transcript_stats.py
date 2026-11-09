"""Measure a claude stream-json transcript instead of trusting the agent's own count.

Prints key=value lines for meta.txt: model, curl commands, tool calls, denied tool calls, turns, cost.
curl_invocations_counted counts every curl the agent asked for; curl_invocations_executed leaves out
commands the permission system refused (they never reached the API). Both count a loop as one.
Usage: python3 -I scripts/transcript_stats.py results/<label>/<run>/transcript.jsonl
"""
import json
import re
import sys

curl_calls = tool_calls = denied = 0
curl_requests = 0
curl_by_id = {}
refused_ids = set()
model = "unknown"
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
                    n = len(re.findall(r"(?:^|[;&|(\s])curl\s", cmd)) or 1
                    curl_requests += n
                    curl_by_id[block.get("id")] = n
    elif event.get("type") == "user":
        for block in event.get("message", {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                text = json.dumps(block.get("content", ""))
                if "permission" in text.lower() or "denied" in text.lower():
                    denied += 1
                # A command that ran and failed starts with its exit code; anything else was refused.
                if not text.lstrip('"').startswith("Exit code"):
                    refused_ids.add(block.get("tool_use_id"))
    elif event.get("type") == "system" and event.get("subtype") == "init":
        model = event.get("model") or model
    elif event.get("type") == "result":
        result = event

print(f"model_used={model}")
print(f"bash_calls_with_curl={curl_calls}")
print(f"curl_invocations_counted={curl_requests}")
print(f"curl_invocations_executed={sum(n for i, n in curl_by_id.items() if i not in refused_ids)}")
print(f"tool_calls={tool_calls}")
print(f"denied_tool_calls={denied}")
print(f"refused_tool_calls={len(refused_ids)}")
for key in ("num_turns", "duration_ms", "total_cost_usd", "is_error", "subtype"):
    if key in result:
        print(f"{key}={result[key]}")
