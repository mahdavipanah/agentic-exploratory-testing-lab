# Exploration report

## Charters

Risks (written after reading the docs and before any request other than `GET /ping`, ranked by how much they would hurt a client):
- R1 Auth on PUT/PATCH/DELETE might be bypassable (bad, expired or empty token; wrong Basic credentials; auth on the wrong method). High impact: anyone could change or delete bookings.
- R2 POST /booking validation: missing, wrong-type, negative or huge fields, or checkout before checkin, might be accepted or might crash the server (500). This corrupts data.
- R3 Data round-trip: a booking created in JSON might not come back the same through GET, PUT, PATCH, XML or the filters (type coercion, shifted dates, dropped fields).
- R4 Status codes might not match the docs (DELETE and ping are documented as "Success 200" but the examples show 201; 404 vs 405 for missing ids).
- R5 GET /booking filters (name case, the ">=" date rule, malformed dates) might return the wrong subset.
- R6 Repeated or double actions (DELETE twice, PATCH after delete, reusing a token) might behave inconsistently.

Charters:
1. Explore PUT/PATCH/DELETE auth with missing, malformed, wrong and valid tokens and Basic headers (Saboteur tour) to discover whether bookings can be changed without valid credentials. Budget: 20 requests.
2. Explore POST /booking and PUT with missing, wrong-type, negative, empty and inconsistent fields (Antisocial tour) to discover what invalid data is accepted or crashes the server. Budget: 20 requests.
3. Explore one booking's journey through create → GET (JSON/XML/form) → filters → PATCH → PUT → DELETE (FedEx tour) to discover whether data arrives unchanged and whether the filters follow the documented rules. Budget: 20 requests.
4. Explore the documented examples and status codes, plus repeated and double actions (Guidebook + Obsessive-compulsive tour), to discover where actual behaviour differs from the docs. Budget: 15 requests.
(5 requests reserved for reproduction. No new charter was added. Content-negotiation problems found in charter 3 were explored within charters 3 and 4.)

## Findings

### F1: `depositpaid` given as the string "false" is stored as `true` (JSON, XML and form bodies)
- Severity: high
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"T","lastname":"Dep","totalprice":10,"depositpaid":"false","bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"},"additionalneeds":"Breakfast"}'`
- Expected: Either reject the value because it is not a Boolean (400), or read it as `false`. The documented XML and form examples can only send strings, so `<depositpaid>false</depositpaid>` must mean false.
- Actual: 200, `"depositpaid":true` (booking 16; GET /booking/16 also returns true). XML POST with `<depositpaid>false</depositpaid>` gave `<depositpaid>true</depositpaid>` (booking 21). Form POST with `depositpaid=false` gave `"depositpaid":true` (booking 22). PUT with `"depositpaid":"false"` on booking 11 also stored true. The only "false" value that worked was the JSON number `0`.
- Reproduced: 4 times (JSON POST, PUT, XML POST, form POST)

### F2: `checkout` filter on GET /booking works in reverse (returns checkout <= date instead of >=)
- Severity: high
- Request: `curl -s 'http://localhost:3004/booking?checkout=2031-01-04'`
- Expected: Docs: "Return bookings that have a checkout date greater than or equal to the set checkout date." Booking 21 (checkout 2031-01-05) should be included, and bookings that check out in 2019 should not.
- Actual: 200. Returns ids 1–14, 16–20 (all older checkouts) and leaves out 21. The same happened with `checkout=2030-05-01`: booking 20 (checkout 2030-05-20) was left out and every older booking was included. `checkout=2030-05-20` and `checkout=2030-06-01` both included booking 20.
- Reproduced: 4 times

### F3: `checkin` filter leaves out bookings whose check-in equals the filter date
- Severity: medium
- Request: `curl -s 'http://localhost:3004/booking?checkin=2031-01-01'`
- Expected: Docs say "greater than or equal to". Booking 21 has checkin 2031-01-01 and should be returned.
- Actual: 200 `[]`. Similarly, `checkin=2030-05-10` → `[]` for booking 20 (checkin 2030-05-10), while `checkin=2030-05-01` → `[{"bookingid":20}]`. The comparison is strictly greater-than.
- Reproduced: 2 times

### F4: PATCH with a partial `bookingdates` object corrupts the other date
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3004/booking/21 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkout":"2031-01-09"}}'`
- Expected: Docs list `bookingdates.checkin` and `bookingdates.checkout` as separately optional for PATCH, so the checkin that was not sent should stay the same (2031-01-01).
- Actual: 200, `"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2031-01-09"}`. The corrupted value is saved (a later GET /booking/20 showed the same for booking 20).
- Reproduced: 2 times (bookings 20 and 21)

### F5: `totalprice` is silently changed: decimals cut off, junk strings turned into numbers or null
- Severity: high
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"T","lastname":"Float","totalprice":99.99,"depositpaid":false,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"},"additionalneeds":"x"}'`
- Expected: `totalprice` is documented as a Number, so 99.99 should be stored as 99.99. Non-numeric strings should be rejected with 400.
- Actual: 200, `"totalprice":99`. PUT with 250.75 → `250`. `"totalprice":"abc"` → `null` (POST, booking 12; PATCH, booking 21). `"totalprice":"12abc"` → `12`.
- Reproduced: 5 times

