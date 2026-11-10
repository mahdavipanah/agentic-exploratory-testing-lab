# Prediction report

## Findings

### F1: Manager can review a submitted claim from another team
- Expected wrong behaviour: frank (mobile manager) sends `POST /claims/{id}/review` with `{"decision":"approve"}` on a submitted platform claim and gets 200 (or 403), not 404. The check is probably only `role === manager`.
- Why: from prior knowledge. Missing object-level authorization (BOLA) is the most common bug in role-based APIs. The docs stress team scoping.
- Confidence: high

### F2: Managers or finance can see draft claims
- Expected wrong behaviour: carol sends `GET /claims/{id}` for a draft owned by alice or bob, or dave fetches any draft, and gets 200 instead of 404. Drafts may also show up in `GET /claims` or with `?status=draft`.
- Why: from the docs, which list the "except drafts" visibility rule. Rules like this are often enforced in only one of the two places (list or detail).
- Confidence: high

### F3: `owner` filter leaks other employees' claims
- Expected wrong behaviour: alice calls `GET /claims?owner=bob` and gets bob's claims, because the filter replaces the visibility filter instead of narrowing it.
- Why: from prior knowledge, a common filter-composition bug.
- Confidence: medium

### F4: Deleting an item through a different claim's path works
- Expected wrong behaviour: `DELETE /claims/{A}/items/{itemOfClaimB}` returns 204 and removes the item from claim B, which may not be in an editable state. This can also skip B's state check.
- Why: from the docs ("item must belong to the claim in the path"). This is a classic IDOR.
- Confidence: high

### F5: Paying an already-paid claim records a second payment or changes fields
- Expected wrong behaviour: a second `POST /claims/{id}/pay` on a paid claim overwrites `paid_at` and `payment_reference`, or adds another payment.
- Why: from the docs, which explicitly promise idempotency. That promise is often half-implemented.
- Confidence: medium

### F6: Paying a claim in the wrong state succeeds
- Expected wrong behaviour: `POST /pay` on a `submitted`, `rejected` or `draft` claim returns 200 and sets it to `paid`, instead of returning 409. A related case: a submitted claim gets paid without approval.
- Why: from prior knowledge of state-machine bypasses.
- Confidence: medium

### F7: Review is allowed on a claim that isn't submitted
- Expected wrong behaviour: carol approves or rejects a claim that is already `approved`, `rejected` or `paid` and gets 200. For example, a paid claim goes back to `rejected`.
- Why: from prior knowledge of state-machine bypasses.
- Confidence: medium

### F8: Float rounding in total
- Expected wrong behaviour: items of 0.1 and 0.2 (or 19.99 + 5.01 and similar) produce `total` like `0.30000000000000004` in the claim, the list summary, or `amount_paid`.
- Why: from prior knowledge of JS number summation. The docs promise at most two decimals.
- Confidence: high

### F9: Two-decimal check misjudges valid amounts
- Expected wrong behaviour: the check uses `amount*100 % 1` or `Number.isInteger(amount*100)`, so valid values like `1.13`, `4.35`, `8.2` or `19.99` are rejected. Or the check is string-based and `1e-7` or `0.001` slips through.
- Why: from prior knowledge of float precision in decimal validation.
- Confidence: medium

### F10: Amount boundary off-by-one
- Expected wrong behaviour: `amount: 10000` is rejected, or `10000.01` is accepted. `amount: 0` or negative values might also be accepted.
- Why: from prior knowledge of boundary checks.
- Confidence: medium

### F11: Numeric string amount accepted
- Expected wrong behaviour: `"amount":"12.50"` is coerced and accepted with 201.
- Why: from the docs (an explicit rule usually tests a known bug).
- Confidence: medium

### F12: Date 90-day window off-by-one
- Expected wrong behaviour: the earliest allowed date (today minus 90 days, e.g. 2026-08-12) is rejected, or today minus 91 is accepted.
- Why: from the docs, which give an exact boundary example. Date arithmetic with timestamps and timezones usually gets this wrong.
- Confidence: medium

### F13: Today's date is rejected, or tomorrow is accepted, because of timezone handling
- Expected wrong behaviour: depending on local and UTC time, today's date is treated as future, or tomorrow's date is accepted.
- Why: from prior knowledge. Comparing `new Date('YYYY-MM-DD')` (UTC midnight) with local "now" causes this.
- Confidence: medium

