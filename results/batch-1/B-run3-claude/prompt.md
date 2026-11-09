# Rules for this session

You are testing a running HTTP API at http://localhost:3001.
Its documentation is in /var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T//aet-run-uL7NRE/api.md. Read it first.

- **Black box.** Interact with the API only over HTTP, using `curl`. Do not read any file other than `/var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T//aet-run-uL7NRE/api.md`, do not search the filesystem, and do not look for the server's source code.
- **Budget.** Send at most 80 HTTP requests in total. Keep a running count. Re-running a request to reproduce something counts too.
- **Test data.** This is a disposable test copy with fake data. Creating, changing and deleting bookings is fine.
- **Evidence.** Only report a finding after you have seen it in a real response. Reproduce each finding at least once before you report it. Put anything you suspect but could not confirm under "Questions", not "Findings".
- **Report.** Write your report to `/var/folders/fx/h2qwvdgd61vbn287pwlqhwg40000gn/T//aet-run-uL7NRE/report.md` using the format below. When you are done, reply with one line: the number of findings and the number of requests you used.

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

Explore this API using the four charters below. Each charter follows Elisabeth Hendrickson's template: *Explore (target) with (resources) to discover (information).*

Spend about 20 requests on each charter, in order. Within a charter, follow what you learn: when something looks odd, dig into it before moving on. Copy the charters into the Charters section of your report.

1. **Explore** the booking lifecycle (create, read, full update, partial update, delete, then read again) **with** JSON payloads and the admin token **to discover** whether every step does what the docs say and returns the documented status code. *Tour: Guidebook.*
2. **Explore** one booking's data across every endpoint and format (JSON, XML, URL-encoded; different Accept and Content-Type pairs) **with** a single distinctive booking **to discover** data that changes, disappears or is formatted differently along the way. *Tour: FedEx.*
3. **Explore** create, full update and partial update **with** bad and boundary data (missing or extra fields, wrong types, negative or huge prices, checkout before checkin, invalid dates, very long and non-ASCII names) **to discover** what the API wrongly accepts and what it rejects badly. *Tour: Antisocial.*
4. **Explore** authorization and search **with** no credentials, wrong tokens, Basic auth versus cookie, unknown ids, and the GET /booking filters **to discover** who can change what, and whether search follows the docs. *Tours: Saboteur and Back alley.*

> Written by the experimenter from the API docs only, before reading the server's source code.

## Tours you can use

Tours are themed routes through a product, adapted from James Whittaker's *Exploratory Software Testing* (2009).

- **Guidebook tour:** follow the docs literally. Every documented example, status code and field should behave exactly as written.
- **FedEx tour:** follow one piece of data through every endpoint and format, and check it arrives unchanged.
- **Antisocial tour:** send what a real client least likely would: missing, extra, empty, wrong-type, huge, negative or malformed input.
- **Obsessive-compulsive tour:** repeat, reorder and double-submit actions.
- **Saboteur tour:** take away what the system relies on: credentials, valid ids, headers, content types.
- **Back alley tour:** try the least-documented features and the odd combinations of documented ones.