### F6: Invalid dates are accepted and silently rewritten
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"R","lastname":"Repro","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2018-02-30","checkout":"notadate"},"additionalneeds":"x"}'`
- Expected: 400 for dates that do not exist or cannot be parsed.
- Actual: 200, `"checkin":"2018-03-02","checkout":"0NaN-aN-aN"`. The booking is saved (GET /booking/15 shows the same values). Bookings with a NaN checkout then disappear from checkout-filter results.
- Reproduced: 2 times (bookings 15 and 23)

### F7: Missing or wrong-type required fields on POST cause 500 (PUT returns 400 for the same thing)
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"lastname":"Brown","totalprice":111,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"},"additionalneeds":"Breakfast"}'`
- Expected: 400 Bad Request, the same as PUT returns for a missing firstname.
- Actual: `500 Internal Server Error`. Missing `bookingdates` → 500, and `"firstname":123` → 500. PUT /booking/11 without firstname → `400 Bad Request`.
- Reproduced: 4 times

### F8: Negative prices and checkout-before-checkin are accepted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"R","lastname":"NegRev","totalprice":-1,"depositpaid":true,"bookingdates":{"checkin":"2025-06-10","checkout":"2025-06-01"},"additionalneeds":"x"}'`
- Expected: 400. A booking cannot end before it starts, and a negative total price makes no sense for a booking.
- Actual: 200, booking 24 created with `"totalprice":-1` and checkout before checkin.
- Reproduced: 2 times (bookings 13/14 and 24)

### F9: `Accept: application/x-www-form-urlencoded` returns an internal error message with status 200
- Severity: medium
- Request: `curl -s -i -H 'Accept: application/x-www-form-urlencoded' http://localhost:3004/booking/1`
- Expected: Docs show a "URL Response" format (`firstname=Jim&lastname=Brown&...`) for GET/POST/PUT/PATCH.
- Actual: `200`, body `formurlencoded is not a function`. This exposes an internal JavaScript error and reports it as success.
- Reproduced: 2 times

### F10: Malformed date in a GET /booking filter causes 500
- Severity: low
- Request: `curl -s 'http://localhost:3004/booking?checkout=2020-13-45'`
- Expected: 400. Docs: "Format must be CCYY-MM-DD".
- Actual: `500 Internal Server Error` (also for `checkin=garbage`).
- Reproduced: 2 times

### F11: POST /booking without a Content-Type causes 500
- Severity: low
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type:' -H 'Accept: application/json' -d '{"firstname":"No","lastname":"CT","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"}}'`
- Expected: 400 or 415 Unsupported Media Type.
- Actual: `500 Internal Server Error`
- Reproduced: 2 times

### F12: POST /auth with bad credentials returns 200
- Severity: low
- Request: `curl -s -i -X POST http://localhost:3004/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 (or 4xx) so clients can tell failure from success by the status code.
- Actual: `200 OK`, `{"reason":"Bad credentials"}`. The same for an empty body, `ADMIN`, an array password and an unknown user.
- Reproduced: 5 times

### F13: PUT/PATCH/DELETE on an id that does not exist returns 405 instead of 404
- Severity: low
- Request: `curl -s -X DELETE http://localhost:3004/booking/99999 -H 'Cookie: token=d5c06e84f907bd8'`
- Expected: 404 Not Found, which is what GET returns for the same id. 405 means the method is not supported on this resource at all.
- Actual: `405 Method Not Allowed` (PUT 99999, DELETE 99999, DELETE of an already-deleted id, PATCH of a deleted id).
- Reproduced: 4 times

### F14: An Accept header the server does not support returns 418 "I'm a Teapot"
- Severity: low
- Request: `curl -s -i -H 'Accept: text/html' http://localhost:3004/booking/1`
- Expected: 406 Not Acceptable, or fall back to JSON.
- Actual: `418 I'm a Teapot`. An empty Accept header gives the same result.
- Reproduced: 2 times

## Questions
- Name filters are case-sensitive: `?firstname=zelda` → `[]`, while `?firstname=Zelda` → `[20]`. The docs example uses `firstname=sally&lastname=brown` against the "Sally Brown" sample, which suggests matching should ignore case. The docs never say this explicitly, so I am not reporting it as a finding.
- DELETE returns `201 Created`. The docs' "Success 200" heading disagrees with the 201 example, and 201 is semantically wrong for a delete, but the docs are contradictory. The same applies to `/ping`.
- POST without `additionalneeds` is accepted (booking 19), although the docs mark it "Optional: no". The docs may simply be wrong.
- Extra fields (`isAdmin`, `bookingid`) were silently dropped, which looks fine. I did not check whether `bookingid` in the body can ever overwrite an id.
- XML output escapes `<` and `&` but not `>`. That is valid XML, but I did not test XML injection on input.
- Tokens do not seem to expire or be replaced: the first token still worked after a second one was issued. I could not test a time-based expiry.

## Coverage
- Explored: auth negatives on PUT/PATCH/DELETE (missing, wrong, empty and prefix tokens; wrong or empty Basic credentials; Bearer). No bypass found; all returned 403. Also: /auth edge cases; POST validation (missing fields, wrong types, negative and decimal prices, bad dates, reversed dates, malformed JSON, no Content-Type, extra fields); JSON/XML/form create and read; Accept negotiation; name and date filters; PATCH with nested partial objects; PUT coercion; delete, double delete, PATCH after delete; GET on non-numeric and deleted ids.
- Not covered: very large payloads and long strings; XML injection or malformed XML; concurrent updates; PUT/PATCH responses in XML/form; combining name and date filters; query-parameter injection; token expiry over time.
- Requests used: 76 of 80.
