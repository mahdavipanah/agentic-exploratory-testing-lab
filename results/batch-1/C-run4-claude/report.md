# Exploration report

## Charters

Risks (ranked by client impact), written before any request except GET /ping:
- R1 Auth on PUT/PATCH/DELETE: bad/missing/expired token or wrong Basic creds still allowed to mutate; /auth accepting bad creds or returning 200 with an error body.
- R2 Input validation on POST/PUT: missing fields, wrong types, negative price, checkout before checkin, malformed JSON accepted or producing 500s; stored data differs from what was sent.
- R3 Data integrity across endpoints/formats: POST response vs GET (JSON/XML/urlencoded), PATCH clobbering untouched fields, search filters (checkin/checkout ">=" semantics) returning wrong ids.
- R4 Lifecycle/idempotency: double DELETE, PUT/PATCH/GET on deleted or non-existent ids, non-numeric ids, wrong status codes.

Charters:
- C1: Explore PUT/PATCH/DELETE and POST /auth with missing, wrong and malformed credentials (cookie and Basic) to discover whether unauthorised clients can mutate bookings. Tour: Saboteur. Budget: 20 requests (used 18).
- C2: Explore POST /booking and PUT /booking/:id with missing, wrong-type, empty, negative and malformed bodies to discover validation gaps and server errors. Tour: Antisocial. Budget: 22 requests (used 15).
- C3: Explore one booking's lifecycle (create -> get JSON/XML -> patch -> search -> delete) in JSON, XML and urlencoded to discover data that changes or is lost between endpoints and formats. Tour: FedEx. Budget: 22 requests (used 15).
- C4: Explore DELETE, GET, PUT on deleted/non-existent/odd ids and repeated submissions to discover wrong status codes and non-idempotent behaviour. Tour: Obsessive-compulsive / Back alley. Budget: 14 requests (used 10, the rest went to reproductions and a few Saboteur header checks).

No new charter was added. The id-parsing issue (F1) came up during C4 and I followed it inside that charter.

## Findings

### F1: Malformed booking ids are truncated to a numeric prefix, so DELETE removes the wrong booking
- Severity: high
- Request: `curl -s -i -X DELETE http://localhost:3003/booking/14abc -H 'Cookie: token=<valid token>'`
- Expected: 404 (or 400) for an id that is not a number. The docs type the id as Number.
- Actual: `201 Created`, and a later `GET /booking/14` returned `404 Not Found`, so booking 14 had been deleted. `DELETE /booking/12.5` with Basic auth also returned 201 and deleted booking 12. `GET /booking/12.9` and `GET /booking/13xyz` returned bookings 12 and 13.
- Reproduced: 4 times (2 DELETE, 2 GET)

### F2: String "false" for depositpaid is stored as true (JSON, XML, urlencoded, PUT)
- Severity: high
- Request: `curl -s -i -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"T","lastname":"DepF","totalprice":5,"depositpaid":"false","bookingdates":{"checkin":"2020-01-01","checkout":"2020-01-05"},"additionalneeds":"x"}'`
- Expected: either 400 (wrong type) or depositpaid=false. Storing the opposite of what the client sent is never right.
- Actual: 200 with `"depositpaid":true`. The same thing happens with XML `<depositpaid>false</depositpaid>` (booking 20, confirmed by a JSON GET), with urlencoded `depositpaid=false` (booking 22), and with a PUT on booking 12. A JSON boolean `false` is kept correctly. Because XML and form bodies can only carry strings, those formats cannot record an unpaid deposit at all.
- Reproduced: 4 times

### F3: Decimal totalprice is silently truncated to an integer
- Severity: high
- Request: `curl -s -i -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"T","lastname":"Dec","totalprice":99.99,"depositpaid":false,"bookingdates":{"checkin":"2020-01-01","checkout":"2020-01-05"},"additionalneeds":"x"}'`
- Expected: totalprice 99.99. The docs type it as Number, not integer.
- Actual: 200 with `"totalprice":99`. A PUT with 12.75 stored 12.
- Reproduced: 2 times (POST, PUT)

