# Exploration report

## Charters
- Exercise every documented endpoint (/ping, /auth, GET/POST/PUT/PATCH/DELETE /booking, GET /booking search) against the docs and look for behaviour that contradicts them.
- Probe input validation on CreateBooking/UpdateBooking (missing fields, wrong types, bad dates, negative values).
- Probe auth handling on the protected PUT/PATCH/DELETE endpoints.
- Probe content-type handling (JSON vs XML vs urlencoded) and the search/date-filter query parameters.

## Findings

### F1: POST /booking returns 500 when any required field is missing
- Severity: high
- Request:
  ```
  curl -i -X POST http://localhost:3001/booking \
    -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -d '{"lastname":"Brown","totalprice":111,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"},"additionalneeds":"Breakfast"}'
  ```
- Expected: The docs mark firstname, lastname, totalprice, depositpaid and bookingdates as required ("Optional: no"). A request missing a required field should be rejected with a client error (400 Bad Request), not a server crash.
- Actual: `HTTP/1.1 500 Internal Server Error`, body `Internal Server Error`. Same 500 occurs when `totalprice` is omitted and when `bookingdates` is omitted. An unvalidated missing field reaches server code and throws.
- Reproduced: 4 times (missing firstname twice; missing totalprice; missing bookingdates).

### F2: depositpaid is always stored as true when sent via XML or urlencoded
- Severity: medium
- Request:
  ```
  curl -X POST http://localhost:3001/booking \
    -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/json' \
    -d 'firstname=Dp&lastname=False&totalprice=10&depositpaid=false&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02'
  ```
- Expected: depositpaid is a documented Boolean; sending `false` should store `false`, as it does for JSON.
- Actual: `200 OK` with `"depositpaid":true`. Same bug via XML (`<depositpaid>false</depositpaid>` -> stored `true`, booking 20). Control via JSON `{"depositpaid":false}` correctly stores `false` (booking 21). The string "false" from non-JSON bodies is coerced truthy, so depositpaid can never be false unless the client uses JSON — silent data corruption of a documented field.
- Reproduced: 2 times urlencoded, 1 time XML, plus JSON control.

### F3: PATCH of one nested booking date destroys the other date
- Severity: medium
- Request (on a freshly created booking id 22 whose dates were 2024-01-01 / 2024-12-31):
  ```
  curl -X PATCH http://localhost:3001/booking/22 \
    -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -H 'Cookie: token=<valid-token>' \
    -d '{"bookingdates":{"checkin":"2024-06-01"}}'
  ```
- Expected: PATCH "Updates a current booking with a partial payload" and all body fields are documented optional, so patching only `bookingdates.checkin` should leave `checkout` unchanged (2024-12-31).
- Actual: `200 OK` with `"bookingdates":{"checkin":"2024-06-01","checkout":"0NaN-aN-aN"}`. The nested object is replaced wholesale and the absent checkout is coerced into the invalid date string `0NaN-aN-aN`. The booking is left with a corrupt checkout.
- Reproduced: 2 times (booking 11 and fresh booking 22).

### F4: Invalid date strings are accepted and stored as "0NaN-aN-aN"
- Severity: medium
- Request:
  ```
  curl -X POST http://localhost:3001/booking \
    -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -d '{"firstname":"Bad","lastname":"Date","totalprice":100,"depositpaid":false,"bookingdates":{"checkin":"notadate","checkout":"2020-13-45"},"additionalneeds":"none"}'
  ```
- Expected: checkin/checkout are documented as Date (filter format "CCYY-MM-DD"). Garbage like "notadate" or an impossible date like "2020-13-45" should be rejected with a client error.
- Actual: `200 OK`; the booking is created (id 14) and both dates are stored as `"0NaN-aN-aN"`. No validation; the corrupt value is persisted and returned on later GETs.
- Reproduced: 2 times (creation + later GET of booking 14; the same `0NaN-aN-aN` artifact also appears via F3).

### F5: checkin date filter is exclusive, contradicting the docs (and inconsistent with checkout)
- Severity: medium
- Request (booking 15 has checkin exactly 2021-01-01):
  ```
  curl -i 'http://localhost:3001/booking?checkin=2021-01-01'
  ```
- Expected: Docs say checkin returns bookings "that have a checkin date greater than or equal to the set checkin date", so booking 15 (checkin = 2021-01-01) must be included.
- Actual: booking 15 is NOT in the result for `checkin=2021-01-01`, but IS included for `checkin=2020-12-31`. So the checkin filter is strictly greater-than (off-by-one vs the docs). The checkout filter, by contrast, IS inclusive: `checkout=2021-01-05` includes booking 15 (checkout = 2021-01-05). The two bounds behave inconsistently and checkin disagrees with its documentation.
- Reproduced: 2 times each boundary.

