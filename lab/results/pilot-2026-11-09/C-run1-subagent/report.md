# Exploration report

## Charters

Risks found in the docs, worst first:
- R1, auth bypass: PUT, PATCH and DELETE are guarded by a token cookie or Basic auth. If a missing, wrong, malformed or reused credential works, anyone can change or delete bookings. POST /auth might also report failure with a 200.
- R2, data changed on the round trip: data goes through POST, GET, PUT and PATCH in JSON, XML and urlencoded. Prices, booleans, dates or non-ASCII text could change silently, and PATCH could wipe fields it was not sent.
- R3, weak validation: the docs list types and required fields but no error behaviour. Bad input could be stored as garbage or cause a 500.
- R4, docs and API disagree: DELETE and /ping are documented as "Success 200" but the examples show 201. The PATCH examples use PUT. The id is typed String in one place and Number in others. The checkout filter is described as "greater than or equal".
- R5, search filters: they could be case-sensitive, get the date boundaries wrong, or return 500 on malformed dates.
- R6, repeated or out-of-order actions: deleting twice, or updating or reading after a delete, could leave bad state or return misleading codes.

Charters (80 requests in total: 1 for GET /ping, 79 shared below):
- C1: Explore auth on PUT, PATCH and DELETE with valid, invalid, missing and malformed tokens, Basic auth variants and POST /auth with bad credentials to discover whether any write succeeds without valid credentials. Tour: Saboteur. Budget: 18. (R1)
- C2: Explore the booking lifecycle (POST, GET, list, PUT, PATCH, DELETE) with one distinctive booking sent in JSON, XML and urlencoded to discover whether data arrives unchanged and whether the documented examples and status codes behave as written. Tour: FedEx + Guidebook. Budget: 22. (R2, R4)
- C3: Explore POST, PUT and PATCH bodies with missing, extra, wrong-type, negative, huge, malformed and illogical input to discover what invalid data gets stored and what crashes the server. Tour: Antisocial. Budget: 20. (R3)
- C4: Explore GET /booking filters with boundary dates, case variations and malformed values to discover whether search returns the right subset. Tour: Back alley. Budget: 10. (R5)
- C5: Explore repeated and reordered actions (double DELETE, PUT or PATCH after DELETE, unknown ids, reusing an old token) to discover state problems and misleading status codes. Tour: Obsessive-compulsive. Budget: 9. (R6)

