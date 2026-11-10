# Prediction report

## Findings

### F1: Totals suffer floating-point drift (e.g. 0.1 + 0.2 = 0.30000000000000004)
- Expected wrong behaviour: `total` in GET /claims/{id}, GET /claims summaries, and `amount_paid` from POST /claims/{id}/pay shows values like `251.39999999999998` or `0.30000000000000004` because the code sums JS floats without rounding to cents.
- Why: from prior knowledge. Naive `reduce((a,b)=>a+b)` over decimal amounts is a classic bug. The docs stress "at most two decimal places".
- Confidence: high

### F2: Two-decimal check on amount is wrong for some values
- Expected wrong behaviour: POST /claims/{id}/items rejects valid amounts like `1.15`, `0.29`, `4.35` or `9.95` (because `amount*100 % 1 !== 0` hits float error), or accepts `12.345` / `1.005` when the check uses rounding.
- Why: from prior knowledge. Float-based decimal-place validation often goes wrong.
- Confidence: medium

### F3: Amount boundary off-by-one: 10000 rejected or 0 / negative accepted
- Expected wrong behaviour: `amount: 10000` returns 400 (the check uses `<` instead of `<=`), or `amount: 0` is accepted (the check uses `>= 0`).
- Why: from the docs. "Greater than 0 and at most 10000.00" is an obvious place for a boundary bug.
- Confidence: medium

### F4: Amount type coercion: string "12.50", booleans or NaN-like values accepted
- Expected wrong behaviour: POST /claims/{id}/items with `amount: "12.50"` gets 201 (because of `Number()` coercion), even though the docs say strings are rejected.
- Why: from the docs, which call this case out explicitly.
- Confidence: medium

### F5: 90-day date window off by one
- Expected wrong behaviour: the item date 2026-08-12 (exactly 90 days before today) is rejected, or 2026-08-11 is accepted. A date of today might also be rejected because of timezone handling (local time vs UTC), or tomorrow accepted.
- Why: from the docs. They give exact boundary examples, which suggests boundary testing. Date math in ms/UTC is error-prone.
- Confidence: high

### F6: Invalid calendar dates accepted (2026-02-30, 2026-09-31)
- Expected wrong behaviour: POST items with `date: "2026-09-31"` is accepted because the JS `Date` rolls it over to 2026-10-01 (only the regex is checked).
- Why: from prior knowledge. The docs say "A real calendar date".
- Confidence: high

### F7: Meals daily limit wrong at the boundary or not applied across sources
- Expected wrong behaviour: meals adding up to exactly 60.00 on one day are rejected (`<` vs `<=`). Or the limit isn't enforced within the POST /claims `items` array (only existing items are checked, not earlier items in the same request). Or the limit counts meals across all claims or all dates instead of per claim per date. Float sum such as 20.1+19.9+20 might falsely exceed 60.
- Why: from the docs, which describe the meals rule in detail.
- Confidence: high

### F8: POST /claims with an invalid item still creates the claim (not atomic)
- Expected wrong behaviour: when items[1] is invalid, the response is 400, but the claim (and/or items[0]) has been created and appears in GET /claims. Item ids get consumed.
- Why: from the docs ("If any item is invalid, nothing is created").
- Confidence: medium

### F9: Validation error `field` missing index for nested items
- Expected wrong behaviour: an error for the second item reports `field: "date"` instead of `items[1].date`, or the index is wrong (1-based).
- Why: from the docs.
- Confidence: medium

### F10: Manager can review claims of another team
- Expected wrong behaviour: frank (mobile manager) can approve or reject a submitted platform claim, or carol can see/review mobile claims. The authorization check is on role only, not team.
- Why: from the docs and prior knowledge (BOLA/IDOR).
- Confidence: medium

### F11: Managers/finance can see drafts
- Expected wrong behaviour: GET /claims for carol or dave includes draft claims, or GET /claims/{draftId} returns 200 instead of 404. `?status=draft` for a manager returns drafts.
- Why: from the docs (the visibility rules).
- Confidence: medium

