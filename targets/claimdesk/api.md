# Claimdesk API documentation

Claimdesk is a small service for team expense claims. Employees collect their expenses (train tickets, hotel nights, meals, equipment) into a claim and submit it. A manager of their team approves or rejects it, and finance pays approved claims.

Base URL: http://localhost:3001 (see your run instructions for the actual port)

All data is kept in memory. Every start of the server resets it to the same seed data: the six users below and ten sample claims in every status.

## Contents

- [Conventions](#conventions)
- [Authentication and seed users](#authentication-and-seed-users)
- [Roles and visibility](#roles-and-visibility)
- [Claim lifecycle](#claim-lifecycle)
- [Rules for items](#rules-for-items)
- [Objects](#objects)
- [Endpoints](#endpoints)

## Conventions

- **Requests.** Send request bodies as JSON objects with `Content-Type: application/json`. Bodies are limited to 1 MB.
- **Responses.** Every response except `204 No Content` has a JSON body and `Content-Type: application/json; charset=utf-8`.
- **Ids.** Claim and item ids are positive integers. In a path, an id that is not a positive integer (for example `abc`, `0` or `007`) is treated as not found.
- **Money.** Amounts and totals are JSON numbers in the claim's currency, with at most two decimal places, for example `89.9` or `251.4`. Each claim has one currency (`EUR`, `USD` or `GBP`), and all its items are in that currency.
- **Dates.** An item's `date` is a calendar date in `YYYY-MM-DD` format. Timestamps such as `created_at` are ISO 8601 in UTC with milliseconds, for example `2026-10-08T09:12:00.000Z`. "Today" always means the current date in UTC.
- **Trailing slash.** `/claims/` is the same as `/claims`.

### Errors

Errors have this shape:

```json
{ "error": "validation_failed", "message": "amount must not exceed 10000.00", "field": "amount" }
```

`field` is present only for validation errors. For items sent inside `POST /claims`, it includes the position, for example `items[1].date`.

| Status | `error` | When |
| --- | --- | --- |
| 400 | `validation_failed` | A field or query parameter is missing or invalid |
| 400 | `invalid_json` | The body is not valid JSON |
| 400 | `invalid_body` | The body is valid JSON but not an object (for example an array) |
| 400 | `invalid_url` | The request URL cannot be parsed |
| 401 | `unauthorized` | The bearer token is missing or unknown |
| 401 | `invalid_credentials` | Login with a wrong username or password |
| 403 | `forbidden` | You can see the claim, but your role or ownership does not allow this action |
| 404 | `not_found` | No such route, claim or item, or a claim you are not allowed to see |
| 405 | `method_not_allowed` | The path exists but not with this method; the `Allow` header lists the methods |
| 409 | `invalid_state` | The claim's status does not allow this action |
| 413 | `payload_too_large` | The body is larger than 1 MB |
| 500 | `internal_error` | Unexpected server error |

## Authentication and seed users

Log in with `POST /auth/login` to get a token, then send it on every request except `GET /ping` and `POST /auth/login`:

```
Authorization: Bearer <token>
```

The scheme name is case-insensitive (`bearer` works too). Tokens stay valid until the server restarts. Each login issues a new token; earlier tokens keep working.

| Username | Password | Role | Team |
| --- | --- | --- | --- |
| `alice` | `alice-pass` | employee | platform |
| `bob` | `bob-pass` | employee | platform |
| `erin` | `erin-pass` | employee | mobile |
| `carol` | `carol-pass` | manager | platform |
| `frank` | `frank-pass` | manager | mobile |
| `dave` | `dave-pass` | finance | (none) |

The examples below store tokens in shell variables:

```bash
B=http://localhost:3001
TOKEN=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"alice-pass"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
```

## Roles and visibility

| Role | Can see | Can do |
| --- | --- | --- |
| employee | Their own claims, in every status | Create claims; edit, delete, submit their own claims |
| manager | Claims of employees in their own team, except drafts | Approve or reject submitted claims of employees in their team |
| finance | All claims except drafts | Pay approved claims |

- Only employees create claims. Managers and finance get `403` from `POST /claims`.
- Only the owner of a claim can change it, delete it, change its items or submit it.
- A claim you are not allowed to see behaves as if it did not exist: every endpoint returns `404` for it, including the list (it is never included).
- If you can see a claim but the action is not yours (for example finance trying to approve, or a manager trying to edit), the response is `403`.

## Claim lifecycle

```
draft ──submit──▶ submitted ──approve──▶ approved ──pay──▶ paid
                      │
                      └──reject──▶ rejected ──submit──▶ submitted
```

| Action | Who | Allowed from | Result |
| --- | --- | --- | --- |
| Create | employee | | `draft` |
| Edit fields, add or remove items | owner | `draft`, `rejected` | status unchanged |
| Delete | owner | `draft` | claim and its items are removed |
| Submit | owner | `draft`, `rejected` | `submitted`; the claim must have at least one item |
| Approve | manager of the owner's team | `submitted` | `approved` |
| Reject | manager of the owner's team | `submitted` | `rejected`; a comment is required |
| Pay | finance | `approved` | `paid`; one payment of the claim total is recorded |

Paying a claim that is already paid is safe: it returns `200` with the claim and records nothing new. Any other action from a status not listed returns `409 invalid_state`.

## Rules for items

An item is one expense. These rules are checked whenever an item is added, either in `POST /claims` or with `POST /claims/{id}/items`. Seed data is not re-checked.

| Field | Type | Rules |
| --- | --- | --- |
| `date` | string | Required. A real calendar date in `YYYY-MM-DD` format. Not in the future, and at most 90 days before today. If today is 2026-11-10, the earliest accepted date is 2026-08-12 and the latest is 2026-11-10. |
| `category` | string | Required. One of `travel`, `meals`, `lodging`, `equipment`, `other`. |
| `description` | string | Required. 1 to 200 characters after trimming surrounding whitespace. |
| `amount` | number | Required. Greater than 0 and at most 10000.00, with at most two decimal places. Strings such as `"12.50"` are rejected. |

**Meals limit.** Within one claim, the `meals` items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected with `400`.

## Objects

### Claim

Returned by `POST /claims`, `GET /claims/{id}`, `PATCH /claims/{id}` and the submit, review and pay actions.

| Field | Type | Description |
| --- | --- | --- |
| `id` | integer | Claim id |
| `title` | string | 1 to 120 characters |
| `purpose` | string or null | Optional business purpose, up to 500 characters |
| `owner` | string | Username of the employee who created the claim |
| `team` | string | The owner's team |
| `currency` | string | `EUR`, `USD` or `GBP` |
| `status` | string | `draft`, `submitted`, `approved`, `rejected` or `paid` |
| `items` | array of Item | In the order they were added |
| `total` | number | Sum of the item amounts |
| `created_at` | string | Timestamp |
| `updated_at` | string | Timestamp of the last successful write to the claim: a PATCH, an item added or removed, or a status change |
| `submitted_at` | string or null | Timestamp of the last submission |
| `reviewed_by` | string or null | Username of the manager who last reviewed it |
| `reviewed_at` | string or null | Timestamp of the last review |
| `review_comment` | string or null | Comment from the last review |
| `paid_at` | string or null | Timestamp of the payment |
| `amount_paid` | number or null | Amount paid; `null` until the claim is paid |
| `payment_reference` | string or null | Reference given by finance when paying |

Example:

```json
{
  "id": 1,
  "title": "Berlin offsite travel",
  "purpose": "Platform team offsite, 6-7 October",
  "owner": "alice",
  "team": "platform",
  "currency": "EUR",
  "status": "approved",
  "items": [
    { "id": 1, "claim_id": 1, "date": "2026-10-06", "category": "travel", "description": "ICE train Hamburg to Berlin", "amount": 89.9 },
    { "id": 2, "claim_id": 1, "date": "2026-10-06", "category": "lodging", "description": "Hotel, 1 night", "amount": 119 },
    { "id": 3, "claim_id": 1, "date": "2026-10-07", "category": "meals", "description": "Dinner", "amount": 42.5 }
  ],
  "total": 251.4,
  "created_at": "2026-10-08T09:12:00.000Z",
  "updated_at": "2026-10-09T14:03:00.000Z",
  "submitted_at": "2026-10-08T09:20:00.000Z",
  "reviewed_by": "carol",
  "reviewed_at": "2026-10-09T14:03:00.000Z",
  "review_comment": null,
  "paid_at": null,
  "amount_paid": null,
  "payment_reference": null
}
```

### Claim summary

Returned in lists by `GET /claims`.

| Field | Type | Description |
| --- | --- | --- |
| `id` | integer | Claim id |
| `title` | string | |
| `owner` | string | Owner's username |
| `team` | string | Owner's team |
| `currency` | string | |
| `status` | string | |
| `total` | number | Sum of the item amounts |
| `created_at` | string | Timestamp |
| `submitted_at` | string or null | Timestamp |

### Item

| Field | Type | Description |
| --- | --- | --- |
| `id` | integer | Item id (unique across all claims) |
| `claim_id` | integer | The claim the item belongs to |
| `date` | string | `YYYY-MM-DD` |
| `category` | string | `travel`, `meals`, `lodging`, `equipment` or `other` |
| `description` | string | |
| `amount` | number | In the claim's currency |

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/ping` | Health check |
| POST | `/auth/login` | Log in and get a token |
| GET | `/claims` | List and search claims you can see |
| POST | `/claims` | Create a draft claim |
| GET | `/claims/{id}` | Get one claim with its items |
| PATCH | `/claims/{id}` | Change a claim's title, purpose or currency |
| DELETE | `/claims/{id}` | Delete a draft claim |
| POST | `/claims/{id}/items` | Add an item |
| DELETE | `/claims/{id}/items/{itemId}` | Remove an item |
| POST | `/claims/{id}/submit` | Submit a claim for review |
| POST | `/claims/{id}/review` | Approve or reject a submitted claim |
| POST | `/claims/{id}/pay` | Pay an approved claim |

### GET /ping

Health check. No authentication.

| Status | Body |
| --- | --- |
| 200 | `{"status":"ok"}` |

```bash
curl -s "$B/ping"
```

### POST /auth/login

No authentication.

Body:

| Field | Type | Required |
| --- | --- | --- |
| `username` | string | yes |
| `password` | string | yes |

| Status | When |
| --- | --- |
| 200 | `{"token": "<token>", "user": {"id": 1, "username": "alice", "name": "Alice Novak", "role": "employee", "team": "platform"}}` |
| 400 | Body missing, not an object, or `username`/`password` not strings |
| 401 | `invalid_credentials`: unknown username or wrong password |

```bash
curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"carol","password":"carol-pass"}'
```

### GET /claims

Lists the claims you can see (see [Roles and visibility](#roles-and-visibility)), as claim summaries.

Query parameters, all optional:

| Parameter | Description |
| --- | --- |
| `status` | One of `draft`, `submitted`, `approved`, `rejected`, `paid`. Any other value returns `400`. |
| `owner` | Username. Narrows the list to that user's claims, among the claims you can see. An unknown username gives an empty list. |
| `q` | Case-insensitive text search. A claim matches if its title or any of its item descriptions contains the text. |
| `sort` | `created_at`, `-created_at`, `total` or `-total`. A leading `-` means descending. Default `-created_at` (newest first). Ties are ordered by id, ascending. Any other value returns `400`. |
| `page` | Page number, a positive integer. Default 1. A page past the end returns `200` with an empty `data` array. |
| `per_page` | Claims per page, 1 to 50. Default 20. |

Response `200`:

```json
{
  "data": [
    { "id": 9, "title": "Taxi to airport", "owner": "alice", "team": "platform", "currency": "EUR",
      "status": "submitted", "total": 37.8, "created_at": "2026-11-04T07:30:00.000Z", "submitted_at": "2026-11-04T07:31:00.000Z" }
  ],
  "meta": { "page": 1, "per_page": 1, "total_count": 4, "next_page": 2 }
}
```

`meta.total_count` counts all matching claims across pages. `meta.next_page` is the number of the next page that has results, or `null` on the last page.

| Status | When |
| --- | --- |
| 200 | List returned |
| 400 | Invalid `status`, `sort`, `page` or `per_page` |
| 401 | Missing or unknown token |

```bash
curl -s "$B/claims?status=submitted&sort=-total&per_page=5" -H "Authorization: Bearer $TOKEN"
curl -s "$B/claims?q=taxi" -H "Authorization: Bearer $TOKEN"
```

### POST /claims

Creates a claim in `draft` status. Employees only. Fields not listed below are ignored.

Body:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `title` | string | yes | 1 to 120 characters after trimming |
| `purpose` | string or null | no | Up to 500 characters; empty becomes `null` |
| `currency` | string | yes | `EUR`, `USD` or `GBP` (upper case) |
| `items` | array | no | Items to add right away, each following the [rules for items](#rules-for-items). If any item is invalid, nothing is created. |

| Status | When |
| --- | --- |
| 201 | Created. Body: the claim. `Location: /claims/{id}` |
| 400 | Validation failed |
| 401 | Missing or unknown token |
| 403 | You are not an employee |

```bash
curl -s -i -X POST "$B/claims" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Hamburg meetup","currency":"EUR","items":[
        {"date":"2026-11-05","category":"travel","description":"Regional train","amount":12.5},
        {"date":"2026-11-05","category":"meals","description":"Lunch","amount":15.75}]}'
```

### GET /claims/{id}

Returns the claim with its items.

| Status | When |
| --- | --- |
| 200 | Body: the claim |
| 401 | Missing or unknown token |
| 404 | No such claim, or you are not allowed to see it |

```bash
curl -s "$B/claims/1" -H "Authorization: Bearer $TOKEN"
```

### PATCH /claims/{id}

Partial update by the owner, while the claim is `draft` or `rejected`. Send any of the fields below; fields you leave out keep their values. Only these fields can be changed: any other field in the body, such as `status`, `owner` or `total`, is ignored. An empty object is accepted and returns `200`.

| Field | Type | Rules |
| --- | --- | --- |
| `title` | string | 1 to 120 characters after trimming; cannot be `null` |
| `purpose` | string or null | Up to 500 characters; `null` or empty clears it |
| `currency` | string | `EUR`, `USD` or `GBP`. Amounts are not converted. |

| Status | When |
| --- | --- |
| 200 | Body: the updated claim |
| 400 | Validation failed |
| 401 | Missing or unknown token |
| 403 | You can see the claim but are not its owner |
| 404 | No such claim, or you are not allowed to see it |
| 409 | The claim is not `draft` or `rejected` |

```bash
curl -s -X PATCH "$B/claims/4" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Office chair and footrest","purpose":null}'
```

### DELETE /claims/{id}

Deletes a `draft` claim and its items. Owner only.

| Status | When |
| --- | --- |
| 204 | Deleted, no body |
| 401 | Missing or unknown token |
| 403 | You can see the claim but are not its owner |
| 404 | No such claim, or you are not allowed to see it |
| 409 | The claim is not a draft |

```bash
curl -s -i -X DELETE "$B/claims/4" -H "Authorization: Bearer $TOKEN"
```

### POST /claims/{id}/items

Adds one item to a claim. Owner only, while the claim is `draft` or `rejected`. The body is one item: `date`, `category`, `description`, `amount` (see [rules for items](#rules-for-items)).

| Status | When |
| --- | --- |
| 201 | Body: the new item |
| 400 | Validation failed |
| 401 | Missing or unknown token |
| 403 | You can see the claim but are not its owner |
| 404 | No such claim, or you are not allowed to see it |
| 409 | The claim is not `draft` or `rejected` |

```bash
curl -s -X POST "$B/claims/4/items" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"date":"2026-11-02","category":"equipment","description":"Footrest","amount":34.5}'
```

### DELETE /claims/{id}/items/{itemId}

Removes an item from a claim. Owner only, while the claim is `draft` or `rejected`. The item must belong to the claim in the path.

| Status | When |
| --- | --- |
| 204 | Removed, no body |
| 401 | Missing or unknown token |
| 403 | You can see the claim but are not its owner |
| 404 | No such claim (or you are not allowed to see it), or no such item in this claim |
| 409 | The claim is not `draft` or `rejected` |

```bash
curl -s -i -X DELETE "$B/claims/4/items/8" -H "Authorization: Bearer $TOKEN"
```

### POST /claims/{id}/submit

Submits a claim for review. Owner only. Allowed from `draft` and from `rejected` (a rejected claim can be edited first, then submitted again). No body. Sets `status` to `submitted` and `submitted_at` to now.

| Status | When |
| --- | --- |
| 200 | Body: the submitted claim |
| 400 | The claim has no items (`field`: `items`) |
| 401 | Missing or unknown token |
| 403 | You can see the claim but are not its owner |
| 404 | No such claim, or you are not allowed to see it |
| 409 | The claim is not `draft` or `rejected` |

```bash
curl -s -X POST "$B/claims/4/submit" -H "Authorization: Bearer $TOKEN"
```

### POST /claims/{id}/review

Approves or rejects a `submitted` claim. Only a manager of the claim owner's team can review it.

Body:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `decision` | string | yes | `approve` or `reject` |
| `comment` | string | for `reject` | Up to 500 characters. Optional when approving. |

Sets `status` to `approved` or `rejected`, and `reviewed_by`, `reviewed_at` and `review_comment`.

| Status | When |
| --- | --- |
| 200 | Body: the reviewed claim |
| 400 | Invalid `decision` or `comment`, or a rejection without a comment |
| 401 | Missing or unknown token |
| 403 | You can see the claim but may not review it (for example you are finance, or the employee who owns it) |
| 404 | No such claim, or you are not allowed to see it |
| 409 | The claim is not `submitted` |

```bash
CAROL=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"carol","password":"carol-pass"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
curl -s -X POST "$B/claims/3/review" -H "Authorization: Bearer $CAROL" -H 'Content-Type: application/json' \
  -d '{"decision":"reject","comment":"Please attach the taxi receipt"}'
```

### POST /claims/{id}/pay

Pays an `approved` claim. Finance only. Records one payment of the claim total: `status` becomes `paid`, `amount_paid` equals `total`, and `paid_at` is set to now.

Body (optional):

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `reference` | string | no | Bank transfer reference, up to 64 characters |

If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing.

| Status | When |
| --- | --- |
| 200 | Body: the paid claim |
| 400 | Invalid `reference` |
| 401 | Missing or unknown token |
| 403 | You can see the claim but are not finance |
| 404 | No such claim, or you are not allowed to see it |
| 409 | The claim is neither `approved` nor `paid` |

```bash
DAVE=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"dave","password":"dave-pass"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
curl -s -X POST "$B/claims/8/pay" -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' \
  -d '{"reference":"PAY-2026-1110-01"}'
```