I added no new charter. C5 also spent one request (#80) reproducing F1.

## Findings

### F1: PATCH with only one booking date wipes the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -X PATCH http://localhost:3003/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=5be19583227e3da' -d '{"bookingdates":{"checkout":"2026-03-04"}}'`
- Expected: PATCH is documented as a partial update and every field is optional, so only checkout should change. Checkin should stay 2026-02-28.
- Actual: 200 `"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2026-03-04"}`. Sending only checkin (#80) wiped checkout the same way: `{"checkin":"2026-05-02","checkout":"0NaN-aN-aN"}`. The corrupted value is stored, and a later GET returns it.
- Reproduced: 3 times (#25 urlencoded, #28 JSON checkout only, #80 JSON checkin only)

### F2: depositpaid strings "false" and "no" are stored as true
- Severity: high
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/json' -d 'firstname=Form&lastname=False&totalprice=10&depositpaid=false&bookingdates%5Bcheckin%5D=2026-06-01&bookingdates%5Bcheckout%5D=2026-06-02&additionalneeds=None'`
- Expected: urlencoded is a documented format, so depositpaid=false should be stored as false. A non-boolean such as "no" should be rejected.
- Actual: 200 with `"depositpaid":true`. A booking whose deposit is unpaid is recorded as paid.
- Reproduced: 4 times (#25 and #29 PATCH urlencoded, #39 POST urlencoded, #50 JSON `"depositpaid":"no"`)

### F3: Invalid dates are accepted and stored as "0NaN-aN-aN"
- Severity: high
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date2","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"not-a-date","checkout":"2026-06-02"},"additionalneeds":"None"}'`
- Expected: a 400, because checkin is typed Date.
- Actual: 200, booking 25 created with `"checkin":"0NaN-aN-aN"`.
- Reproduced: 2 times (#46 "2026-13-45", #58 "not-a-date")

### F4: Impossible calendar dates silently roll over into the next month
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Feb","lastname":"Thirty","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2026-02-30","checkout":"2026-03-05"},"additionalneeds":"None"}'`
- Expected: a 400, or the value stored as sent. A different date should not be saved without notice.
- Actual: 200 with `"checkin":"2026-03-02"`. 2026-04-31 became 2026-05-01. The guest's stay changes silently.
- Reproduced: 2 times (#60, #70)

### F5: Decimal totalprice is truncated to an integer
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Price","lastname":"Frac","totalprice":99.99,"depositpaid":false,"bookingdates":{"checkin":"2026-06-01","checkout":"2026-06-02"},"additionalneeds":"None"}'`
- Expected: totalprice is typed Number, so 99.99 should be stored, or rejected if only whole numbers are allowed.
- Actual: 200 with `"totalprice":99`. 123.45 became 123 (#19), and GET #20 confirms the stored value. The value is cut off, not rounded.
- Reproduced: 2 times (#19, #38)

### F6: A non-numeric totalprice is accepted and stored as null
- Severity: medium
- Request: `curl -X PATCH http://localhost:3003/booking/16 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=5be19583227e3da' -d '{"totalprice":"free"}'`
- Expected: a 400, because totalprice is typed Number.
- Actual: 200 with `"totalprice":null`. The price is lost.
- Reproduced: 2 times (#43 POST "abc", #54 PATCH "free")

### F7: Negative prices and checkout before checkin are accepted
- Severity: medium
- Request: `curl -X PATCH http://localhost:3003/booking/16 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=5be19583227e3da' -d '{"totalprice":-1,"bookingdates":{"checkin":"2026-07-10","checkout":"2026-07-01"}}'`
- Expected: a 400. A booking cannot have a negative price or end before it starts.
- Actual: 200 with `"totalprice":-1,...,"checkin":"2026-07-10","checkout":"2026-07-01"`.
- Reproduced: negative price 2 times (#44, #57), reversed dates 2 times (#45, #57)

### F8: POST with a missing field or a wrong-typed name returns 500, not 400
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"lastname":"NoFirst","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2026-06-01","checkout":"2026-06-02"},"additionalneeds":"None"}'`
- Expected: a 400 for client errors. PUT with missing fields does return 400 (#53), so POST is inconsistent.
- Actual: 500 `Internal Server Error`. The same happens with `{}` and with `"firstname":12345`.
- Reproduced: 4 times (#41 missing firstname, #42 `{}`, #48 and #51 numeric firstname)

### F9: POST with a missing or unsupported Content-Type returns 500
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: text/plain' -H 'Accept: application/json' -d '{"firstname":"Plain","lastname":"X","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2026-06-01","checkout":"2026-06-02"},"additionalneeds":"None"}'`
- Expected: a 415 or 400. Content-Type is a required header with documented values.
- Actual: 500 `Internal Server Error`.
- Reproduced: 2 times (#56 empty Content-Type, #59 text/plain)

### F10: A malformed date in a GET /booking filter returns 500
- Severity: medium
- Request: `curl "http://localhost:3003/booking?checkin=garbage"`
- Expected: a 400. The docs say "Format must be CCYY-MM-DD".
- Actual: 500 `Internal Server Error`.
- Reproduced: 2 times (#67 checkin=garbage, #69 checkout=31-12-2026)

### F11: The checkin filter leaves out bookings that check in on the given date
- Severity: medium
- Request: `curl "http://localhost:3003/booking?checkin=2026-06-01"`
- Expected: the docs say "checkin date greater than or equal to". Bookings 17, 18, 19, 22, 23 and 24 all check in on 2026-06-01 and should be listed.
- Actual: 200 `[{"bookingid":3},{"bookingid":16},{"bookingid":20},{"bookingid":21},{"bookingid":25}]`, with none of the same-day bookings. With checkin=2026-07-10, booking 16 (checkin exactly 2026-07-10) was also missing. The filter behaves as strictly greater than.
- Reproduced: 2 times (#63, #64)

### F12: The checkout filter returns bookings on or before the date, the opposite of the docs
- Severity: medium
- Request: `curl "http://localhost:3003/booking?checkout=2025-01-05"`
- Expected: the docs say "checkout date greater than or equal to the set checkout date". Bookings 12 (2026-03-04) and 16 (2026-07-01) should be included.
- Actual: 200 `[{"bookingid":11},{"bookingid":13}]`, whose checkouts are 2025-01-05 and 2019-01-01. With checkout=2026-06-02 (#66), booking 13 (2019-01-01) was returned and booking 16 (2026-07-01) was not. The filter behaves as less than or equal. Combined with F11, the checkin bound excludes the boundary date and the checkout bound includes it.
- Reproduced: 2 times (#66, #68)

### F13: Bookings with a corrupted checkin match every checkin filter
- Severity: low
- Request: `curl "http://localhost:3003/booking?checkin=2026-07-10"`
- Expected: bookings 21 and 25 have checkin "0NaN-aN-aN" (see F3) and should not match a "checkin on or after" date.
- Actual: 200 `[{"bookingid":3},{"bookingid":21},{"bookingid":25}]`. Bookings 21 and 25 appear for both 2026-06-01 and 2026-07-10.
- Reproduced: 2 times (#63, #64)

### F14: Accept: application/x-www-form-urlencoded returns 200 with an internal error message
- Severity: medium
- Request: `curl http://localhost:3003/booking/16 -H 'Accept: application/x-www-form-urlencoded'`
- Expected: a urlencoded body, as in the docs' "URL Response" example, or at worst a 406.
- Actual: 200 with Content-Type text/html and the body `formurlencoded is not a function`. This leaks an internal error and reports success.
- Reproduced: 2 times (#22, #40)

### F15: XML responses are sent with Content-Type text/html
- Severity: low
- Request: `curl -i http://localhost:3003/booking/12 -H 'Accept: application/xml'`
- Expected: Content-Type application/xml, since that is what was asked for in Accept.
- Actual: 200 `Content-Type: text/html; charset=utf-8` with an XML body. Strict clients will not parse it as XML.
- Reproduced: 3 times (#21 GET, #24 PUT, #33 POST)

### F16: PUT, PATCH and DELETE on a missing or deleted booking return 405, not 404
- Severity: medium
- Request: `curl -X DELETE http://localhost:3003/booking/99999 -H 'Cookie: token=5be19583227e3da'`
- Expected: a 404. The method is allowed on this route, and GET on the same ids returns 404 (#35, #76).
- Actual: 405 `Method Not Allowed`. Clients cannot tell "no such booking" apart from "wrong method".
- Reproduced: 4 times (#71 second DELETE of 15, #72 PUT on deleted 14, #73 PATCH on deleted 14, #75 DELETE of 99999)

### F17: POST /auth with bad credentials returns 200
- Severity: medium
- Request: `curl -X POST http://localhost:3003/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: a 401 or 403. The docs list only a 200 response containing a token.
- Actual: 200 `{"reason":"Bad credentials"}`. A client that checks only the status code will think it logged in.
- Reproduced: 3 times (#3 wrong password, #16 missing password, #17 object password `{"$ne":null}`)

### F18: DELETE returns 201 Created, but the docs' success section says 200
- Severity: low
- Request: `curl -i -X DELETE http://localhost:3003/booking/14 -H 'Content-Type: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='`
- Expected: the docs' section says "Success 200", and 201 Created means a resource was created, which is wrong for a delete. A 200 or 204 would be correct.
- Actual: 201 `Created`. GET /ping does the same (#1).
- Reproduced: 2 times (#34 Basic auth, #36 cookie)

## Questions
- The name filters are case-sensitive: `?firstname=jim&lastname=brown` returned `[]` and `?firstname=Jim&lastname=Brown` returned `[{"bookingid":13}]`. The docs' example uses lowercase "sally"/"brown", so it is unclear which behaviour is intended.
- Booking 12 has checkin "0NaN-aN-aN" from F1 but was not returned by the checkin filters, while bookings 21 and 25 (corrupted on POST, F3) were. The two kinds of corruption may be stored differently. I could not confirm this from outside.
- The old token still worked after a new one was issued (#79). The docs say nothing about expiry or rotation, and I did not test expiry over time.
- A 100,000-character firstname was accepted with 200 (#52). No length limit is documented.
- Unknown fields such as `"bookingid":1,"admin":true` are silently ignored (#49). This is harmless here, but the client gets no feedback.
- The urlencoded POST example from the docs omits additionalneeds, yet it succeeds (#31) and the response leaves the field out. The docs mark additionalneeds as not optional in both request and response, and seed bookings 1 and 3 also lack it.
- Problems in the docs themselves: the PATCH examples use `curl -X PUT`; the Authorization row contains garbled text (`YWRtaW46cGFzc3dvcmQxMjM=]`); id is typed String for GET and Number elsewhere; the Content-Type rows list only JSON and XML while the examples use urlencoded; DELETE and /ping say "Success 200" but show 201.

## Coverage
- Explored: all 7 endpoints (/auth, GET, POST, PUT and PATCH on /booking, DELETE, GET /booking list and filters, /ping); all 3 body formats for POST; XML for PUT; urlencoded for PATCH; Accept set to JSON, XML and urlencoded; cookie and Basic auth, valid and invalid; type, range, date and Content-Type validation; checkin and checkout filter boundaries; deleted and non-existent ids.
- Auth (C1) held up: no write succeeded without valid credentials. Missing, empty, prefix-only, wrong and duplicate-cookie tokens, and wrong, empty-password and malformed Basic auth were all rejected with 403.
- Not covered: double POST and duplicate detection; concurrent updates; PATCH and PUT with an XML body containing bad data; PUT with urlencoded; unsupported Accept values (for example text/csv); negative and zero ids; HEAD and OPTIONS; injection through filter values; token expiry over time; combined checkin plus checkout filters (docs example 3).
- Requests used: 80 of 80. By charter: #1-2 ping and first token; C1 #3-18 (16); C2 #19-40 (22); C3 #41-60 (20); C4 #61-69 (9); #70 reproduced F4; C5 #71-79 (9); #80 reproduced F1.