### F14: Impossible calendar dates accepted
- Expected wrong behaviour: `"date":"2026-02-30"` or `"2026-09-31"` passes because JS Date rolls it over to the next valid date. Formats like `2026-9-5` might also pass.
- Why: from prior knowledge ("A real calendar date" in the docs hints at this).
- Confidence: high

### F15: Meals daily limit is wrong at the boundary or across items
- Expected wrong behaviour: one of these:
  - meals totalling exactly 60.00 are rejected (`>=` used).
  - the check only looks at the new item (a single item over 60) and not the sum per date.
  - non-meals items are included in the sum.
  - items on other dates are included in the sum.
- Why: from the docs (explicit, detailed business rule).
- Confidence: medium

### F16: Meals limit not enforced among items in `POST /claims`
- Expected wrong behaviour: creating a claim with two meals items on the same date (40 + 40) succeeds, because each item is only checked against existing items, not against earlier items in the same batch.
- Why: from prior knowledge of batch-validation bugs.
- Confidence: medium

### F17: Invalid item in `POST /claims` still creates the claim
- Expected wrong behaviour: a claim with one valid and one invalid item returns 400, but a claim (with the valid item) is still created. Later the list shows it, or the next claim id skips a number.
- Why: from the docs ("If any item is invalid, nothing is created"). Atomicity is often missed.
- Confidence: medium

### F18: Wrong index in the `field` of an item error
- Expected wrong behaviour: an error in the second item is reported as `items[2].date` (1-based) or without the index at all (`date`).
- Why: from the docs, which give an example format.
- Confidence: low

### F19: Description or title length checked before trimming, or not trimmed
- Expected wrong behaviour: a description of only spaces (`"   "`) is accepted, or 200 characters plus surrounding spaces is rejected. The stored value may be untrimmed.
- Why: from the docs ("after trimming").
- Confidence: medium

### F20: Invalid category, or currency in the wrong case, accepted
- Expected wrong behaviour: `"currency":"eur"` is accepted in POST or PATCH, or an unknown category is accepted.
- Why: from the docs ("upper case" is emphasised).
- Confidence: low

### F21: PATCH applies ignored fields (mass assignment)
- Expected wrong behaviour: `PATCH /claims/{id}` with `{"status":"approved"}`, `owner` or `total` changes those fields.
- Why: from the docs, which explicitly list ignored fields. This is a classic mass-assignment bug.
- Confidence: medium

### F22: PATCH accepts `title: null` or an empty or too-long title
- Expected wrong behaviour: `{"title":null}` returns 200 and sets the title to null, or `{"title":""}` is accepted.
- Why: from the docs ("cannot be null").
- Confidence: medium

### F23: PATCH `purpose: ""` not normalised to null (and the same in POST)
- Expected wrong behaviour: purpose is stored as `""` instead of `null`.
- Why: from the docs.
- Confidence: low

### F24: Editing a claim allowed in a non-editable state
- Expected wrong behaviour: PATCH or `POST /items` on a `submitted`, `approved` or `paid` claim returns 200 or 201 instead of 409. For example, an item is added after approval, so the paid amount differs from the approved total.
- Why: from prior knowledge of state checks.
- Confidence: medium

### F25: DELETE of a rejected claim allowed
- Expected wrong behaviour: `DELETE /claims/{id}` on a `rejected` claim returns 204. Deletion should be allowed only from `draft`, but the code reuses the "editable" check (draft or rejected).
- Why: from the docs (delete and edit have different allowed states, which invites code reuse).
- Confidence: medium

### F26: Submit with no items succeeds
- Expected wrong behaviour: submitting an empty draft returns 200, or returns 409 instead of 400 with `field: items`. A claim whose only item was deleted might also be submittable.
- Why: from the docs.
- Confidence: medium

### F27: Reject without a real comment accepted
- Expected wrong behaviour: `{"decision":"reject"}`, `"comment":""` or a whitespace-only comment returns 200. A comment over 500 characters might be accepted.
- Why: from the docs.
- Confidence: medium

### F28: Owner gets the wrong status when reviewing their own claim, or non-managers can review
- Expected wrong behaviour: alice reviewing her own submitted claim gets 200, or dave (finance) can approve.
- Why: from the docs (explicit 403 examples).
- Confidence: low

### F29: Payment reference length not validated
- Expected wrong behaviour: a 65+ character `reference`, or a non-string such as a number, is accepted.
- Why: from the docs.
- Confidence: low

### F30: `updated_at` not updated on item add or remove, or on status change
- Expected wrong behaviour: after `POST /claims/{id}/items` or an item deletion, `updated_at` is unchanged. Review or pay may also leave it unchanged.
- Why: from the docs (lists exactly what counts as a write).
- Confidence: medium