### F4: Partial PATCH of bookingdates overwrites the other date with "0NaN-aN-aN"
- Severity: high
- Request: `curl -s -i -X PATCH http://localhost:3003/booking/11 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=<valid token>' -d '{"bookingdates":{"checkin":"2020-01-02"}}'`
- Expected: checkin is updated and checkout stays 2020-01-05. The docs mark bookingdates.checkin and checkout as separately optional in PATCH.
- Actual: 200 with `"bookingdates":{"checkin":"2020-01-02","checkout":"0NaN-aN-aN"}`. Patching only checkout on booking 12 turned its checkin into `"0NaN-aN-aN"`.
- Reproduced: 2 times

### F5: GET /booking date filters do not follow the documented ">=" semantics
- Severity: high
- Request: `curl -s 'http://localhost:3003/booking?checkin=2022-05-10'` and `curl -s 'http://localhost:3003/booking?checkout=2022-05-02'`
- Expected (docs): "checkin greater than or equal to" and "checkout greater than or equal to" the given date.
- Actual: The checkin filter is strictly greater-than. Booking 24 (checkin 2022-05-10) is missing from the checkin=2022-05-10 results. Booking 11 (checkin 2020-01-01) was missing for checkin=2020-01-01 but present for checkin=2019-12-31. The checkout filter works as less-than-or-equal: checkout=2022-05-02 returns booking 24 (checkout 2022-05-01) and booking 20 (checkout 2019-01-01). checkout=2020-01-05 returned booking 13 (checkout 2020-01-01) and booking 11 (equal), and left out booking 12 (checkout 2021-03-02).
- Reproduced: 2 times for each filter, on different data

### F6: Invalid values are stored instead of rejected (totalprice -> null, bad dates -> "0NaN-aN-aN", impossible dates rolled over)
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"R","lastname":"Repro","totalprice":"ten","depositpaid":true,"bookingdates":{"checkin":"2021-04-31","checkout":"garbage"},"additionalneeds":"x"}'`
- Expected: 400. totalprice must be a Number and the dates must be valid CCYY-MM-DD.
- Actual: 200 with `"totalprice":null,"bookingdates":{"checkin":"2021-05-01","checkout":"0NaN-aN-aN"}`. Earlier, `totalprice:"abc"` gave null (booking 14) and `"notadate"`/`"2020-13-45"` gave `0NaN-aN-aN` (booking 15). A PUT with 2021-02-30 stored 2021-03-02.
- Reproduced: 3 times

### F7: Missing or wrongly typed required fields cause 500 on POST, not 400
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"R","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2020-01-01","checkout":"2020-01-05"},"additionalneeds":"x"}'`
- Expected: 400 Bad Request, which is what PUT returns for an incomplete body.
- Actual: `500 Internal Server Error`. Missing firstname, missing lastname, missing bookingdates and a numeric firstname (`"firstname":123`) all gave 500.
- Reproduced: 4 times

### F8: Logical validation missing: negative totalprice and checkout before checkin accepted
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"R","lastname":"Rev","totalprice":-1,"depositpaid":true,"bookingdates":{"checkin":"2022-05-10","checkout":"2022-05-01"},"additionalneeds":"x"}'`
- Expected: 400. A negative price or a stay that ends before it starts is not a valid booking (reasoning; the docs are silent).
- Actual: 200, stored with `"totalprice":-1` and checkin after checkout. Bookings 12 (-500) and 13 (reversed dates) behaved the same way.
- Reproduced: 2 times for each

### F9: Accept: application/x-www-form-urlencoded returns 200 with a JS error as the body, after the booking has already been created
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3003/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/x-www-form-urlencoded' -d 'firstname=Ulla&lastname=Form&totalprice=111&depositpaid=false&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02&additionalneeds=Late%20checkout'`
- Expected: a urlencoded body as in the docs' "URL Response" example.
- Actual: `200 OK`, `Content-Type: text/html`, body `formurlencoded is not a function`. The booking was still created (id 21, found with `?firstname=Ulla`), but the client never gets its id. `GET /booking/11` with the same Accept gives the same error.
- Reproduced: 2 times (POST, GET)

