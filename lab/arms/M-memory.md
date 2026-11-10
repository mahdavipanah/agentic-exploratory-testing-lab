# Rules for this session

You have the documentation of an HTTP API in {{RUN_DIR}}/api.md. Read it.

You cannot reach the API. Do not send any requests or run any commands. Don't read any file other than `{{RUN_DIR}}/api.md`.

# Your task

From the docs and anything you already know, predict the bugs this API has. Be specific: name the endpoint, the input, and the wrong behaviour you expect. List every bug you think is likely.

Write your predictions to `{{RUN_DIR}}/report.md` in this format. When you are done, reply with one line: the number of predictions.

```markdown
# Prediction report

## Findings
### F1: <the predicted problem, as a one-line title>
- Expected wrong behaviour: what you think the API does
- Why: "from the docs", or "from prior knowledge", and say what you recognise
- Confidence: high | medium | low

## Questions
Leave empty.

## Coverage
Which parts of the docs you based predictions on.
```
