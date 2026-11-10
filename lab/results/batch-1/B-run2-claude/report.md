# Exploration report

## Charters
1. Explore the booking lifecycle (create, read, full update, partial update, delete, then read again) with JSON payloads and the admin token to discover whether every step does what the docs say and returns the documented status code. Tour: Guidebook.
2. Explore one booking's data across every endpoint and format (JSON, XML, URL-encoded; different Accept and Content-Type pairs) with a single distinctive booking to discover data that changes, disappears or is formatted differently along the way. Tour: FedEx.
3. Explore create, full update and partial update with bad and boundary data (missing or extra fields, wrong types, negative or huge prices, checkout before checkin, invalid dates, very long and non-ASCII names) to discover what the API wrongly accepts and what it rejects badly. Tour: Antisocial.
4. Explore authorization and search with no credentials, wrong tokens, Basic auth versus cookie, unknown ids, and the GET /booking filters to discover who can change what, and whether search follows the docs. Tours: Saboteur and Back alley.

## Findings

### F1: PATCH with a partial `bookingdates` object corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -X PATCH http://localhost:3002/booking/11 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=5d3c0c5bec57c97' -d '{"bookingdates":{"checkout":"2019-03-03"}}'`
- Expected: The docs list `bookingdates.checkin` and `bookingdates.checkout` as separately optional for PATCH, so the date you leave out should stay as it was (2018-02-01).
- Actual: 200 with `"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2019-03-03"}`. The corrupted value is saved and comes back on later GETs.
- Reproduced: 2 (patching only `checkout` broke `checkin`; patching only `checkin` then broke `checkout`)

### F2: `depositpaid=false` sent as XML or URL-encoded is stored as `true`
- Severity: high
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking><firstname>Xena</firstname><lastname>Fedex</lastname><totalprice>50</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2025-01-01</checkin><checkout>2025-01-05</checkout></bookingdates><additionalneeds>None</additionalneeds></booking>'`
- Expected: `depositpaid` is false, as sent.
- Actual: 200 with `<depositpaid>true</depositpaid>`. JSON `"depositpaid":"no"` is also stored as `true`. The string looks to be checked for truthiness instead of being parsed.
- Reproduced: 3 (XML PUT on booking 12, URL-encoded PUT on booking 12, XML POST that created booking 13), plus the JSON "no" case on booking 21

### F3: Decimal and large prices are silently changed (123.45→123, 1e308→1, 2e21→2, 5e25→5)
- Severity: high
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Big","lastname":"Price","totalprice":2e21,"depositpaid":true,"bookingdates":{"checkin":"2025-06-01","checkout":"2025-06-02"}}'`
- Expected: `totalprice` is a Number. The API should store it unchanged or reject it, not quietly change the amount.
- Actual: 200 with `"totalprice":2`. Also 1e308→1 (POST), 5e25→5 (PUT), 123.45→123 (POST JSON) and 99.99→99 (PATCH XML). This looks like parseInt applied to the number's string form.
- Reproduced: 3 for huge values, 2 for decimals

### F4: Accept `application/x-www-form-urlencoded` returns "formurlencoded is not a function", yet the booking is still created
- Severity: high
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/x-www-form-urlencoded' -d '{"firstname":"Ghost","lastname":"Booking","totalprice":7,"depositpaid":true,"bookingdates":{"checkin":"2025-06-01","checkout":"2025-06-02"}}'`
- Expected: A URL-encoded body, as in the docs' "URL Response" example, or a clean error that creates nothing.
- Actual: 200 `text/html`, body `formurlencoded is not a function`, which is an internal error leaking out. The booking is still saved (`GET /booking?firstname=Ghost` → `[{"bookingid":25}]`), but the client never gets its id. GET /booking/12 with this Accept header fails the same way.
- Reproduced: 3 (GET 12; POST that created booking 14, confirmed with GET 14; POST that created booking 25)

