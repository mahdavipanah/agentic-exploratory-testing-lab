# Exploration report

## Charters
1. Explore the booking lifecycle (create, read, full update, partial update, delete, then read again) with JSON payloads and the admin token to discover whether every step does what the docs say and returns the documented status code. *Tour: Guidebook.*
2. Explore one booking's data across every endpoint and format (JSON, XML, URL-encoded; different Accept and Content-Type pairs) with a single distinctive booking to discover data that changes, disappears or is formatted differently along the way. *Tour: FedEx.*
3. Explore create, full update and partial update with bad and boundary data (missing or extra fields, wrong types, negative or huge prices, checkout before checkin, invalid dates, very long and non-ASCII names) to discover what the API wrongly accepts and what it rejects badly. *Tour: Antisocial.*
4. Explore authorization and search with no credentials, wrong tokens, Basic auth versus cookie, unknown ids, and the GET /booking filters to discover who can change what, and whether search follows the docs. *Tours: Saboteur and Back alley.*

## Findings

### F1: PATCH with a partial `bookingdates` object corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request:
  `curl -X PATCH http://localhost:3001/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkin":"2020-01-02"}}'`
- Expected: Fields marked optional in the PATCH docs (`bookingdates.checkin` and `bookingdates.checkout` are listed separately as optional), so only checkin should change and checkout should stay 2020-01-05.
- Actual: 200 `{"...","bookingdates":{"checkin":"2020-01-02","checkout":"0NaN-aN-aN"},...}`. A later GET returns the same corrupted value, so the data is lost for good.
- Reproduced: 2 times (booking 11, patching only checkout, which turned checkin into `0NaN-aN-aN`; booking 12, patching only checkin, which turned checkout into `0NaN-aN-aN`)

