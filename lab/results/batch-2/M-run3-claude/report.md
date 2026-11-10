# Prediction report

## Findings

### F1: Claim total shows floating-point errors
- Expected wrong behaviour: Items 0.1 + 0.2 (or 89.9 + 119 + 42.5 style sums) give `total` like `0.30000000000000004`, which breaks the "at most two decimal places" rule; `amount_paid` inherits the same error.
- Why: from prior knowledge (summing JS floats without rounding or integer cents)
- Confidence: medium

### F2: Two-decimal check on amount rejects valid values or accepts invalid ones
- Expected wrong behaviour: POST /claims/{id}/items with `amount` 0.29, 1.13 or 4.35 rejected (`x*100` not an integer), or 1.005 / 12.345 accepted.
- Why: from prior knowledge (float `Number.isInteger(amount*100)` checks)
- Confidence: medium

### F3: Amount boundaries wrong
- Expected wrong behaviour: `amount` 10000 rejected or 10000.01 accepted; `0` or negative amounts accepted.
- Why: from the docs (explicit boundaries: >0 and ≤10000.00), common off-by-one
- Confidence: medium

### F4: String amounts accepted
- Expected wrong behaviour: `"amount":"12.50"` is coerced and accepted (201) instead of 400.
- Why: from the docs (explicitly called out, which suggests a trap)
- Confidence: medium

### F5: Meals daily limit off-by-one at exactly 60.00
- Expected wrong behaviour: Meals items that add up to exactly 60.00 on one date are rejected (uses `>=`), or 60.01 accepted; float sums like 20.1+19.9+20 fail by mistake.
- Why: from the docs (boundary 60.00 is stated precisely)
- Confidence: medium

### F6: Meals limit not enforced across items in the same POST /claims body
- Expected wrong behaviour: POST /claims with two meals items on the same date of 40 each is accepted, because the check only looks at items already stored, not earlier items in the same batch.
- Why: from prior knowledge (batch validation done before insertion)
- Confidence: medium

### F7: Meals limit counted wrongly (only the new item, all claims, or ignoring the date)
- Expected wrong behaviour: Adding a 30 meal to a claim that already has a 40 meal on the same date succeeds; or meals in *other* claims / other dates count toward the limit.
- Why: from the docs (the "within one claim, same date" scope is easy to get wrong)
- Confidence: medium

### F8: 90-day date window off by one
- Expected wrong behaviour: Item dated exactly 90 days ago (2026-08-12 when today is 2026-11-10) rejected, or 91 days ago (2026-08-11) accepted.
- Why: from the docs (exact boundary example given)
- Confidence: medium

### F9: Today/future date computed in local time instead of UTC
- Expected wrong behaviour: Around midnight UTC, today's date is rejected as future or tomorrow's date accepted; date window shifts by one day.
- Why: from the docs ("Today always means the current date in UTC")
- Confidence: low

### F10: Impossible calendar dates accepted
- Expected wrong behaviour: `date` "2026-02-30", "2026-09-31" or "2026-13-01" accepted (JS Date rolls over), or non-padded "2026-9-5" accepted.
- Why: from prior knowledge (regex + `new Date()` validation)
- Confidence: medium

### F11: Whitespace-only description/title accepted, or length checked before trimming
- Expected wrong behaviour: `description: "   "` or `title: "   "` accepted; a 200-char description with padding rejected; stored values not trimmed.
- Why: from the docs ("after trimming")
- Confidence: medium

### F12: Category or currency validation case-insensitive or missing
- Expected wrong behaviour: `currency: "eur"` accepted on POST /claims or PATCH; unknown category accepted.
- Why: from the docs ("upper case")
- Confidence: low

### F13: POST /claims not atomic when an item is invalid
- Expected wrong behaviour: A body with a valid first item and an invalid second one returns 400, but a claim (with the first item) is created anyway and shows up in GET /claims; or item ids get used up.
- Why: from the docs ("If any item is invalid, nothing is created")
- Confidence: medium

### F14: Error `field` index for items is wrong
- Expected wrong behaviour: Invalid second item reports `items[2].date` (1-based) or just `date`, instead of `items[1].date`.
- Why: from the docs
- Confidence: low