### F5: Search by checkin date is strictly greater-than, not greater-than-or-equal
- Severity: medium
- Request: `curl 'http://localhost:3002/booking?checkin=2030-01-01'`
- Expected: Docs say "checkin date greater than or equal to the set checkin date", so booking 13 (checkin 2030-01-01) should be returned.
- Actual: 200 `[]`. Also `?checkin=2025-06-01` left out bookings 17–22, whose checkin is exactly 2025-06-01.
- Reproduced: 2

### F6: Search by checkout date is reversed (returns checkouts on or before the date)
- Severity: medium
- Request: `curl 'http://localhost:3002/booking?checkout=2026-01-01'`
- Expected: Docs say "checkout date greater than or equal to the set checkout date". So booking 12 (checkout 2026-01-02) should be returned and booking 14 (checkout 2018-01-02) should not.
- Actual: 200. The list includes 13 (checkout 2020-01-01), 14 (2018-01-02) and 15 (2025-06-01), and leaves out 12. `?checkout=2025-06-02` showed the same pattern.
- Reproduced: 2

### F7: POST with missing fields or a non-string firstname returns 500 instead of 400
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{}'`
- Expected: 400 Bad Request. All fields are required, and PUT with missing fields already returns 400.
- Actual: 500 `Internal Server Error`. Same for a missing `lastname` and for `"firstname":123`.
- Reproduced: 4

### F8: Invalid dates are accepted and silently changed
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2025-02-30","checkout":"not-a-date"}}'`
- Expected: 400 for dates that are not valid CCYY-MM-DD.
- Actual: 200. `checkin` became `2025-03-02` and `checkout` became `0NaN-aN-aN`. Empty-string dates also became `0NaN-aN-aN` (booking 23).
- Reproduced: 2

### F9: Checkout before checkin and negative prices are accepted
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg","lastname":"Price","totalprice":-500,"depositpaid":true,"bookingdates":{"checkin":"2025-06-10","checkout":"2025-06-01"},"additionalneeds":"x"}'`
- Expected: Rejected. A stay can't end before it starts, and a negative total price makes no sense.
- Actual: 200 with booking 15 saved as sent. A PUT with checkin 2030-01-01 and checkout 2020-01-01 was also accepted, and PATCH accepted `totalprice:-1`.
- Reproduced: 3

### F10: Wrong types are accepted and saved (non-numeric price → null, numeric names via PATCH)
- Severity: medium
- Request: `curl -X PATCH http://localhost:3002/booking/21 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=5d3c0c5bec57c97' -d '{"lastname":99}'`
- Expected: 400. `lastname` is a String and `totalprice` is a Number.
- Actual: 200 with `"lastname":99`. A GET confirmed `"firstname":42` was saved on booking 13. A POST with `"totalprice":"abc"` or `"xyz"` saved `"totalprice":null` (bookings 19 and 24). Validation is also inconsistent: POST returns 500 for a numeric firstname, but PATCH accepts it.
- Reproduced: 2 for numeric names via PATCH, 2 for string prices

### F11: Empty first and last names are accepted
- Severity: low
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"","lastname":"","totalprice":0,"depositpaid":false,"bookingdates":{"checkin":"","checkout":""}}'`
- Expected: Rejected. The fields are required ("Optional: no").
- Actual: 200 (booking 23). Also POST booking 24 and PATCH `"firstname":""` on booking 13.
- Reproduced: 3

### F12: PUT does not replace the whole booking; an omitted `additionalneeds` keeps its old value
- Severity: low
- Request: `curl -X PUT http://localhost:3002/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"firstname":"Zoë","lastname":"Brien & Co","totalprice":123,"depositpaid":false,"bookingdates":{"checkin":"2025-12-31","checkout":"2026-01-02"}}'`
- Expected: A full update either requires every field (docs say "Optional: no", and other missing fields give 400) or clears the ones left out.
- Actual: 200 with `"additionalneeds":"Late"` kept from before. Booking 13 kept "None" the same way.
- Reproduced: 2

