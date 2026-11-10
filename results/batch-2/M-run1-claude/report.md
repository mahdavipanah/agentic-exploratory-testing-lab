# Prediction report

## Findings

### F1: Total uses floating-point sum, giving values like 251.39999999999998
- Expected wrong behaviour: `total` (claim and summary) and `amount_paid` are computed with naive float addition, e.g. items 0.1 + 0.2 give `total: 0.30000000000000004`; seed claim 1 may show a non-2-decimal total.
- Why: from prior knowledge (JS float summing is a classic money bug); docs stress "at most two decimal places".
- Confidence: medium

### F2: Amount decimal-place check fails on float edge cases
- Expected wrong behaviour: `POST /claims/{id}/items` with `amount: 1.005` or `0.001` accepted, or valid values like `1.15`/`4.35`/`19.99` rejected because the check uses `amount*100 % 1` style math.
- Why: from prior knowledge.
- Confidence: medium

### F3: Amount boundary off-by-one at 10000 / 0
- Expected wrong behaviour: `amount: 10000` rejected (uses `<` instead of `<=`), or `10000.01` accepted; or `amount: 0` / negative accepted.
- Why: from the docs (explicit boundary "at most 10000.00", "greater than 0").
- Confidence: low

### F4: Amount as string accepted/coerced
- Expected wrong behaviour: `POST /claims/{id}/items` with `"amount":"12.50"` returns 201 (coerced via Number()), despite docs saying strings are rejected. Also `NaN`/`true` handling.
- Why: from the docs (explicit rule called out) and prior knowledge.
- Confidence: medium

### F5: 90-day date window off by one
- Expected wrong behaviour: `date: "2026-08-12"` (exactly 90 days ago) rejected, or `2026-08-11` accepted; today's date may be rejected due to timezone/time-of-day comparisons (comparing to `new Date()` with time, or local time instead of UTC).
- Why: from the docs (very specific worked example of the boundary).
- Confidence: medium

### F6: Impossible calendar dates accepted
- Expected wrong behaviour: `date: "2026-02-30"` or `"2026-09-31"` accepted because JS Date rolls over; or `"2026-9-5"` accepted by a loose regex.
- Why: from the docs ("a real calendar date") and prior knowledge.
- Confidence: medium

### F7: Meals daily limit off-by-one or ignores existing items
- Expected wrong behaviour: meals adding up to exactly 60.00 on one date rejected (`<` vs `<=`), or limit only checks the single item (e.g. two 40.00 meals same day both accepted), or in `POST /claims` with `items[]` the limit is not checked across items in the same request. Float sum may also make 20.1+20.2+19.7 = 60.00000000001 rejected.
- Why: from the docs (explicit rule) and prior knowledge.
- Confidence: medium

### F8: Meals limit counts items of other claims or other categories
- Expected wrong behaviour: the per-day meals sum includes meals from the user's other claims, or includes non-meal items on that date, so a valid meal is rejected.
- Why: from the docs ("Within one claim").
- Confidence: low

### F9: POST /claims with invalid item still creates the claim (non-atomic)
- Expected wrong behaviour: `POST /claims` with items where `items[1]` is invalid returns 400 but a draft claim (possibly with item 0) is left behind and appears in `GET /claims`; or item ids get consumed.
- Why: from the docs ("If any item is invalid, nothing is created").
- Confidence: medium

### F10: Validation error field lacks item index
- Expected wrong behaviour: `POST /claims` invalid nested item returns `field: "date"` instead of `items[1].date`, or index off by one.
- Why: from the docs.
- Confidence: low

### F11: DELETE item does not check item belongs to the claim
- Expected wrong behaviour: `DELETE /claims/4/items/1` (item 1 belongs to claim 1, an approved claim of alice) returns 204 and removes an item from another claim, bypassing status checks.
- Why: from the docs ("The item must belong to the claim in the path") — classic IDOR.
- Confidence: high

