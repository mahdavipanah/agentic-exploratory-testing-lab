# Exploration report

## Charters
Check that the GET /booking filters (checkin, checkout, name) work as the docs describe.
Check input validation on create (POST), update (PUT) and partial update (PATCH) for JSON, XML and urlencoded bodies.
Check auth on PUT, PATCH and DELETE, and the status codes for missing resources.

## Findings

### F1: `checkout` filter is backwards: it returns bookings with checkout ≤ the date instead of ≥
- Severity: high
- Request: `curl -s 'http://localhost:3004/booking?checkout=2018-06-01'`
- Expected: The docs say "Return bookings that have a checkout date greater than or equal to the set checkout date". Booking 1 (checkout 2025-12-03) and booking 9 (checkout 2021-04-27) should be in the result.
- Actual: 200 `[]`. `?checkout=2030-01-01` returns every booking (1–11), even though no booking has a checkout on or after 2030. `?checkout=2021-01-05` returns bookings 8, 11, 14, 15, 16 and 17 (checkouts on or before that date) and leaves out 1 and 9 (later checkouts).
- Reproduced: 3 times (dates 2019-01-01, 2018-06-01/2030-01-01 and 2021-01-05)

### F2: `checkin` filter leaves out bookings whose checkin equals the filter date (should be ≥)
- Severity: medium
- Request: `curl -s 'http://localhost:3004/booking?checkin=2021-01-01'`
- Expected: The docs say "checkin date greater than or equal to". Booking 17 (checkin 2021-01-01) should be included.
- Actual: 200 `[{"bookingid":2},{"bookingid":3},{"bookingid":4},{"bookingid":5},{"bookingid":7},{"bookingid":10},{"bookingid":14}]`, so 17 is missing. In the same way, `?checkin=2018-01-01` left out booking 11 (checkin 2018-01-01), but `?checkin=2017-12-31` included it. The result also includes booking 14, whose checkin is the invalid value `0NaN-aN-aN`.
- Reproduced: 2 times (bookings 11 and 17)

### F3: PATCH with only one booking date overwrites the other date with `0NaN-aN-aN`
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3004/booking/17 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkout":"2021-01-09"}}'`
- Expected: In a partial update, every field is optional (docs: bookingdates.checkin and bookingdates.checkout are both "Optional: yes"). The checkin date that was not sent (2021-01-01) should stay the same.
- Actual: 200 `"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2021-01-09"}`. Patching only the checkin of booking 15 did the same thing to its checkout (`"checkout":"0NaN-aN-aN"`), and a later GET /booking/15 showed the bad value was saved.
- Reproduced: 2 times (checkin-only on 15, checkout-only on 17)

### F4: Invalid dates are accepted and saved as `0NaN-aN-aN`
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2022-01-01","checkout":"tomorrow"},"additionalneeds":"x"}'`
- Expected: 400. The field is a Date and the docs give the format as CCYY-MM-DD.
- Actual: 200 `{"bookingid":19,...,"checkout":"0NaN-aN-aN"}`. `"checkin":"notadate"` gave the same result (booking 14).
- Reproduced: 2 times

### F5: Non-numeric `totalprice` is accepted and saved as `null`
- Severity: medium
- Request: `curl -s -X PATCH http://localhost:3004/booking/19 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=5330424177a0681' -d '{"totalprice":"lots"}'`
- Expected: 400. totalprice is a Number.
- Actual: 200 `"totalprice":null`. POST with `"totalprice":"abc"` also returned 200 with `"totalprice":null` (booking 14).
- Reproduced: 2 times (POST and PATCH)

### F6: `depositpaid` set to the string "false" (in urlencoded or JSON) is saved as `true`
- Severity: high
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/json' -d 'firstname=Url2&lastname=Enc2&totalprice=5&depositpaid=false&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02&additionalneeds=None'`
- Expected: `depositpaid: false`. The docs show urlencoded as a supported format, and the only way to send a boolean in that format is the text `false`.
- Actual: 200 `"depositpaid":true`. The same happened for booking 16 (urlencoded, checked with a GET), for JSON `"depositpaid":"false"` (booking 17), and for `"depositpaid":"maybe"` (booking 14). Any non-empty string becomes true.
- Reproduced: 3 times

### F7: POST /booking with a required field missing returns 500 Internal Server Error
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"No","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"},"additionalneeds":"x"}'`
- Expected: 400 Bad Request. The fields are required, and PUT with an incomplete body correctly returns 400.
- Actual: `HTTP/1.1 500 Internal Server Error`
- Reproduced: 2 times (missing firstname, missing lastname)

