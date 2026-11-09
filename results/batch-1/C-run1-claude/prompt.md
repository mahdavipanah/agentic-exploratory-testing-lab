# Rules for this session

You are testing a running HTTP API at http://localhost:3001.
Its documentation is in /var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T//aet-run-89est0/api.md. Read it first.

- **Black box.** Interact with the API only over HTTP, using `curl`. Do not read any file other than `/var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T//aet-run-89est0/api.md`, do not search the filesystem, and do not look for the server's source code.
- **Budget.** Send at most 80 HTTP requests in total. Keep a running count. Re-running a request to reproduce something counts too.
- **Test data.** This is a disposable test copy with fake data. Creating, changing and deleting bookings is fine.
- **Evidence.** Only report a finding after you have seen it in a real response. Reproduce each finding at least once before you report it. Put anything you suspect but could not confirm under "Questions", not "Findings".
- **Report.** Write your report to `/var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T//aet-run-89est0/report.md` using the format below. When you are done, reply with one line: the number of findings and the number of requests you used.

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

Explore this API. You will write your own missions first.

1. **List the risks.** Read the docs and list where this API is most likely to be wrong, and which failures would hurt a client most.
2. **Write 3 to 5 charters** from those risks, using Elisabeth Hendrickson's template: *Explore (target) with (resources) to discover (information).* Name a tour for each (see below) and give each a share of your request budget. Put the risks and the charters in the Charters section of your report **before** you send any request other than `GET /ping`.
3. **Explore each charter in order.** Follow what you learn: when something looks odd, dig into it before moving on. If you discover a new risk area, add a charter for it and note why.

## Tours you can use

Tours are themed routes through a product, adapted from James Whittaker's *Exploratory Software Testing* (2009).

- **Guidebook tour:** follow the docs literally. Every documented example, status code and field should behave exactly as written.
- **FedEx tour:** follow one piece of data through every endpoint and format, and check it arrives unchanged.
- **Antisocial tour:** send what a real client least likely would: missing, extra, empty, wrong-type, huge, negative or malformed input.
- **Obsessive-compulsive tour:** repeat, reorder and double-submit actions.
- **Saboteur tour:** take away what the system relies on: credentials, valid ids, headers, content types.
- **Back alley tour:** try the least-documented features and the odd combinations of documented ones.
