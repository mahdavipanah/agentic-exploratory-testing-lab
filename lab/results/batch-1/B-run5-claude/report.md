# Exploration report

## Charters
1. Explore the booking lifecycle (create, read, full update, partial update, delete, then read again) with JSON payloads and the admin token to discover whether every step does what the docs say and returns the documented status code. (Tour: Guidebook)
2. Explore one booking's data across every endpoint and format (JSON, XML, URL-encoded; different Accept and Content-Type pairs) with a single distinctive booking to discover data that changes, disappears or is formatted differently along the way. (Tour: FedEx)
3. Explore create, full update and partial update with bad and boundary data (missing or extra fields, wrong types, negative or huge prices, checkout before checkin, invalid dates, very long and non-ASCII names) to discover what the API wrongly accepts and what it rejects badly. (Tour: Antisocial)
4. Explore authorization and search with no credentials, wrong tokens, Basic auth versus cookie, unknown ids, and the GET /booking filters to discover who can change what, and whether search follows the docs. (Tours: Saboteur and Back alley)

## Findings

### F1: PATCH with only one booking date corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -X PATCH http://localhost:3002/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkout":"2020-02-02"}}'`
- Expected: Docs say every PATCH field is optional, including `bookingdates.checkin` and `bookingdates.checkout` on their own. The date that was not sent should stay the same (it was `2020-01-01`).
- Actual: 200 `{"...","bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2020-02-02"},...}`. The bad value is saved (a later GET returns it).
- Reproduced: 2 times (booking 11 patching only checkin, where checkout became `0NaN-aN-aN`; booking 12 patching only checkout, where checkin became `0NaN-aN-aN`).