### F13: XML responses are sent with `Content-Type: text/html`
- Severity: low
- Request: `curl -i http://localhost:3002/booking/12 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`, since that is what the client asked for.
- Actual: 200 `Content-Type: text/html; charset=utf-8` with an XML body. Same for XML responses to PUT and POST.
- Reproduced: 3

### F14: POST /auth with bad credentials returns 200
- Severity: low
- Request: `curl -X POST http://localhost:3002/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 (or another 4xx) for a failed login.
- Actual: 200 `{"reason":"Bad credentials"}`
- Reproduced: 2

### F15: Changing or deleting a booking that doesn't exist returns 405 instead of 404
- Severity: low
- Request: `curl -X PATCH http://localhost:3002/booking/999999 -H 'Content-Type: application/json' -H 'Cookie: token=5d3c0c5bec57c97' -d '{"firstname":"X"}'`
- Expected: 404 Not Found, which is what GET returns for the same ids.
- Actual: 405 `Method Not Allowed`. Same for PUT on deleted booking 11, DELETE on deleted booking 11 and DELETE /booking/abc.
- Reproduced: 4

### F16: A malformed date in a search filter causes a 500
- Severity: low
- Request: `curl 'http://localhost:3002/booking?checkin=garbage'`
- Expected: 400. Docs say "Format must be CCYY-MM-DD".
- Actual: 500 `Internal Server Error`. Same for `?checkout=bad`.
- Reproduced: 2

## Questions
- Name search is case-sensitive (`?firstname=jim&lastname=brown` → `[]`, `Jim/Brown` → `[{"bookingid":14}]`; `zoë` vs `Zoë` behaves the same way). The docs example uses lowercase `sally`/`brown` while the data is `Sally Brown`, which suggests case-insensitive search was intended. The docs don't say.
- `Accept: text/plain` on GET returns `418 I'm a Teapot`. Docs say Accept "Can be application/json or application/xml". A 406 would be more conventional. Seen once.
- The docs' PATCH examples use `curl -X PUT`, and the docs say DELETE "Success 200" but show 201 Created (the API returns 201 "Created"; /ping also returns 201). These are documentation errors.
- `Content-Type` is documented as "application/json or text/xml", but the docs' own examples use `application/x-www-form-urlencoded`, which works for PUT.
- Extra fields (`isAdmin`, `bookingid`) on POST are silently dropped. That is probably fine, but it isn't documented.
- XML output escapes `<` as `&lt;` but leaves `>` alone (`Late &lt;checkout>`). That is valid XML, just noted.

## Coverage
- Charter 1 (requests 1–19): auth, create, GET, PUT, PATCH (flat and nested), DELETE, GET after delete, repeated DELETE, PUT/PATCH on missing ids, ping, bad login.
- Charter 2 (20–34): one distinctive booking (non-ASCII, `&`, `<`, decimal price) read as JSON/XML/URL-encoded/text/plain/`*/*`; updated via XML and URL-encoded PUT; created via XML POST; PATCH via XML; looked up through search.
- Charter 3 (35–53): missing, extra, empty and wrong-type fields; negative, huge and decimal prices; reversed and invalid dates; non-ASCII names; malformed JSON; PUT with missing fields; PATCH with wrong types.
- Charter 4 (54–73): no credentials, wrong cookie, empty token, token prefix, wrong Basic, non-base64 Basic, Bearer token; GET/DELETE on non-numeric ids; name and date filters including boundaries and malformed dates. Authorization held up: every attempt without valid credentials got 403.
- Reproductions (74–78).
- Not covered: very long names (I couldn't generate a large payload in this sandbox), whether tokens expire, concurrent/double submits, combined name+date filters, XML that is malformed or has extra elements, PATCH via URL-encoded body, and whether a valid cookie plus a wrong Basic header (or the reverse) is accepted.
- Requests used: 78 of 80.