### F2: `depositpaid: false` is stored as `true` when sent as XML, URL-encoded or as the JSON string "false"
- Severity: high
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking><firstname>Zoë</firstname><lastname>Brien &amp; Co</lastname><totalprice>123.45</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2021-12-31</checkin><checkout>2022-01-02</checkout></bookingdates><additionalneeds>Late check-out</additionalneeds></booking>'`
- Expected: `depositpaid` false, as sent. The docs show `<depositpaid>true</depositpaid>` and `depositpaid=true` as the XML and URL-encoded way to send this Boolean, so "false" should mean false.
- Actual: 200 `<depositpaid>true</depositpaid>`. GET /booking/14 as JSON also shows `"depositpaid":true`.
- Reproduced: 5 times: XML POST (#23), URL-encoded POST `depositpaid=false` (#25), XML PUT on booking 13, which flipped from false to true (#26), XML PATCH (#35), and JSON `"depositpaid":"false"` (#46). JSON PATCH with `"depositpaid":"nope"` was also stored as true.

### F3: Very large `totalprice` values are stored as 1
- Severity: high
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Huge","lastname":"Price","totalprice":1e308,"depositpaid":true,"bookingdates":{"checkin":"2021-01-01","checkout":"2021-01-02"},"additionalneeds":"x"}'`
- Expected: Either store the number as sent, or reject it with 400. Silently changing it is wrong.
- Actual: 200 `"totalprice":1`
- Reproduced: 2 times (1e308 gave 1; 1000000000000000000000 gave 1)

### F4: Decimal `totalprice` values are silently truncated
- Severity: medium
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Zoë","lastname":"Brien & Co","totalprice":123.45,"depositpaid":false,"bookingdates":{"checkin":"2021-12-31","checkout":"2022-01-02"},"additionalneeds":"Late check-out"}'`
- Expected: The docs give totalprice the type Number, so 123.45 should be kept, or the request rejected if only integers are allowed.
- Actual: 200 `"totalprice":123`
- Reproduced: 4 times (JSON 123.45 gave 123; XML 123.45 gave 123; URL-encoded 123.45 gave 123; JSON 99.99 gave 99)

### F5: The documented `Accept: application/x-www-form-urlencoded` returns 200 with an internal error message, but still applies the change
- Severity: medium
- Request:
  `curl -i http://localhost:3001/booking/13 -H 'Accept: application/x-www-form-urlencoded'`
- Expected: A URL-encoded body, as in the docs' "URL Response" examples (`firstname=...&lastname=...`).
- Actual: `200 OK`, `Content-Type: text/html`, body `formurlencoded is not a function` (an internal error leaks out with a success status). With PATCH (`-X PATCH .../booking/15 -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/x-www-form-urlencoded' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d 'firstname=Zoey'`) the same error comes back, yet a GET shows that firstname did change to "Zoey". The client is told nothing useful about whether the write worked.
- Reproduced: 3 times (GET twice, PATCH once)

### F6: The GET /booking `checkout` filter returns bookings with checkout on or before the date, which is the opposite of the docs
- Severity: high
- Request: `curl 'http://localhost:3001/booking?checkout=2000-01-02'`
- Expected: Docs: "Return bookings that have a checkout date greater than or equal to the set checkout date", so almost every booking should come back.
- Actual: 200 `[{"bookingid":12},{"bookingid":22}]`. Booking 22 has checkout 2000-01-01, which is earlier than the filter, and booking 12 has checkout `0NaN-aN-aN`. With `checkout=2022-01-02` the result included bookings 16, 17, 20, 21 and 23 (checkout 2021-01-02) and booking 22 (2000-01-01), and left out most seed bookings.
- Reproduced: 2 times (two different dates, both consistent with `<=`)

### F7: The GET /booking `checkin` filter leaves out bookings whose checkin equals the filter date
- Severity: medium
- Request: `curl 'http://localhost:3001/booking?checkin=2030-01-01'`
- Expected: Docs say "greater than or equal to", so booking 22 (checkin 2030-01-01) should be included.
- Actual: 200 `[{"bookingid":18}]`. Booking 22 is missing, and booking 18, which has checkin `0NaN-aN-aN`, is included.
- Reproduced: 2 times. `checkin=2021-12-31` left out bookings 13, 14 and 15 (checkin exactly 2021-12-31), and `checkin=2021-12-30` included them.

### F8: Invalid dates are accepted and either stored as "0NaN-aN-aN" or silently rolled over
- Severity: medium
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2021-02-30","checkout":"not-a-date"},"additionalneeds":"x"}'`
- Expected: 400, because these fields are of type Date.
- Actual: 200 `"bookingdates":{"checkin":"2021-03-02","checkout":"0NaN-aN-aN"}`. February 30 becomes March 2, and the garbage string becomes `0NaN-aN-aN`. These corrupted records then show up in date searches they shouldn't match (see F6 and F7: bookings 12 and 18).
- Reproduced: 2 times (POST #40; PUT on booking 18 with `"garbage"` and `"2021-13-45"`, where both were stored as `0NaN-aN-aN`)

### F9: POST /booking with missing or wrong-type required fields returns 500 instead of 400
- Severity: medium
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"lastname":"NoFirst","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2021-01-01","checkout":"2021-01-02"},"additionalneeds":"x"}'`
- Expected: 400 Bad Request, as PUT does for a missing field (`PUT {"firstname":"OnlyFirst"}` gives 400) and as malformed JSON does.
- Actual: `500 Internal Server Error`
- Reproduced: 4 times (missing firstname, missing bookingdates, empty `{}` body, numeric `"firstname":42`)

### F10: Wrong-type and empty values are accepted and stored
- Severity: medium
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"Price","totalprice":"abc","depositpaid":true,"bookingdates":{"checkin":"2021-01-01","checkout":"2021-01-02"},"additionalneeds":"x"}'`
- Expected: 400, because totalprice is a Number and is required.
- Actual: 200 `"totalprice":null`. PATCH `{"totalprice":"lots","depositpaid":"nope","firstname":""}` on booking 17 also returned 200 and stored `"firstname":""`, `"totalprice":null` and `"depositpaid":true`.
- Reproduced: 2 times (POST and PATCH)

### F11: A checkout date before the checkin date is accepted
- Severity: medium
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Back","lastname":"Wards","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2022-05-10","checkout":"2022-05-01"},"additionalneeds":"x"}'`
- Expected: 400. A stay can't end before it starts.
- Actual: 200, stored as sent.
- Reproduced: 2 times (POST; PATCH on booking 22 with checkin 2030-01-01 and checkout 2000-01-01)

### F12: A negative `totalprice` is accepted
- Severity: low
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg","lastname":"Price","totalprice":-500,"depositpaid":true,"bookingdates":{"checkin":"2021-01-01","checkout":"2021-01-02"},"additionalneeds":"x"}'`
- Expected: 400. A booking price shouldn't be negative.
- Actual: 200 `"totalprice":-500`
- Reproduced: 2 times (POST -500; PUT -1 on booking 18)