### F8: Bookings with checkout before checkin, or a negative total price, are accepted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg2","lastname":"Rev2","totalprice":-1,"depositpaid":false,"bookingdates":{"checkin":"2022-05-10","checkout":"2022-05-01"},"additionalneeds":"x"}'`
- Expected: 400. A stay cannot end before it starts, and a price cannot be negative.
- Actual: 200 `{"bookingid":18,"booking":{..."totalprice":-1,...,"checkin":"2022-05-10","checkout":"2022-05-01"...}}`
- Reproduced: 2 times (bookings 12/13 and booking 18)

### F9: `Accept: application/x-www-form-urlencoded` returns an internal error message with status 200
- Severity: medium
- Request: `curl -s -i http://localhost:3004/booking/15 -H 'Accept: application/x-www-form-urlencoded'`
- Expected: The booking encoded as urlencoded text. The docs show "URL Response" examples for GET, POST and PUT.
- Actual: `HTTP/1.1 200 OK`, `Content-Type: text/html`, body `formurlencoded is not a function`. This is a server-side exception, and its message is sent back to the client. On POST, the booking is still created (booking 16 exists).
- Reproduced: 2 times (POST /booking and GET /booking/15)

### F10: PUT, PATCH and DELETE on a booking that does not exist return 405 instead of 404
- Severity: low
- Request: `curl -s -i -X PATCH http://localhost:3004/booking/9999 -H 'Content-Type: application/json' -H 'Cookie: token=5330424177a0681' -d '{"firstname":"Ghost"}'`
- Expected: 404 Not Found, the same as GET /booking/9999. The method is allowed on this route.
- Actual: `HTTP/1.1 405 Method Not Allowed`. PUT /booking/9999, DELETE /booking/9999, and DELETE of an already-deleted booking (12) gave the same result.
- Reproduced: 4 times

### F11: Failed login returns 200 OK
- Severity: low
- Request: `curl -s -i -X POST http://localhost:3004/auth -H 'Content-Type: application/json' -d '{"username":"nobody","password":"x"}'`
- Expected: 401 (or 4xx) for wrong credentials. Clients and monitoring cannot tell success from failure by the status code.
- Actual: `HTTP/1.1 200 OK` `{"reason":"Bad credentials"}`. A wrong password and an empty body `{}` gave the same result.
- Reproduced: 3 times

### F12: XML responses are labelled `Content-Type: text/html`
- Severity: low
- Request: `curl -s -i http://localhost:3004/booking/11 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`, matching the Accept header and the content.
- Actual: 200, `Content-Type: text/html; charset=utf-8`, with an XML body (`<?xml version='1.0'?><booking>...`)
- Reproduced: 2 times (GET /booking/11, POST /booking with XML)

## Questions
- Name filters are case-sensitive: `?firstname=mary` returns `[]` and `?firstname=Mary` returns [1,7,8]. The docs example uses lowercase (`firstname=sally&lastname=brown`), which suggests matching should ignore case. I didn't count this as a bug because the docs don't say so directly.
- DELETE returns `201 Created`, and /ping returns `201 Created` with the body "Created". The docs list this under "Success 200" but show 201 in the examples, so the docs contradict themselves. 200 or 204 would be more usual.
- Tokens never seem to expire or get revoked: the first token still worked after a second one was issued. I didn't test expiry over time.
- The docs for the PATCH examples use `curl -X PUT`, which looks like a mistake in the docs.

## Coverage
Explored: /ping; /auth (valid, wrong password, unknown user, empty body); GET /booking with no filter and with firstname, lastname, checkin and checkout filters; GET /booking/:id (existing, missing, non-numeric, with JSON, XML and urlencoded Accept); POST with JSON, XML and urlencoded bodies, missing fields, wrong types, invalid dates, reversed dates, negative price, malformed JSON and malformed XML; PUT and PATCH with no auth, an invalid token, an empty token, wrong Basic auth, a valid cookie and valid Basic auth; PATCH with falsy values (these worked) and with partial bookingdates; DELETE with no auth, cookie, Basic auth, a missing ID and an already-deleted ID.
Not covered: PUT/PATCH with XML or urlencoded bodies, combining several filters with dates, very long strings or injection payloads, concurrency, token expiry over time, and HTTP methods not listed in the docs.
Requests used: 67 of 80.