### F31: Total not recalculated after item deletion, or in the list summary
- Expected wrong behaviour: the `total` in `GET /claims` summaries is stale or missing after items change, or is a string.
- Why: from prior knowledge of cached or denormalized totals.
- Confidence: low

### F32: `next_page` wrong on the last page
- Expected wrong behaviour: when `total_count` is an exact multiple of `per_page`, the last page reports `next_page` pointing to an empty page. A page past the end may also report a non-null `next_page`.
- Why: from the docs ("next page that has results"). This is a common off-by-one.
- Confidence: high

### F33: `total_count` reflects page size or the unfiltered count
- Expected wrong behaviour: `meta.total_count` equals the number of items on the current page, or ignores the `status`, `q` or `owner` filters.
- Why: from prior knowledge.
- Confidence: medium

### F34: Pagination params poorly validated
- Expected wrong behaviour: `per_page=0`, `per_page=51`, `page=0`, `page=-1`, `page=1.5` or `page=abc` is accepted (or causes 500) instead of returning 400. `per_page=50` might be rejected.
- Why: from prior knowledge.
- Confidence: medium

### F35: Sort by total is wrong
- Expected wrong behaviour: `sort=total` sorts lexicographically, or ties are not ordered by ascending id. With `-total` or `-created_at`, ties may be reversed to descending id.
- Why: from the docs, which specify the tie-break.
- Confidence: medium

### F36: `q` search is case-sensitive or ignores item descriptions
- Expected wrong behaviour: `q=TAXI` doesn't match "Taxi to airport", or a term that appears only in an item description doesn't match. Regex special characters in `q` (e.g. `(`) may cause 500.
- Why: from the docs.
- Confidence: medium

### F37: Invalid `status` filter returns 200
- Expected wrong behaviour: `GET /claims?status=foo` returns 200 with an empty list, and `?sort=foo` is silently ignored.
- Why: from the docs.
- Confidence: low

### F38: Non-canonical path ids accepted
- Expected wrong behaviour: `GET /claims/007` or `/claims/1.0` returns claim 7 or claim 1 instead of 404 (via `parseInt`/`Number`). `/claims/abc` may give 500 or 400.
- Why: from the docs (explicit `007` example).
- Confidence: high

### F39: Trailing slash or 405 handling wrong
- Expected wrong behaviour: `/claims/` returns 404, or `PUT /claims/1` returns 404 instead of 405, or returns 405 without an `Allow` header.
- Why: from the docs.
- Confidence: low

### F40: Malformed body handling
- Expected wrong behaviour: invalid JSON returns 500, a JSON array or `null` body returns 500 or `validation_failed` instead of `invalid_body`, and a body over 1 MB returns 500 instead of 413.
- Why: from prior knowledge.
- Confidence: medium

### F41: Login crashes on non-string credentials
- Expected wrong behaviour: `{"username":123,"password":{}}` returns 500 or 401 instead of 400. A missing body may return 500.
- Why: from the docs.
- Confidence: low

### F42: Bearer scheme handling
- Expected wrong behaviour: `Authorization: bearer <token>` (lowercase) returns 401, or a new login invalidates older tokens.
- Why: from the docs.
- Confidence: low

### F43: Ids reused after deletion
- Expected wrong behaviour: after deleting a claim or item, the next created claim or item reuses the id (because it's computed from array length), so item ids are not unique.
- Why: from prior knowledge of in-memory stores.
- Confidence: low

### F44: Managers or finance can create claims
- Expected wrong behaviour: `POST /claims` as carol or dave returns 201 instead of 403.
- Why: from the docs.
- Confidence: low

### F45: Location header missing or wrong on create
- Expected wrong behaviour: the 201 response from `POST /claims` has no `Location` header.
- Why: from the docs.
- Confidence: low

### F46: Currency PATCH on a claim with items gets 400, or converts amounts
- Expected wrong behaviour: PATCH currency changes the item amounts, or is refused.
- Why: from the docs ("Amounts are not converted").
- Confidence: low

## Questions

## Coverage
I used every section of api.md: conventions (ids, money, dates, trailing slash, errors), authentication, roles and visibility, the claim lifecycle, item rules (including the meals limit), the Claim, Summary and Item objects, and all twelve endpoints. That covers list filtering, sorting and pagination, create/patch/delete, items, submit/review/pay, and the error statuses 400, 401, 403, 404, 405, 409 and 413.