### F13: PUT, PATCH and DELETE on a missing booking id return 405 Method Not Allowed instead of 404
- Severity: low
- Request: `curl -X DELETE http://localhost:3001/booking/99999 -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='`
- Expected: 404 Not Found, which is what GET returns for the same id. The method is allowed on this route.
- Actual: `405 Method Not Allowed`
- Reproduced: 6 times (DELETE on deleted id 11, PUT and PATCH on 11, DELETE and PUT on 99999, DELETE on `abc`)

### F14: `Content-Type: application/xml` request bodies cause a 500
- Severity: medium
- Request:
  `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/xml' -H 'Accept: application/json' -d '<booking><firstname>Ann</firstname></booking>'`
- Expected: Either accept it the way `text/xml` is accepted, or reject it with 415 or 400. A standard XML media type shouldn't crash the server.
- Actual: `500 Internal Server Error`
- Reproduced: 2 times (full and partial XML body)

### F15: Invalid dates in the search filters cause a 500
- Severity: medium
- Request: `curl 'http://localhost:3001/booking?checkin=not-a-date'`
- Expected: 400. The docs say "Format must be CCYY-MM-DD", so a bad value is a client error.
- Actual: `500 Internal Server Error`
- Reproduced: 2 times (`checkin=not-a-date`, `checkout=garbage`)

### F16: XML responses are labelled `Content-Type: text/html`
- Severity: low
- Request: `curl -i http://localhost:3001/booking/13 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`, since the client asked for that.
- Actual: 200 `Content-Type: text/html; charset=utf-8` with an XML body.
- Reproduced: 3 times (GET, XML POST and URL-encoded Accept responses all had text/html)

## Questions
- POST /auth with the wrong password returns `200 OK` with `{"reason":"Bad credentials"}` instead of 401. I saw this only once, so it is unconfirmed.
- A POST with an empty `Content-Type` header gave 500 (seen once). I'm not sure whether a missing Content-Type should give 400 or 415.
- `Accept: text/plain` gives `418 I'm a Teapot` (seen once). 406 Not Acceptable would be the standard answer.
- DELETE returns `201 Created` with body "Created", and /ping also returns 201. Both match the docs, but they look wrong: 200 or 204 would be expected. The docs' "Success 200" header disagrees with their own 201 example.
- The PATCH examples in the docs all use `curl -X PUT`, so they are wrong for PATCH.
- The docs say Content-Type can be "application/json or text/xml", but they also give URL-encoded examples, which do work for requests. URL-encoded responses don't work (F5).
- Unknown extra fields (`"isAdmin":true`) are silently dropped. That seems fine, but the docs don't say what should happen.
- Name search is case-sensitive (`firstname=str` returns [], `firstname=Str` returns 16 and 22), but the docs' example uses lowercase `firstname=sally&lastname=brown`. If the seed data is "Sally Brown", that example would return nothing.
- Tokens: I never saw a token expire, and I didn't test token reuse over time.

## Coverage
- Charter 1 (requests 1–19): auth, create, GET, PUT, PATCH, DELETE, GET after delete, repeated DELETE/PUT/PATCH on a deleted id, ping, list. Cookie and Basic auth both worked for writes.
- Charter 2 (requests 20–35): one booking with non-ASCII and `&` characters through JSON, XML and URL-encoded in both directions (Content-Type and Accept). Round-tripped correctly: non-ASCII names, `&` escaping in XML, and search by "Zoë". Problems are in F2, F4, F5, F14 and F16.
- Charter 3 (requests 36–55): missing fields, wrong types, empty body, extra field, negative, decimal and huge prices, inverted and invalid dates, emoji/CJK names (round-tripped fine), malformed JSON and XML (both correctly 400), missing Content-Type. **Not tested:** very long names. The sandbox blocked generating a large payload in the shell.
- Charter 4 (requests 56–79): no credentials, wrong cookie, empty cookie, Bearer token, wrong Basic password, wrong-case Basic username (all correctly 403 for PUT, PATCH and DELETE), bad /auth login, unknown and non-numeric ids, name filters (exact, combined, case), checkin and checkout filters including boundaries, invalid filter dates.
- Not explored: token expiry or invalidation, concurrency and double-submit, XML entity tricks (XXE), very long strings, `additionalneeds` omitted on its own, query parameter injection.
- Requests used: 79 of 80.
