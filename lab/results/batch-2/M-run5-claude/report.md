# Prediction report

## Findings

### F1: Claim total has floating-point errors
- Expected wrong behaviour: `GET /claims/{id}` / `GET /claims` return totals like `0.30000000000000004` or `60.010000000000005` when items such as 0.1 + 0.2 or 20.1 + 19.91 + 20 are summed; totals are not rounded to 2 decimals.
- Why: from prior knowledge — naive JS `reduce((a,b)=>a+b)` on floats; docs stress "at most two decimal places".
- Confidence: high

### F2: Two-decimal check on `amount` rejects valid values or accepts 3 decimals
- Expected wrong behaviour: `POST /claims/{id}/items` with `amount: 4.35`, `1.15` or `8.2` rejected with 400 because `amount*100 % 1 !== 0`; or `12.345` accepted.
- Why: from prior knowledge — float multiplication check is a classic bug.
- Confidence: medium

### F3: `amount` upper bound off by one
- Expected wrong behaviour: `amount: 10000` rejected (uses `<`), or `10000.01` accepted.
- Why: from the docs ("at most 10000.00") + common boundary bug.
- Confidence: medium

### F4: `amount` 0 or negative or string accepted
- Expected wrong behaviour: `amount: 0`, `-5`, or `"12.50"` accepted (coerced with Number()).
- Why: from the docs explicitly calling out strings being rejected and "greater than 0".
- Confidence: medium

### F5: 90-day date window off by one
- Expected wrong behaviour: on 2026-11-10, `date: "2026-08-12"` is rejected, or `"2026-08-11"` is accepted.
- Why: from the docs giving exact boundary dates; easy to miscount days.
- Confidence: high

### F6: Today's date accepted/rejected wrongly due to time-of-day or local timezone
- Expected wrong behaviour: `date` equal to today (UTC) rejected as "future" (comparison against `new Date()` with time), or tomorrow accepted around midnight because local time is used instead of UTC.
- Why: from the docs ("Today always means UTC"); prior knowledge of Date pitfalls.
- Confidence: medium

### F7: Impossible calendar dates accepted
- Expected wrong behaviour: `date: "2026-02-30"`, `"2026-09-31"` or `"2026-13-01"` accepted (JS Date rolls over), or `"2026-9-5"` accepted.
- Why: from the docs ("a real calendar date"); prior knowledge of regex-only/Date.parse validation.
- Confidence: high

### F8: Meals limit boundary — exactly 60.00 rejected
- Expected wrong behaviour: meals items on one date totalling exactly 60.00 (e.g. 30 + 30, or 20.1 + 19.9 + 20 with float error) rejected with 400.
- Why: from the docs ("at most 60.00"); `>=` vs `>` and float sum issues.
- Confidence: medium

### F9: Meals limit not enforced across items inside one `POST /claims` body
- Expected wrong behaviour: `POST /claims` with two meals items on the same date of 40 each is accepted (each checked only against already-stored items, which are none).
- Why: from the docs (limit applies within one claim, checked in both POST /claims and POST items); batch validation often skips intra-batch sums.
- Confidence: high

### F10: Meals limit applied with wrong scope
- Expected wrong behaviour: limit summed across all dates, across other categories, or across the user's other claims; or not applied at all when adding via `POST /claims/{id}/items` on a rejected claim.
- Why: from the docs; scope is easy to get wrong.
- Confidence: low

### F11: Partial creation when an item in `POST /claims` is invalid
- Expected wrong behaviour: claim (and earlier valid items) persisted even though a later item fails validation; or claim/item id counters advance.
- Why: from the docs ("If any item is invalid, nothing is created").
- Confidence: medium

### F12: Wrong `field` path for item errors in `POST /claims`
- Expected wrong behaviour: error for the second item reports `items[0].date` / `items[2].date` (off by one) or just `date`.
- Why: from the docs (`items[1].date` example).
- Confidence: medium

### F13: Manager of another team can see or review claims
- Expected wrong behaviour: `frank` (mobile) `GET /claims/{id}` or `POST /claims/{id}/review` on alice's (platform) submitted claim returns 200 or 403 instead of 404.
- Why: from the docs (other-team claims must be invisible → 404); team check commonly missing in review.
- Confidence: high

### F14: Drafts leak to managers/finance
- Expected wrong behaviour: `GET /claims?status=draft` as carol or dave returns drafts, or `GET /claims/{draftId}` returns 200 / action returns 403 instead of 404.
- Why: from the docs (drafts invisible to non-owners).
- Confidence: high

