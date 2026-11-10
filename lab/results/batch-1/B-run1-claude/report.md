# Exploration report

## Charters
1. Explore the booking lifecycle (create, read, full update, partial update, delete, then read again) with JSON payloads and the admin token to discover whether every step does what the docs say and returns the documented status code. Tour: Guidebook.
2. Explore one booking's data across every endpoint and format (JSON, XML, URL-encoded; different Accept and Content-Type pairs) with a single distinctive booking to discover data that changes, disappears or is formatted differently along the way. Tour: FedEx.
3. Explore create, full update and partial update with bad and boundary data (missing or extra fields, wrong types, negative or huge prices, checkout before checkin, invalid dates, very long and non-ASCII names) to discover what the API wrongly accepts and what it rejects badly. Tour: Antisocial.
4. Explore authorization and search with no credentials, wrong tokens, Basic auth versus cookie, unknown ids, and the GET /booking filters to discover who can change what, and whether search follows the docs. Tours: Saboteur and Back alley.

## Findings

### F1: PATCH with a partial `bookingdates` object corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -X PATCH http://localhost:3002/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkin":"2020-01-02"}}'`
- Expected: The docs mark `bookingdates.checkin` and `bookingdates.checkout` as individually optional for PATCH, so only the supplied date should change and the other should keep its value.
- Actual: 200 with `"bookingdates":{"checkin":"2020-01-02","checkout":"0NaN-aN-aN"}`. The corrupted value is saved: a later GET returns it too.
- Reproduced: 2 times (booking 11 with checkout only, where checkin was corrupted; booking 12 with checkin only, where checkout was corrupted), plus a follow-up GET.

### F2: `depositpaid=false` is stored as `true` when sent as XML or URL-encoded
- Severity: high
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking><firstname>Zoë &amp; &lt;Ann&gt;</firstname><lastname>Fedex-Tröger</lastname><totalprice>123.45</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2025-12-31</checkin><checkout>2026-01-02</checkout></bookingdates><additionalneeds>a=b&amp;c=d; late</additionalneeds></booking>'`
- Expected: `depositpaid` should be false. The same data sent as JSON keeps false.
- Actual: 200 with `<depositpaid>true</depositpaid>`, and a later JSON GET of booking 14 returns `"depositpaid":true`.
- Reproduced: 4 times (XML POST for booking 14, URL-encoded POST for booking 15, XML PUT on booking 13, URL-encoded PATCH `depositpaid=false&totalprice=125` on booking 13).

### F3: Prices of 1e21 or more silently collapse to their leading digit
- Severity: high
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Huge","lastname":"Price25","totalprice":7e25,"depositpaid":true,"bookingdates":{"checkin":"2025-01-01","checkout":"2025-01-02"},"additionalneeds":"x"}'`
- Expected: Either store the number or reject it with a 400. It should not save a different value.
- Actual: 200 with `"totalprice":7`. Likewise 1e308 → 1 and 1e21 → 1. Values up to 1e20 are kept, and 2.5e3 → 2500 works.
- Reproduced: 3 times (1e308, 1e21, 7e25).

### F4: Wrong-typed fields are silently coerced instead of rejected (POST and PATCH)
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"Types","totalprice":"abc","depositpaid":"no","bookingdates":{"checkin":"2025-01-01","checkout":"2025-01-02"},"additionalneeds":"x"}'`
- Expected: 400, because the docs type `totalprice` as Number and `depositpaid` as Boolean.
- Actual: 200 with `"totalprice":null,"depositpaid":true`. PATCH `{"totalprice":"free","depositpaid":"nope","firstname":12345}` returned 200 with `"firstname":12345,"totalprice":null,"depositpaid":true`. The number is stored as firstname even though the docs type it as String.
- Reproduced: 2 times (POST for booking 19, PATCH on booking 12).

### F5: Invalid dates are accepted and stored as "0NaN-aN-aN"
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Dates","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2025-13-45","checkout":"not-a-date"},"additionalneeds":"x"}'`
- Expected: 400 for dates that cannot be parsed.
- Actual: 200 with `"checkin":"0NaN-aN-aN","checkout":"0NaN-aN-aN"` (booking 20).
- Reproduced: 1 time directly. The same "0NaN-aN-aN" value also appeared twice through F1.

