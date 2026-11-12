# Report template

```markdown
# Exploration report

## Environment
Target, version or commit, configuration, timezone, how you checked the state.

## Risks
Ranked list of the risks you explored for, one line each.

## Charters
One line each: Explore ... with ... to discover .... Tour: .... Budget: ....

## Findings
### F1: <one-line title>
- Kind: bug | needs a decision
- Severity: high | medium | low
- Steps: the exact commands or actions
- Expected: what should happen, and which oracle says so
- Actual: what happened (status, output, the relevant part of the response)
- Reproduced: how many times

## Questions
Unconfirmed suspicions only, each with what you saw and what would confirm it.

## Coverage
Per charter: covered, partly covered or not reached, and what you saw working. Anything you explored outside the charters. What remains unknown, and the risks you didn't reach. Budget used.
```

Write titles that describe the problem, not the test ("Renaming a playlist drops its last song", not "Tested rename"). If one probe shows two separate problems, report them as two findings.