### F15: Employee can read another employee's claim (IDOR)
- Expected wrong behaviour: bob `GET /claims/{alice's id}` returns 200, or bob's PATCH/DELETE/submit on alice's claim returns 403 (leaking existence) instead of 404.
- Why: from the docs (visibility rule 404); prior knowledge of IDOR.
- Confidence: medium

### F16: `owner` filter bypasses visibility
- Expected wrong behaviour: `GET /claims?owner=erin` as carol (platform manager) returns erin's claims; or `owner=alice` as bob returns alice's claims.
- Why: from the docs ("among the claims you can see"); filter applied instead of visibility.
- Confidence: medium

### F17: Search `q` incomplete
- Expected wrong behaviour: `GET /claims?q=TAXI` is case-sensitive, or `q` matching only an item description (e.g. `q=ICE`) doesn't match; or claim duplicated when multiple items match.
- Why: from the docs.
- Confidence: medium

### F18: `meta.next_page` wrong on exact last page
- Expected wrong behaviour: when `total_count` is an exact multiple of `per_page` (e.g. 4 claims, per_page=2, page=2) `next_page` is 3 instead of null; or past-end page gives non-null next_page.
- Why: from the docs ("next page that has results"); classic `data.length === per_page` check.
- Confidence: high

### F19: `meta.total_count` counts only the current page or all claims
- Expected wrong behaviour: `total_count` equals page length, or ignores status/q filters.
- Why: prior knowledge.
- Confidence: low

### F20: Pagination parameter validation gaps
- Expected wrong behaviour: `per_page=0`, `per_page=51`, `page=0`, `page=-1`, `page=1.5`, `page=abc` return 200 (or 500) instead of 400; or `per_page=50` rejected.
- Why: from the docs (ranges given).
- Confidence: high

### F21: Sort issues
- Expected wrong behaviour: `sort=total` sorts lexicographically or ties not broken by id ascending (e.g. for `-created_at`/`-total` ties ordered by id descending because the whole order is reversed); invalid `sort` (e.g. `title`) returns 200.
- Why: from the docs (tie-breaking by id ascending even for descending sort).
- Confidence: medium

### F22: Invalid `status` filter accepted
- Expected wrong behaviour: `GET /claims?status=APPROVED` or `status=foo` returns 200 with empty list instead of 400.
- Why: from the docs.
- Confidence: medium

### F23: Non-canonical ids in path treated as valid
- Expected wrong behaviour: `GET /claims/007`, `/claims/1.0`, `/claims/1e0` or `/claims/+1` return claim 1/7 instead of 404 (parseInt/Number used); `/claims/0` or `/claims/-1` gives 500/400.
- Why: from the docs (explicit `007` example).
- Confidence: high