### F6: totalprice sent as a non-numeric string is silently stored as null
- Severity: low
- Request:
  ```
  curl -X POST http://localhost:3001/booking \
    -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -d '{"firstname":"Price","lastname":"Str","totalprice":"abc","depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"},"additionalneeds":"x"}'
  ```
- Expected: totalprice is a documented Number; a non-numeric value should be rejected with a client error.
- Actual: `200 OK` with `"totalprice":null`. The bad input is swallowed and a null is stored for a documented non-optional Number field.
- Reproduced: 2 times (bookings 12 and 23).

### F7: PUT/PATCH/DELETE on a non-existent booking return 405 instead of 404
- Severity: low
- Request:
  ```
  curl -i -X PUT http://localhost:3001/booking/99999 \
    -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -H 'Cookie: token=<valid-token>' \
    -d '{"firstname":"Ghost","lastname":"Booking","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"},"additionalneeds":"x"}'
  ```
- Expected: Updating/deleting a booking that does not exist should be 404 Not Found (GET /booking/99999 correctly returns 404).
- Actual: `HTTP/1.1 405 Method Not Allowed`. Same for `PATCH /booking/99999` and for `DELETE` of an already-deleted booking (id 12). 405 misrepresents the cause (the resource is absent, the method is valid for the route).
- Reproduced: 3 times (PUT 99999, PATCH 99999, second DELETE of 12).

### F8: /ping health check returns 201 Created instead of 200 OK
- Severity: low
- Request:
  ```
  curl -i http://localhost:3001/ping
  ```
- Expected: A health check is documented under "Success 200"; the normal success status is 200 OK.
- Actual: `HTTP/1.1 201 Created`, body `Created`. (The docs are self-contradictory here — the table says 200 but the example block shows `201 Created` — so at minimum the contract is ambiguous; 201 for an idempotent GET health check is wrong regardless. DELETE /booking also returns 201 for a plain delete.)
- Reproduced: 2 times.

### F9: POST /auth with bad credentials returns HTTP 200
- Severity: low
- Request:
  ```
  curl -i -X POST http://localhost:3001/auth \
    -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"wrong"}'
  ```
- Expected: A failed authentication should return a 4xx status (401 Unauthorized / 403), so clients can detect failure from the status line.
- Actual: `HTTP/1.1 200 OK` with body `{"reason":"Bad credentials"}` and no token. Success status for a failed auth; clients must parse the body to notice failure.
- Reproduced: 1 time.

## Questions
- Bookings with the corrupt date `0NaN-aN-aN` (e.g. booking 14) appear in BOTH the checkin and checkout date-range filters for every query I tried. It looks like an invalid/unparseable date always passes the date filter, but I did not exhaustively confirm this is independent of the query value — flagging as suspected only.
- The DELETE /booking success is documented as "Default HTTP 201 response" and indeed returns 201 Created; using 201 for a deletion is unusual (204/200 would be conventional) but it matches the (odd) documented contract, so I did not score it as a defect.
- Docs defect (not an API behaviour): every curl example in the PATCH /booking/:id section uses `-X PUT`, which looks like a copy-paste error from the PUT section. The live endpoint does accept PATCH (verified), so this is a documentation issue only.
- I did not probe for auth-token expiry/lifetime, concurrency, very large payloads, or malformed-JSON bodies, and I avoided injection-style payloads.

## Coverage
Explored: /ping; POST /auth (valid + bad credentials); GET /booking (all ids + firstname/lastname search incl. case sensitivity + checkin/checkout date filters and their boundaries); GET /booking/:id (JSON, XML, unsupported Accept -> 418, non-existent id, non-numeric id); POST /booking (JSON, XML, urlencoded; missing required fields; wrong types; invalid/garbage dates; reversed dates; negative price; markup/escaping in XML output); PUT /booking/:id (no auth -> 403, invalid token -> 403, wrong basic auth -> 403, valid cookie token, valid basic auth, XML); PATCH /booking/:id (single field, nested partial); DELETE /booking/:id (valid, repeat/already-deleted, auth).
Not reached: token expiry/lifetime, malformed-JSON body handling, concurrency/race conditions, oversized payloads, and injection-class inputs.
Requests used: 62 of the 80 budget.

---

Note on process (from the agent's hand-back): one earlier HTTP attempt was stopped by a safety classifier (a malformed curl line that also carried an injection-shaped auth payload); the agent abandoned that approach and continued with standard black-box tests. That attempt is counted in the 62.