### F6: Negative prices and checkout-before-checkin are accepted
- Severity: medium
- Request: `curl -X PUT http://localhost:3002/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"firstname":"Neg2","lastname":"Put","totalprice":-1,"depositpaid":false,"bookingdates":{"checkin":"2030-06-01","checkout":"2001-01-01"},"additionalneeds":"x"}'`
- Expected: 400. A booking cannot have a negative total or check out before it checks in.
- Actual: 200, and the values are stored unchanged (`"totalprice":-1`, checkin 2030-06-01, checkout 2001-01-01).
- Reproduced: 2 times (POST for booking 18 with -500 and reversed dates; the PUT above).

### F7: Decimal prices are truncated to integers
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Zoë & <Ann>","lastname":"Fedex-Tröger","totalprice":123.45,"depositpaid":false,"bookingdates":{"checkin":"2025-12-31","checkout":"2026-01-02"},"additionalneeds":"a=b&c=d; late"}'`
- Expected: `totalprice` is documented as Number, so 123.45 should be kept or rejected, not changed.
- Actual: 200 with `"totalprice":123`.
- Reproduced: 3 times (JSON, XML and URL-encoded creates).

### F8: The checkout search filter works backwards (returns checkout <= date)
- Severity: high
- Request: `curl 'http://localhost:3002/booking?lastname=Price&checkout=2025-01-01'`
- Expected: The docs say "Return bookings that have a checkout date greater than or equal to the set checkout date". The "Price" bookings are 18 (checkout 2025-01-01) and 21, 22, 23 (checkout 2025-01-02), so all four should be returned.
- Actual: 200 `[{"bookingid":18}]`. `checkout=2025-01-02` returned 18, 21, 22 and 23, so booking 18 was included even though its checkout is earlier. `checkout=2025-01-03` also returned all four, although every one of their checkouts is earlier than 2025-01-03.
- Reproduced: 3 queries, all consistent with `<=`.

### F9: The checkin search filter excludes the exact date (strict > instead of >=)
- Severity: medium
- Request: `curl 'http://localhost:3002/booking?lastname=Price&checkin=2025-01-10'`
- Expected: Booking 18 (checkin 2025-01-10), because the docs say "greater than or equal to".
- Actual: 200 `[]`. `checkin=2025-01-01` returned only 18 and left out 21, 22 and 23 (checkin 2025-01-01). `checkin=2024-12-31` returned all four.
- Reproduced: 3 queries, all consistent with `>`.

### F10: Accept `application/x-www-form-urlencoded` returns 200 with an internal error message
- Severity: medium
- Request: `curl -i http://localhost:3002/booking/1 -H 'Accept: application/x-www-form-urlencoded'`
- Expected: The docs show a "URL Response" body such as `firstname=Jim&lastname=Brown&...`.
- Actual: `200 OK`, `Content-Type: text/html`, with the body `formurlencoded is not a function`. This leaks an internal error and reports it as a success.
- Reproduced: 2 times (bookings 13 and 1).

### F11: Unsupported Accept returns 418 but the booking is still created
- Severity: medium
- Request: `curl -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: text/plain' -d '{"firstname":"TeapotTwo","lastname":"Fedex","totalprice":10,"depositpaid":false,"bookingdates":{"checkin":"2025-12-31","checkout":"2026-01-02"},"additionalneeds":"x"}'`
- Expected: Either 406 with nothing created, or a successful create in a fallback format. An error status should not come with a side effect.
- Actual: `418 I'm a Teapot`, yet `GET /booking?firstname=TeapotTwo` returns `[{"bookingid":17}]`. The client gets no booking id for a booking that now exists.
- Reproduced: 2 times (Accept text/xml created booking 16; Accept text/plain created booking 17).

### F12: Missing required fields on POST give 500 instead of 400
- Severity: medium
- Request: `curl -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{}'`
- Expected: 400. PUT with missing fields does return `400 Bad Request`, and so does malformed JSON.
- Actual: `500 Internal Server Error`.
- Reproduced: 2 times (`{}` and a body without firstname).