### F24: Deleting an item from another claim
- Expected wrong behaviour: `DELETE /claims/4/items/{item id belonging to claim 5}` returns 204 and removes the item from the other claim (possibly someone else's or a submitted one).
- Why: from the docs ("must belong to the claim in the path").
- Confidence: high

### F25: PATCH mass assignment
- Expected wrong behaviour: `PATCH /claims/{id}` with `{"status":"approved"}`, `{"owner":"bob"}` or `{"total":1}` changes those fields.
- Why: from the docs (fields explicitly said to be ignored).
- Confidence: medium

### F26: PATCH validation gaps
- Expected wrong behaviour: `{"title": null}` accepted (or 500), whitespace-only title accepted, title stored untrimmed, `{"currency":"eur"}` accepted, `purpose: ""` stored as `""` instead of null, purpose of 501 chars accepted.
- Why: from the docs.
- Confidence: medium

### F27: `updated_at` not maintained correctly
- Expected wrong behaviour: not changed on item add/remove or status change (submit/review/pay); or changed by failed requests or by idempotent re-pay.
- Why: from the docs (precise definition).
- Confidence: medium

### F28: POST /claims validation gaps
- Expected wrong behaviour: whitespace-only or 121-char-after-trim title accepted; lowercase currency accepted; `items` not an array (e.g. object/string) gives 500; manager/finance gets 400 instead of 403 when body is invalid (order of checks); `Location` header missing.
- Why: from the docs.
- Confidence: medium

### F29: Description length counted wrongly
- Expected wrong behaviour: description of only spaces accepted; 200-char description with surrounding spaces rejected (length checked before trimming); emoji counted as two chars.
- Why: from the docs ("after trimming").
- Confidence: low

### F30: Submit an empty claim allowed
- Expected wrong behaviour: `POST /claims/{id}/submit` on a draft with no items, or on a rejected claim after all items were removed, returns 200.
- Why: from the docs.
- Confidence: medium

### F31: Resubmission doesn't update `submitted_at`
- Expected wrong behaviour: after reject → submit, `submitted_at` keeps old value.
- Why: from the docs ("timestamp of the last submission").
- Confidence: low

### F32: Missing state checks in review
- Expected wrong behaviour: `POST /claims/{id}/review` on an approved/rejected/paid claim returns 200 (changes status, e.g. paid → rejected) instead of 409.
- Why: from the docs.
- Confidence: medium

### F33: Reject comment validation
- Expected wrong behaviour: reject with `comment: ""` or `"   "` accepted; comment > 500 chars accepted; non-string comment gives 500; invalid `decision` (e.g. `"APPROVE"`) accepted.
- Why: from the docs.
- Confidence: medium

### F34: Pay from wrong status / non-idempotent repeat pay
- Expected wrong behaviour: paying a `submitted` claim succeeds; paying a `paid` claim again overwrites `paid_at`, `payment_reference` or records a second payment (amount_paid doubles).
- Why: from the docs (idempotent pay explicitly specified).
- Confidence: high

### F35: Pay reference validation
- Expected wrong behaviour: reference of 65+ chars accepted; numeric reference gives 500; empty body / no Content-Type causes 400 even though body is optional.
- Why: from the docs.
- Confidence: medium

### F36: Wrong status for role checks (403 vs 404 vs 409)
- Expected wrong behaviour: finance approving returns 409 or 404 instead of 403; manager editing a team claim returns 409 instead of 403 (state checked before ownership); employee reviewing own claim returns 404.
- Why: from the docs (precise 403/404/409 rules).
- Confidence: medium

### F37: Item/claim ids reused after delete
- Expected wrong behaviour: after deleting a claim or item, the next created claim/item gets the same id (id = array length + 1), causing duplicate ids.
- Why: from prior knowledge; docs say item ids are unique across claims.
- Confidence: medium

### F38: Totals stale after item removal / in list
- Expected wrong behaviour: after `DELETE /claims/{id}/items/{itemId}`, `total` in GET or list summary still includes the deleted amount; `amount_paid` differs from `total`.
- Why: from prior knowledge of cached totals.
- Confidence: low

### F39: Delete claim leaves orphaned items or allows non-draft deletion
- Expected wrong behaviour: deleting a rejected claim returns 204; items of a deleted claim remain reachable/counted.
- Why: from the docs (delete only from draft).
- Confidence: low

### F40: Auth header parsing
- Expected wrong behaviour: `authorization: bearer <token>` (lowercase scheme) rejected with 401; or `Bearer` with extra spaces / no scheme (raw token) accepted.
- Why: from the docs ("scheme case-insensitive").
- Confidence: medium

### F41: Login validation errors
- Expected wrong behaviour: non-string `username`/`password` (e.g. numbers, null) give 500 or 401 instead of 400; username matched case-insensitively; missing body gives 500.
- Why: from the docs.
- Confidence: medium

### F42: Body parsing errors not mapped correctly
- Expected wrong behaviour: malformed JSON returns 500 instead of `invalid_json`; array body returns 500/validation_failed instead of `invalid_body`; >1 MB body returns 500 instead of 413.
- Why: from the docs (error table); prior knowledge of Express body-parser defaults.
- Confidence: medium

### F43: 405 / routing issues
- Expected wrong behaviour: `PUT /claims/1` returns 404 instead of 405, or 405 without `Allow` header; `/claims/` trailing slash returns 404; malformed URL (e.g. `/claims/%`) gives 500 instead of `invalid_url`.
- Why: from the docs.
- Confidence: medium

### F44: Currency change on claim with items not handled / allowed in wrong state
- Expected wrong behaviour: PATCH currency on a submitted/approved claim succeeds (state check only for title).
- Why: from the docs.
- Confidence: low

## Questions

## Coverage
Based on all sections of api.md: conventions (ids, money, dates, trailing slash, errors), authentication, roles and visibility, claim lifecycle, item rules (date window, amount, meals limit), Claim/summary/Item objects (totals, timestamps), and every endpoint (ping, login, list with filters/sort/pagination, create, get, patch, delete, items add/remove, submit, review, pay).
