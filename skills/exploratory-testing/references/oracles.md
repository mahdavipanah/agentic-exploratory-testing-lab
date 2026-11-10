# Oracles: how to tell something is wrong

An oracle is a way of recognising a problem. Never rely on one alone: docs can be wrong, and behaviour that matches wrong docs is still a finding. Adapted from James Bach and Michael Bolton's HICCUPPS oracle heuristics.

| Oracle | Ask | Examples |
| --- | --- | --- |
| Never and Always | Does it break a rule that must hold whatever anyone does? | Money created or lost; a total that doesn't match its parts; one user reading another's data; an action applied twice |
| Claims | Does it do what the docs, examples, specs, messages and UI text say? | A tutorial step that fails as written; a limit the docs state but the system doesn't enforce |
| Standards and conventions | Does it follow the protocol, format and platform rules a client would rely on? | An error reported with a success status; a retry that charges twice; a CLI that exits 0 after failing |
| Consistency within the product | Is the same thing treated the same way everywhere? | The web form rejects what the API accepts; one list sorts newest first, a similar one oldest first |
| User expectations | Would a reasonable user or client get what they meant? | An emoji saved as question marks; a total that differs from the sum of its lines |
| Purpose | Does it serve what the feature is for? | An export that can't be imported back |
| History | Does it match earlier behaviour or earlier versions? | A field that used to be required no longer is |
| Comparable products | How do similar systems behave? | Every comparable tool accepts this file and this one rejects it |
| Image | Would this embarrass the team? | A typo in a customer-facing message; secrets in a log line |
| Familiar problems | Does it show a known bug pattern? | Off-by-one, rounding and precision loss, timezone and daylight-saving shifts, encoding and escaping, null versus empty, races and double submits, stale caches, injection, mass assignment (a client setting server-owned fields) |

## When you can't know the exact answer

- **Invert it.** Do the reverse operation and compare: read back what you wrote, export and re-import, convert there and back.
- **Check a range or a property.** A result can be unknowable yet obviously wrong: a negative count, a total above its maximum, a sort that isn't sorted.
- **Push to extremes.** Set inputs to their minimum and maximum so effects are big enough to see.