### F12: Manager can review claims from other teams
- Expected wrong behaviour: `frank` (mobile) can see/approve a submitted platform claim via `POST /claims/{id}/review`, or `GET /claims/{id}` returns it instead of 404.
- Why: from the docs (team-scoped manager rights) — common authz bug.
- Confidence: medium

### F13: Drafts visible to managers/finance
- Expected wrong behaviour: `GET /claims/{id}` for a draft as carol or dave returns 200 instead of 404; or `GET /claims?status=draft` as manager/finance lists drafts; or `owner=alice` filter bypasses visibility.
- Why: from the docs.
- Confidence: medium

### F14: Wrong status code ordering: 403 vs 404 leak
- Expected wrong behaviour: for a claim the caller can't see (e.g. bob on alice's claim), mutating endpoints (PATCH, DELETE, submit, items) return 403 or 409 instead of 404, leaking existence.
- Why: from the docs ("behaves as if it did not exist").
- Confidence: medium

### F15: Status check precedes ownership/role check (409 instead of 403)
- Expected wrong behaviour: finance calling `/review` on an approved claim gets 409 instead of 403; manager PATCHing a submitted claim gets 409 instead of 403.
- Why: from prior knowledge of check-ordering bugs.
- Confidence: low

### F16: Manager can review their own claim / employee can review
- Expected wrong behaviour: the owner employee calling `POST /claims/{id}/review` succeeds, or role check only checks team, not role.
- Why: from the docs (403 for owner explicitly listed).
- Confidence: low

### F17: Pay is not idempotent
- Expected wrong behaviour: second `POST /claims/{id}/pay` on a paid claim returns 409, or updates `paid_at`/`payment_reference`/`updated_at`, or doubles `amount_paid`.
- Why: from the docs (idempotency explicitly promised).
- Confidence: medium

### F18: Pay allowed from non-approved state
- Expected wrong behaviour: `POST /claims/{id}/pay` on a `submitted` or `rejected` claim succeeds.
- Why: from prior knowledge.
- Confidence: low

### F19: Reject without comment / whitespace comment accepted
- Expected wrong behaviour: `{"decision":"reject","comment":"   "}` or `comment: ""` accepted; comment over 500 chars accepted; non-string comment accepted.
- Why: from the docs.
- Confidence: medium

### F20: Approve keeps previous review_comment
- Expected wrong behaviour: after reject (with comment) → resubmit → approve without comment, `review_comment` still holds the old rejection comment instead of null.
- Why: from the docs ("Comment from the last review").
- Confidence: medium

### F21: Resubmission doesn't update submitted_at / updated_at not bumped
- Expected wrong behaviour: submitting a rejected claim keeps old `submitted_at`; adding/removing items doesn't change `updated_at`; or failed writes (400) still bump `updated_at`.
- Why: from the docs (updated_at definition).
- Confidence: medium

### F22: Submit with zero items allowed
- Expected wrong behaviour: submit on a draft whose items were all deleted returns 200 instead of 400 `field: items`.
- Why: from the docs.
- Confidence: low

### F23: PATCH allows protected fields or title null
- Expected wrong behaviour: `PATCH {"status":"approved"}` or `{"owner":"bob"}` or `{"total":1}` changes the claim (mass assignment); `{"title":null}` accepted; `{"currency":"eur"}` accepted.
- Why: from the docs (explicitly lists ignored fields) and prior knowledge.
- Confidence: medium

### F24: PATCH purpose empty string not normalized to null
- Expected wrong behaviour: `PATCH {"purpose":""}` or `POST /claims` with `purpose: ""` stores `""` instead of `null`; whitespace-only titles accepted; title stored untrimmed.
- Why: from the docs.
- Confidence: medium

### F25: Title length counted before trimming / over-limit off by one
- Expected wrong behaviour: title of 120 chars + surrounding spaces rejected, or 121 chars accepted; description of 200 chars rejected.
- Why: from the docs.
- Confidence: low

### F26: Pagination next_page wrong / total_count wrong
- Expected wrong behaviour: `meta.next_page` is non-null on the last page when count is exact multiple of per_page (e.g. 4 claims, per_page=2, page=2 gives next_page 3); `total_count` equals page length rather than all matches.
- Why: from the docs (next_page "has results").
- Confidence: medium