### F13: `Content-Type: application/xml` on POST gives 500
- Severity: medium
- Request: `curl -i -X POST http://localhost:3002/booking -H 'Content-Type: application/xml' -d '<booking><firstname>AppXml2</firstname></booking>'`
- Expected: 415 or 400. `application/xml` is the usual XML media type, and the docs list it for Accept.
- Actual: `500 Internal Server Error`. No booking was created (a search for firstname=AppXml returned `[]`).
- Reproduced: 2 times.

### F14: Invalid date in a search filter gives 500
- Severity: medium
- Request: `curl -i 'http://localhost:3002/booking?checkin=not-a-date'`
- Expected: 400. The docs say "Format must be CCYY-MM-DD".
- Actual: `500 Internal Server Error`.
- Reproduced: 2 times (`checkin=not-a-date`, `checkout=2025-02-30x`).

### F15: XML responses are labelled `Content-Type: text/html`
- Severity: low
- Request: `curl -i http://localhost:3002/booking/13 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`, which is what the client asked for.
- Actual: 200, `Content-Type: text/html; charset=utf-8`, with an XML body.
- Reproduced: 3 times (GET, XML POST, XML PUT).

### F16: Unknown or deleted booking ids return 405 for PUT, PATCH and DELETE
- Severity: low
- Request: `curl -i -X PATCH http://localhost:3002/booking/99999 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=8ce04e6bb40e212' -d '{"firstname":"Ghost"}'`
- Expected: 404 Not Found, which is what GET returns for the same missing id. The method itself is allowed.
- Actual: `405 Method Not Allowed`.
- Reproduced: 3 times (DELETE and PUT on deleted booking 11, PATCH on 99999).

### F17: Failed login returns 200 OK
- Severity: low
- Request: `curl -i -X POST http://localhost:3002/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 for bad credentials. 200 is documented only for success, with a `token` field.
- Actual: `200 OK` with `{"reason":"Bad credentials"}`.
- Reproduced: 2 times.

## Questions
- **Name search is case-sensitive.** `firstname=mixed` and `lastname=price` return `[]`, while `firstname=Mixed` returns `[12]`. The docs example `?firstname=sally&lastname=brown` uses lowercase, which suggests matching should ignore case. The docs never state it, so this is not listed as a finding.
- **Tokens stay valid after a new one is issued.** The first token still worked for PATCH after a second token was created. The docs say nothing about token expiry.
- **A bad Basic header is ignored when the cookie is valid.** A request with an invalid `Authorization: Basic Zm9vOmJhcg==` and a valid cookie succeeded. This may be intended, since the docs call them alternatives.
- **There is no length limit on names.** A 500-character firstname plus a non-ASCII/emoji lastname was accepted (200). I could not send a larger payload (~100 KB) because the shell in this environment blocked it.
- **Extra fields are ignored.** Unknown fields such as `isadmin` and `bookingid` in a POST body were dropped silently. That is probably fine.
- **The 99999999999999999999 price** was stored as 100000000000000000000, which is a precision loss from floating-point numbers.
- **The docs contradict themselves on status codes.** DELETE and ping are documented as "Success 200" but the examples show `201 Created`. The API returns 201. The PATCH examples in the docs use `-X PUT`.

## Coverage
- Explored: the full JSON lifecycle (create, GET, PUT, GET, PATCH, GET, DELETE, GET, repeat DELETE, PUT on a deleted id); auth success and failure; ping; the list endpoint; one distinctive booking (non-ASCII, `&`, `<`, `=`) through JSON, XML and URL-encoded create, PUT and PATCH, plus Accept json/xml/urlencoded/text/xml/text/plain and Content-Type application/xml; missing, empty, wrong-type, negative, huge, exponent, decimal, reversed-date, invalid-date, long and non-ASCII input on POST, PUT and PATCH; malformed JSON; no auth, wrong cookie, empty cookie, wrong Basic, Bearer token, mixed headers, DELETE with Basic, unknown ids without auth, token reuse; search by name, case, checkin and checkout boundaries, invalid dates, unknown parameters.
- Not covered: URL-encoded bodies with nested `bookingdates` on PATCH; XML with bad data (malformed XML, missing fields); very large payloads (100 KB+); non-numeric ids such as `/booking/abc`; concurrent or double-submit behaviour; whether the auth endpoint accepts XML or form bodies.
- Requests used: 77 of 80.