### F10: PUT/PATCH/DELETE on a non-existent booking return 405, not 404
- Severity: low
- Request: `curl -s -i -X DELETE http://localhost:3003/booking/11 -H 'Cookie: token=<valid token>'` (after 11 was deleted)
- Expected: 404 Not Found, which is what GET returns for the same id.
- Actual: `405 Method Not Allowed`. Seen for DELETE /booking/999999, a second DELETE of 11, PUT of 11 and PATCH of 11.
- Reproduced: 4 times

### F11: POST /auth with bad credentials returns 200
- Severity: low
- Request: `curl -s -i -X POST http://localhost:3003/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 (or 400). A client that checks the status code will think it is logged in.
- Actual: `200 OK` with `{"reason":"Bad credentials"}`. Also seen with a missing password and with an unknown user.
- Reproduced: 3 times

### F12: Unsupported Accept returns 418 I'm a Teapot
- Severity: low
- Request: `curl -s -i http://localhost:3003/booking/13 -H 'Accept: text/csv'`
- Expected: 406 Not Acceptable, or a fallback to JSON.
- Actual: `418 I'm a Teapot`. The same happens with `Accept: text/plain`.
- Reproduced: 2 times

### F13: POST with a missing or unsupported Content-Type returns 500
- Severity: low
- Request: `curl -s -i -X POST http://localhost:3003/booking -H 'Accept: application/json' -H 'Content-Type: text/plain' -d '<valid JSON booking>'`
- Expected: 415 Unsupported Media Type (or 400).
- Actual: `500 Internal Server Error`. It is the same with no Content-Type header.
- Reproduced: 2 times

### F14: XML responses use Content-Type text/html
- Severity: low
- Request: `curl -s -i http://localhost:3003/booking/11 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`, since the client asked for it.
- Actual: `Content-Type: text/html; charset=utf-8` with an XML body. POST with Accept application/xml does the same.
- Reproduced: 2 times

## Questions
- Booking 15 has corrupt dates (`0NaN-aN-aN`). It appears in some date-filter results (checkin=2020-01-01, checkin=2022-05-10, checkout=2022-05-02) but not in others (checkout=2020-01-05). The comparison logic for invalid dates looks inconsistent, but I did not isolate it.
- Empty strings for firstname and lastname are accepted (booking 17). It is unclear whether this is intended, since the docs don't say they must be non-empty. I saw it once.
- The docs say DELETE and /ping "Success 200" but show `201 Created`, and the server returns 201. Nothing contradicts the examples, but the docs disagree with themselves.
- The docs' PATCH examples use `curl -X PUT`, which is probably a docs error.
- Not tested: token expiry and reuse, and whether a new /auth call invalidates old tokens.
- POST is not idempotent, so a double submit creates duplicates. That is expected for POST, so I am not reporting it.

## Coverage
- Explored: /ping, /auth (good, bad, missing field, malformed), auth enforcement on PUT/PATCH/DELETE (no auth, bogus, empty and truncated token, wrong Basic creds), POST/PUT validation (missing fields, wrong types, decimals, negatives, reversed and impossible dates, malformed JSON, Content-Type handling), JSON/XML/urlencoded request and response formats, PATCH partial updates (top-level and nested), search by name and dates, the delete lifecycle, and odd ids (non-numeric, negative, decimal, trailing letters).
- Auth enforcement held up: every unauthorised mutation got 403 and the data stayed unchanged.
- Not covered: huge payloads, special or unicode characters in names, XML-specific attacks (entities), concurrent updates, the case sensitivity of the name search, combining name and date filters, token lifetime.
- Requests used: 70 of 80.