### F12: Wrong 403 vs 404 for invisible claims
- Expected wrong behaviour: bob calling PATCH/DELETE/submit on alice's claim gets 403 (leaking existence) instead of 404. Or a manager editing a visible claim gets 404 instead of 403.
- Why: from the docs, which have detailed 403/404 rules.
- Confidence: medium

### F13: Status check order: 409 before 403/404, or 403 before 409 mismatches
- Expected wrong behaviour: a non-owner hitting submit on a non-draft visible claim gets 409 instead of 403. Finance trying to pay a submitted claim gets 403 vs 409 inconsistently.
- Why: from prior knowledge.
- Confidence: low

### F14: Employee can review own claim (self-approval)
- Expected wrong behaviour: alice POSTs /claims/{own}/review with approve and gets 200.
- Why: from the docs, which mention this explicitly in the 403 row.
- Confidence: low

### F15: Pay is not idempotent: a repeat pay changes paid_at / reference / amount_paid
- Expected wrong behaviour: a second POST /claims/{id}/pay on a paid claim updates `paid_at`, `payment_reference` or `updated_at`, or records a double payment. Alternatively it returns 409.
- Why: from the docs, which stress idempotency.
- Confidence: high

### F16: amount_paid not equal to total or stale
- Expected wrong behaviour: `amount_paid` is the unrounded float sum or is missing. It may also be computed from stale items.
- Why: from the docs.
- Confidence: low

### F17: Rejection without comment accepted, or whitespace-only comment accepted
- Expected wrong behaviour: `{"decision":"reject"}` or `{"decision":"reject","comment":"   "}` or `comment: ""` gives 200. A comment over 500 chars is accepted.
- Why: from the docs.
- Confidence: medium

### F18: Resubmit/re-review leaves stale review fields, or submit doesn't update submitted_at
- Expected wrong behaviour: after approve without a comment, `review_comment` still holds the old rejection comment (it is not reset to null). Resubmit of a rejected claim keeps the old `submitted_at`.
- Why: from the docs ("Comment from the last review").
- Confidence: medium

### F19: updated_at not bumped on item add/remove or status changes
- Expected wrong behaviour: POST/DELETE items or review/pay leaves `updated_at` unchanged. Or a failed request (400/409) bumps it.
- Why: from the docs, which explicitly define what counts.
- Confidence: medium

### F20: Submit with zero items allowed, or wrong error code
- Expected wrong behaviour: submitting an empty draft returns 200, or returns 409 instead of 400 with `field: items`. Removing all items from a rejected claim and resubmitting works.
- Why: from the docs.
- Confidence: medium

### F21: Editing allowed in wrong states
- Expected wrong behaviour: PATCH or POST items works on submitted/approved/paid claims (only `draft` is checked negatively), changing the total of an approved claim before pay. DELETE of a rejected claim succeeds (should be 409).
- Why: from the docs.
- Confidence: medium

### F22: PATCH accepts protected fields (mass assignment)
- Expected wrong behaviour: PATCH with `{"status":"approved"}`, `owner`, `total`, or `id` changes them.
- Why: from the docs and prior knowledge.
- Confidence: medium

### F23: PATCH title null / empty / whitespace accepted; purpose "" not converted to null
- Expected wrong behaviour: `title: null` or `"   "` is accepted. `purpose: ""` is stored as an empty string. The title is not trimmed before storing, or the length is counted before trimming.
- Why: from the docs.
- Confidence: medium

### F24: Currency case-insensitive or unvalidated
- Expected wrong behaviour: `currency: "eur"` or `"JPY"` accepted on POST or PATCH.
- Why: from the docs ("upper case").
- Confidence: low

### F25: Delete item from another claim (item not belonging to path claim)
- Expected wrong behaviour: DELETE /claims/4/items/1 (item 1 belongs to claim 1) removes item 1 from claim 1, or returns 204.
- Why: from the docs and prior knowledge (IDOR).
- Confidence: high

### F26: Deleting a claim leaves orphaned items / item ids reused
- Expected wrong behaviour: after a DELETE, new items reuse ids, or `q` search still matches deleted item descriptions.
- Why: from prior knowledge.
- Confidence: low