### F27: page/per_page validation gaps
- Expected wrong behaviour: `per_page=0`, `per_page=51`, `page=0`, `page=-1`, `page=1.5`, `page=abc` return 200 (clamped or NaN → empty) instead of 400; `per_page=50` rejected.
- Why: from the docs.
- Confidence: medium

### F28: Sort ties not ordered by id ascending / total sort is string sort
- Expected wrong behaviour: `sort=-total` reverses tie order too (ids descending), or sorts totals lexicographically ("100" < "37.8").
- Why: from the docs ("Ties are ordered by id, ascending").
- Confidence: medium

### F29: Search q is case-sensitive or ignores item descriptions
- Expected wrong behaviour: `q=TAXI` doesn't match "Taxi"; `q` matching item descriptions not implemented; regex special chars like `q=(` cause 500.
- Why: from the docs and prior knowledge (regex-built search).
- Confidence: medium

### F30: Invalid status filter accepted / case issues
- Expected wrong behaviour: `GET /claims?status=foo` returns 200 empty list instead of 400; `sort=foo` ignored.
- Why: from the docs.
- Confidence: low

### F31: Path id parsing too lenient
- Expected wrong behaviour: `GET /claims/007`, `/claims/1.0`, `/claims/0x1` or `/claims/1abc` returns claim 1 (parseInt) instead of 404.
- Why: from the docs (explicit example `007`).
- Confidence: medium

### F32: Trailing slash and 405 handling
- Expected wrong behaviour: `GET /claims/` returns 404; `PUT /claims/1` returns 404 instead of 405, or 405 lacks `Allow` header / lists wrong methods; trailing slash on `/claims/1/` not handled.
- Why: from the docs.
- Confidence: low

### F33: Body parsing errors mishandled
- Expected wrong behaviour: malformed JSON yields 500 instead of `invalid_json`; array body `[]` or `null` body gives 500 or `validation_failed` instead of `invalid_body`; >1 MB body returns 500 instead of 413; bad URL like `/claims/%` gives 500 instead of `invalid_url`.
- Why: from the docs and prior knowledge.
- Confidence: medium

### F34: Login validation and auth header edge cases
- Expected wrong behaviour: `POST /auth/login` with non-string username (number) gives 500 or 401 instead of 400; `Authorization: bearer <token>` (lowercase) rejected; new login invalidates older tokens.
- Why: from the docs.
- Confidence: low

### F35: Item id not unique across claims / reused after delete
- Expected wrong behaviour: new item ids collide with seed ids or reuse deleted ids; claim ids reused after DELETE.
- Why: from the docs ("unique across all claims").
- Confidence: low

### F36: Currency change allowed with no validation / case-insensitive
- Expected wrong behaviour: `POST /claims` with `currency: "usd"` or `"JPY"` accepted.
- Why: from the docs ("upper case").
- Confidence: low

### F37: Pay reference validation
- Expected wrong behaviour: `reference` of 65 chars or a non-string (number) accepted; missing body on pay returns 400 invalid_json instead of being optional.
- Why: from the docs.
- Confidence: low

### F38: Delete claim leaves orphaned items
- Expected wrong behaviour: after `DELETE /claims/{id}`, its items still exist (e.g. still matched by search or still counted), or delete allowed on rejected claim.
- Why: from the docs.
- Confidence: low

### F39: Owner filter bypasses visibility
- Expected wrong behaviour: `GET /claims?owner=bob` as alice returns bob's claims, or as frank returns platform claims.
- Why: from the docs ("among the claims you can see").
- Confidence: low

## Questions

## Coverage
Conventions (ids, money, dates, trailing slash, errors table), authentication, roles and visibility, lifecycle, item rules (incl. meals limit), Claim/Summary/Item objects, and every endpoint: login, GET/POST /claims, GET/PATCH/DELETE /claims/{id}, item add/remove, submit, review, pay.