### F2: depositpaid=false is saved as true (XML, URL-encoded and JSON string "false")
- Severity: high
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking><firstname>Zoë &amp; X</firstname><lastname>Xml</lastname><totalprice>123.45</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2024-02-29</checkin><checkout>2024-03-01</checkout></bookingdates><additionalneeds>a=b&amp;c</additionalneeds></booking>'`
- Expected: `depositpaid` should be `false`, because the client sent false.
- Actual: 200 with `<depositpaid>true</depositpaid>`. GET /booking/14 also returns `"depositpaid":true`.
- Reproduced: 5 times: XML POST (#14), URL-encoded POST `depositpaid=false` (#15), XML PUT (#13), URL-encoded PATCH (#13), JSON POST with `"depositpaid":"false"` (#23). A JSON boolean `false` is kept correctly.

### F3: Decimal totalprice is cut to a whole number
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Zoë & <Ann>","lastname":"Brien=x;1","totalprice":123.45,"depositpaid":false,"bookingdates":{"checkin":"2024-02-29","checkout":"2024-03-01"},"additionalneeds":"a=b&c"}'`
- Expected: Docs give `totalprice` the type Number, so 123.45 should be kept, or the request should be rejected.
- Actual: 200 `"totalprice":123`
- Reproduced: 3 times (JSON #13, XML #14, URL-encoded #15).

### F4: Very large totalprice is saved as 1
- Severity: high
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Huge2","lastname":"Price","totalprice":1e21,"depositpaid":true,"bookingdates":{"checkin":"2024-01-01","checkout":"2024-01-02"},"additionalneeds":"x"}'`
- Expected: Keep the value or reject it with 400. It should never become a different, valid-looking price.
- Actual: 200 `"totalprice":1`
- Reproduced: 2 times (`1e308` became 1 for #19, `1e21` became 1 for #22).

### F5: Non-numeric totalprice is accepted and saved as null
- Severity: medium
- Request: `curl -X PUT http://localhost:3002/booking/16 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"firstname":"Put","lastname":"StrPrice","totalprice":"ten","depositpaid":true,"bookingdates":{"checkin":"2024-01-01","checkout":"2024-01-02"},"additionalneeds":"x"}'`
- Expected: 400. `totalprice` is a required Number.
- Actual: 200 `"totalprice":null`
- Reproduced: 2 times (POST with `"abc"` gave #17; PUT with `"ten"` on #16).

### F6: Invalid dates are accepted and saved as "0NaN-aN-aN", or silently rolled over
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2024-13-45","checkout":"not-a-date"},"additionalneeds":"x"}'`
- Expected: 400. The fields have the type Date.
- Actual: 200 `"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"0NaN-aN-aN"}`. A PATCH with `{"bookingdates":{"checkin":"2024-02-31","checkout":"yesterday"}}` returned 200 with `checkin:"2024-03-02"` (rolled over) and `checkout:"0NaN-aN-aN"`.
- Reproduced: 2 times (POST #21, PATCH #16).

### F7: Negative price and checkout before checkin are accepted
- Severity: medium
- Request: `curl -X PUT http://localhost:3002/booking/18 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"firstname":"Neg","lastname":"Rev","totalprice":-99999,"depositpaid":true,"bookingdates":{"checkin":"2025-12-31","checkout":"2025-01-01"},"additionalneeds":"x"}'`
- Expected: 400. A booking with a negative total or a checkout before checkin is not valid (reasoning; the docs say nothing about this).
- Actual: 200, saved as sent.
- Reproduced: negative price 3 times (POST #18 with -500, PATCH #16 with -1, PUT #18 with -99999). Reversed dates 2 times (POST #20, PUT #18).

### F8: POST /booking with missing required fields returns 500 instead of 400
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{}'`
- Expected: 400 Bad Request. PUT with a missing field does return `400 Bad Request`, and malformed JSON returns 400.
- Actual: `500 Internal Server Error`
- Reproduced: 3 times (missing firstname, missing bookingdates, empty object).

### F9: Accept: application/x-www-form-urlencoded returns an internal error text with status 200
- Severity: medium
- Request: `curl -X PUT http://localhost:3002/booking/15 -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/x-www-form-urlencoded' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d 'firstname=Jim&lastname=Brown&totalprice=111&depositpaid=true&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02&additionalneeds=x'` (this is the documented URL-encoded example)
- Expected: A URL-encoded body, as in the docs' "URL Response" examples.
- Actual: `200`, `Content-Type: text/html`, body `formurlencoded is not a function`. The update was still applied (a GET of #15 showed the new data), so the client gets an error message for a change that succeeded.
- Reproduced: 2 times (GET /booking/13, PUT /booking/15).

### F10: XML responses are sent with Content-Type text/html
- Severity: low
- Request: `curl -i http://localhost:3002/booking/13 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`, because the client asked for that.
- Actual: 200, `Content-Type: text/html; charset=utf-8`, with an XML body.
- Reproduced: 3 times (GET, POST and PUT with Accept application/xml).

### F11: PUT, PATCH and DELETE on a missing booking return 405 instead of 404
- Severity: medium
- Request: `curl -X DELETE http://localhost:3002/booking/999999 -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='`
- Expected: 404 Not Found. GET on the same ids returns 404, and the methods are clearly allowed on this route.
- Actual: `405 Method Not Allowed`
- Reproduced: 4 times (DELETE, PUT and PATCH on deleted #11; DELETE on #999999).

### F12: POST /auth with bad credentials returns 200
- Severity: medium
- Request: `curl -X POST http://localhost:3002/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 (or 4xx). The docs list only 200 as the success response, with a `token`.
- Actual: `200 {"reason":"Bad credentials"}`
- Reproduced: 3 times (wrong password, empty body, wrong username).

### F13: The checkout search filter works backwards (returns earlier checkouts)
- Severity: high
- Request: `curl 'http://localhost:3002/booking?checkout=2030-01-01'`
- Expected: Docs say "Return bookings that have a checkout date greater than or equal to the set checkout date". No booking checks out on or after 2030, so the result should be empty or nearly empty.
- Actual: 200 with 21 of 23 ids. `checkout=2025-01-01` returned #1 (checkout 2021-12-06), #12 (2020-01-05), #15 (2018-01-02), all earlier than the date given.
- Reproduced: 3 times (2025-01-01, 2030-01-01, 01/01/2024).

### F14: The checkin search filter leaves out bookings on the exact date
- Severity: medium
- Request: `curl 'http://localhost:3002/booking?checkin=2025-12-31'`
- Expected: Docs say "greater than or equal to", so #18 (checkin 2025-12-31) should be included.
- Actual: `200 []`. With `checkin=2024-05-01`, #13 (checkin 2024-05-01) was also left out, while later bookings were returned.
- Reproduced: 2 times.

### F15: An invalid date in a search filter returns 500
- Severity: medium
- Request: `curl 'http://localhost:3002/booking?checkin=notadate'`
- Expected: 400. Docs say "Format must be CCYY-MM-DD".
- Actual: `500 Internal Server Error`. Note that `checkout=01/01/2024` was not rejected and was parsed loosely.
- Reproduced: 2 times (`banana`, `notadate`).

### F16: POST with an unsupported Content-Type returns 500
- Severity: low
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: text/plain' -H 'Accept: application/json' -d '{"firstname":"Plain"}'`
- Expected: 415 Unsupported Media Type, or 400.
- Actual: `500 Internal Server Error`
- Reproduced: 2 times.

## Questions
- **Wrong field types:** a PATCH with `"firstname":12345` was saved and returned as a JSON number. I saw this only once, so it is not confirmed.
- **PUT that leaves out a field:** a PUT without `additionalneeds` (documented as required) returned 200 and kept the old value. Is PUT a merge rather than a full replace? Seen once; the old value matched what I would have sent, so it is not clear.
- **Search is case-sensitive:** `firstname=jim` returns nothing, `firstname=Jim` finds #15. The docs example uses lowercase `firstname=sally&lastname=brown`, which suggests case-insensitive search is intended.
- **Filters and corrupt dates:** `checkin=2024-05-01` returned #21, whose checkin is `0NaN-aN-aN`. Corrupt dates seem to match filters in unexpected ways.
- **DELETE returns `201 Created`:** this is as documented, but the wrong semantics (the docs table even calls it "Success 200"). /ping also returns 201.
- **No length limit:** a firstname of about 560 characters with CJK and emoji was accepted and returned unchanged. That is fine for encoding, but there seems to be no limit at all.
- **`Accept: text/plain`** returns `418 I'm a Teapot`. 406 would be expected.
- **Docs errors:** the PATCH examples use `curl -X PUT`. The Content-Type header row lists only JSON and XML, but URL-encoded examples are given. Bearer tokens are not accepted (403), which matches the docs since only Cookie and Basic are documented.
- **Extra fields:** extra fields (`isAdmin`, `bookingid`) were silently dropped. That looks harmless, but the client gets no warning.

## Coverage
- **Charter 1 (requests 1–20):** auth, create, get, PUT with cookie, PATCH, nested PATCH, delete, get after delete, double delete, PUT/PATCH on a deleted id, ping, Basic-auth PUT/PATCH.
- **Charter 2 (21–35):** one distinctive booking (`&`, `<`, `ë`, `=`, `;`, decimal price, leap day) through JSON, XML and URL-encoded create, GET with Accept xml / urlencoded / none / text/plain, PUT with XML, PATCH with URL-encoded, and search by the special-character name. The name and additionalneeds were escaped and returned correctly in every format.
- **Charter 3 (36–53):** missing, extra and wrong-type fields, negative and huge prices, reversed and invalid dates, a long non-ASCII name, malformed JSON, and an empty object, across POST, PUT and PATCH.
- **Charter 4 (54–80):** no credentials, a wrong cookie, wrong Basic, a Bearer token, /auth failures, unknown and non-numeric ids, name and date filters, malformed filter dates, and an unsupported Content-Type.
- **Not covered:**
  - token expiry or reuse after logout
  - DELETE with a cookie versus Basic on someone else's booking (there is only one user)
  - XML injection or entity payloads
  - very large bodies (over 1 MB)
  - concurrent or double-submit (obsessive-compulsive tour)
  - combined checkin+checkout filters
  - PATCH with XML
- **Requests used:** 80 of 80.