### F27: Path id parsing too lax
- Expected wrong behaviour: `/claims/007`, `/claims/1.0`, `/claims/1abc` or `/claims/+1` return claim 1 instead of 404 (parseInt). `/claims/0` or a negative id gives 400/500.
- Why: from the docs, which mention this explicitly.
- Confidence: high

### F28: Pagination errors
- Expected wrong behaviour: `next_page` is non-null on the last page (e.g. when total_count is an exact multiple of per_page), or null when more pages exist. `page=0`, `page=-1`, `page=1.5`, `per_page=0`, `per_page=51` or `per_page=abc` are accepted or cause a 500. `total_count` counts only the current page. Page offset is off by one.
- Why: from the docs and prior knowledge.
- Confidence: high

### F29: Sorting bugs
- Expected wrong behaviour: `sort=total` sorts lexicographically (as strings), ties are not ordered by id ascending (e.g. the descending sort also reverses ties), or the default is not newest first.
- Why: from the docs and prior knowledge.
- Confidence: medium

### F30: q search case-sensitive or ignores item descriptions
- Expected wrong behaviour: `q=TAXI` doesn't match "Taxi". Item descriptions are not searched. Regex special chars like `q=(` cause a 500. A claim is duplicated in results when multiple items match.
- Why: from the docs and prior knowledge.
- Confidence: medium

### F31: owner filter bypasses visibility
- Expected wrong behaviour: bob calling GET /claims?owner=alice sees alice's claims. Or a manager with owner= sees drafts.
- Why: from the docs and prior knowledge.
- Confidence: medium

### F32: Invalid status filter not rejected
- Expected wrong behaviour: `status=foo` or `status=SUBMITTED` returns 200 with an empty list instead of 400.
- Why: from the docs.
- Confidence: low

### F33: Malformed JSON / non-object body produces 500 or wrong error
- Expected wrong behaviour: an array body `[]` or `null` or `"str"` gives 500 or `validation_failed` instead of `invalid_body`. Malformed JSON gives 500. A body over 1MB gives 500 or isn't rejected with 413.
- Why: from the docs.
- Confidence: medium

### F34: Login type confusion
- Expected wrong behaviour: POST /auth/login with `username: ["alice"]` or a non-string password gives 500 or 401 instead of 400. A missing body gives 500.
- Why: from the docs.
- Confidence: low

### F35: Authorization header parsing
- Expected wrong behaviour: `bearer <token>` (lowercase) is rejected. Extra whitespace or a missing token ("Bearer ") gives 500. An unknown token gives 403.
- Why: from the docs.
- Confidence: low

### F36: Trailing slash and 405 handling
- Expected wrong behaviour: `/claims/` returns 404. PUT /claims/1 returns 404 instead of 405, or 405 without an `Allow` header.
- Why: from the docs.
- Confidence: medium

### F37: Description length checked before trim / not trimmed
- Expected wrong behaviour: a whitespace-only description is accepted, or a 201-char description with padding is mishandled. The stored description is not trimmed.
- Why: from the docs.
- Confidence: low

### F38: Purpose length limit not enforced (501 chars accepted) or title 121 chars accepted
- Expected wrong behaviour: an over-length title or purpose is accepted on POST or PATCH.
- Why: from the docs.
- Confidence: low

### F39: Payment reference validation missing
- Expected wrong behaviour: a reference of 65+ characters or a non-string reference (number) is accepted, or causes a 500.
- Why: from the docs.
- Confidence: low

### F40: Content-Type/204 bodies
- Expected wrong behaviour: a 204 response includes a body, or errors lack `charset=utf-8`.
- Why: from the docs.
- Confidence: low

## Questions

## Coverage
All sections: Conventions (ids, money, dates, trailing slash, errors), Authentication, Roles and visibility, Claim lifecycle, Rules for items (including the meals limit), Objects (Claim/Item fields, updated_at semantics), and every endpoint (ping, login, list with filters/sort/pagination, create, get, patch, delete, items add/remove, submit, review, pay).