### F15: Manager can see or act on draft claims of team members
- Expected wrong behaviour: carol's GET /claims includes platform drafts, or GET /claims/{draftId} returns 200 instead of 404 for a manager.
- Why: from the docs (visibility excludes drafts for managers)
- Confidence: medium

### F16: Finance can see drafts
- Expected wrong behaviour: dave's GET /claims or GET /claims/{id} returns draft claims.
- Why: from the docs
- Confidence: medium

### F17: Manager can review a claim from another team
- Expected wrong behaviour: frank (mobile) POST /claims/{id}/review on a submitted platform claim returns 200 (or 403 instead of 404, revealing it exists).
- Why: from the docs (team check is easy to forget; should be 404 because not visible)
- Confidence: high

### F18: Other employees' claims return 403 instead of 404
- Expected wrong behaviour: bob GET/PATCH/DELETE /claims/{alice's id} returns 403 (or even 200) instead of 404.
- Why: from the docs (visibility must look like non-existence)
- Confidence: medium

### F19: `owner` filter bypasses visibility
- Expected wrong behaviour: alice GET /claims?owner=bob returns bob's claims; or manager filtering by owner sees drafts / other teams.
- Why: from prior knowledge (filter applied instead of, not in addition to, visibility)
- Confidence: medium

### F20: Invalid list query parameters not rejected
- Expected wrong behaviour: `status=foo` returns empty list 200; `sort=title` silently defaults; `page=0`, `page=-1`, `page=abc`, `per_page=0` or `per_page=51` accepted, or `per_page=50` rejected.
- Why: from the docs
- Confidence: medium

### F21: Pagination meta wrong
- Expected wrong behaviour: `total_count` equals the number on the current page; `next_page` is non-null on the last page (e.g., when total is an exact multiple of per_page) or null when more remain.
- Why: from prior knowledge
- Confidence: medium

### F22: Sorting wrong
- Expected wrong behaviour: `sort=total` sorts lexicographically or ties not broken by ascending id (ties reversed for descending sorts); default not newest-first.
- Why: from the docs ("Ties are ordered by id, ascending" even for `-` sorts)
- Confidence: medium

### F23: Search `q` incomplete
- Expected wrong behaviour: `q` is case-sensitive, or only matches titles and not item descriptions (e.g., `q=hotel` doesn't find claim 1).
- Why: from the docs
- Confidence: medium

### F24: PATCH mass assignment
- Expected wrong behaviour: PATCH with `{"status":"approved"}`, `owner`, or `total` changes those fields.
- Why: from the docs (explicitly says ignored)
- Confidence: medium

### F25: PATCH accepts `title: null` or crashes
- Expected wrong behaviour: `{"title":null}` returns 200 with null title or 500, instead of 400.
- Why: from the docs
- Confidence: medium

### F26: PATCH/item changes allowed in wrong status
- Expected wrong behaviour: PATCH, POST items or DELETE items on a submitted/approved/paid claim returns 200/201/204 instead of 409; or edits on a rejected claim wrongly return 409.
- Why: from the docs
- Confidence: medium

### F27: Status vs ownership check order wrong
- Expected wrong behaviour: A manager PATCHing a submitted claim gets 409 instead of 403 (or the owner gets 403 instead of 409).
- Why: from prior knowledge
- Confidence: low

### F28: `purpose` empty string not converted to null
- Expected wrong behaviour: POST/PATCH with `purpose: ""` stores `""`; purpose over 500 chars accepted.
- Why: from the docs
- Confidence: medium

### F29: `updated_at` not updated on item add/remove or status change
- Expected wrong behaviour: After POST /claims/{id}/items or DELETE item, `updated_at` stays the same; or a failed request changes it.
- Why: from the docs
- Confidence: medium

### F30: Total not recomputed after item removal
- Expected wrong behaviour: DELETE /claims/{id}/items/{itemId} leaves `total` (stored/cached) unchanged in GET or list.
- Why: from prior knowledge
- Confidence: low

### F31: Deleting an item through the wrong claim id
- Expected wrong behaviour: DELETE /claims/4/items/{itemOfAnotherClaim} deletes it (204) instead of 404, even an item in someone else's claim.
- Why: from the docs ("The item must belong to the claim in the path")
- Confidence: high

### F32: DELETE claim allowed outside draft
- Expected wrong behaviour: Deleting a rejected claim returns 204 instead of 409.
- Why: from the docs (edit allowed for rejected but delete only for draft)
- Confidence: medium

### F33: Submit allows empty claim
- Expected wrong behaviour: POST /claims/{id}/submit on a draft with no items returns 200, or 409 rather than 400 with `field: items`.
- Why: from the docs
- Confidence: medium

### F34: Submit allowed from submitted/approved/paid
- Expected wrong behaviour: Re-submitting a submitted or approved claim returns 200 (resetting status) instead of 409.
- Why: from the docs
- Confidence: medium

### F35: Resubmit does not update `submitted_at`
- Expected wrong behaviour: After reject then submit, `submitted_at` keeps the first submission time.
- Why: from the docs ("last submission")
- Confidence: low

### F36: Reject comment validation
- Expected wrong behaviour: Reject with no comment, empty string or whitespace-only comment accepted; comment over 500 chars accepted; non-string comment causes 500.
- Why: from the docs
- Confidence: medium

### F37: Approve doesn't clear old review comment
- Expected wrong behaviour: After reject (comment) → resubmit → approve without comment, `review_comment` still holds the old rejection text.
- Why: from the docs ("comment from the last review")
- Confidence: low

### F38: Invalid decision accepted
- Expected wrong behaviour: `decision: "APPROVE"`, `"approved"` or missing decision treated as approve/reject instead of 400.
- Why: from prior knowledge
- Confidence: low

### F39: Repeated pay records a second payment or changes data
- Expected wrong behaviour: Second POST /claims/{id}/pay on a paid claim changes `paid_at`, `payment_reference`, or adds to `amount_paid` (doubles it).
- Why: from the docs (idempotency emphasized)
- Confidence: high

### F40: Pay allowed from wrong status or by wrong role
- Expected wrong behaviour: Paying a submitted claim succeeds; a manager paying gets 200 instead of 403.
- Why: from the docs
- Confidence: medium

### F41: Pay reference not validated
- Expected wrong behaviour: Reference longer than 64 chars or a non-string reference accepted (or 500).
- Why: from the docs
- Confidence: medium

### F42: Pay with no body fails
- Expected wrong behaviour: POST /claims/{id}/pay without body or Content-Type returns 400 invalid_json/invalid_body.
- Why: from the docs (body is optional)
- Confidence: low

### F43: Path ids parsed leniently
- Expected wrong behaviour: `/claims/007`, `/claims/1abc` or `/claims/1.0` resolve to claim 1/7 instead of 404; `/claims/0` or huge numbers return 500.
- Why: from the docs (parseInt behaviour)
- Confidence: medium

### F44: Trailing slash not handled
- Expected wrong behaviour: GET /claims/ returns 404, or /claims/1/ handled inconsistently.
- Why: from the docs
- Confidence: low

### F45: Wrong method returns 404 or lacks Allow header
- Expected wrong behaviour: PUT /claims/1 returns 404 instead of 405, or 405 without `Allow` header.
- Why: from the docs
- Confidence: low

### F46: Malformed bodies cause 500
- Expected wrong behaviour: Invalid JSON, JSON array, `null` body, or body > 1 MB return 500 instead of 400 invalid_json / invalid_body / 413.
- Why: from the docs
- Confidence: medium

### F47: Login with non-string credentials crashes or succeeds
- Expected wrong behaviour: `{"username":"alice","password":123}` or object values give 500; username case-insensitive matching.
- Why: from the docs
- Confidence: low

### F48: Bearer scheme case-sensitive
- Expected wrong behaviour: `Authorization: bearer <token>` returns 401.
- Why: from the docs
- Confidence: low

### F49: Missing Location header on POST /claims
- Expected wrong behaviour: 201 without `Location: /claims/{id}`.
- Why: from the docs
- Confidence: low

### F50: Employee role checks for review
- Expected wrong behaviour: Owner employee posting review on own submitted claim gets 200 or 404 instead of 403.
- Why: from the docs
- Confidence: low

## Questions

## Coverage
All sections: conventions (ids, money, dates, trailing slash, errors), auth, roles/visibility, lifecycle, item rules (dates, amounts, meals limit), objects (timestamps, totals, review/payment fields), and every endpoint (login, list with filters/sort/pagination, create, get, patch, delete, items add/remove, submit, review, pay).
