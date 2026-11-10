# Rules for this session

You are testing a running HTTP API at http://localhost:3003.
Its documentation is in /private/var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T/aet-run-qoDOns/api.md. Read it first.

- **Black box.** Interact with the API only over HTTP, using `curl`. Do not read any file other than `/private/var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T/aet-run-qoDOns/api.md`, do not search the filesystem, and do not look for the server's source code.
- **Budget.** Send at most 80 HTTP requests in total. Keep a running count. Re-running a request to reproduce something counts too.
- **Test data.** This is a disposable test copy with fake data. Creating, changing and deleting claims is fine.
- **Evidence.** Only report a finding after you have seen it in a real response. Reproduce each finding at least once before you report it. Put anything you suspect but could not confirm under "Questions", not "Findings".
- **Report.** Write your report to `/private/var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T/aet-run-qoDOns/report.md` using the format below. When you are done, reply with one line: the number of findings and the number of requests you used.

## Report format

```markdown
# Exploration report

## Charters
The missions you followed, one per line. Write "none" if you had none.

## Findings
### F1: <one-line title>
- Severity: high | medium | low
- Request: the exact curl command
- Expected: what should happen, and why (a line in the docs, or your reasoning)
- Actual: status code and the relevant part of the response
- Reproduced: how many times you saw it

## Questions
Behaviour that looks odd but you could not confirm, or where the docs are unclear.

## Coverage
What you explored, what you did not get to, and how many requests you used.
```

---

# Your task

Find bugs in this API.
