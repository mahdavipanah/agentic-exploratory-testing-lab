# Exploration report

## Charters

Risks (written before any request other than `GET /ping`, most damaging to a client first):
1. Auth on PUT/PATCH/DELETE: a write is accepted with missing or wrong token/Basic credentials. Anyone could change or destroy bookings.
2. Data integrity on create/update: wrong types, missing required fields, checkout before checkin and negative prices are stored silently. PATCH could wipe fields that were not sent.
3. Data that changes in transit: a booking created as JSON/XML/urlencoded comes back different (types, dates, special characters) through GET, PUT, PATCH and the search filters.
4. Search filter semantics: the checkin/checkout ">=" rules, case sensitivity of names, invalid dates. Clients get missing or wrong results.
5. Status codes for missing ids and repeated actions: double delete, update after delete, non-numeric ids. The docs also contradict themselves (DELETE/ping say "Success 200" but show "201 Created").

Charters:
- C1: Explore PUT/PATCH/DELETE auth with missing, wrong, truncated and alternative credentials (Saboteur tour) to discover whether unauthorised writes are possible. Budget: 20 requests. Used: 18.
- C2: Explore POST/PUT/PATCH /booking bodies with missing, wrong-type, negative, empty and malformed values (Antisocial tour) to discover what invalid data the API stores or crashes on. Budget: 20. Used: 15.
- C3: Explore one booking's journey through create → get → search → put in JSON, XML and urlencoded (FedEx tour) to discover data that is lost or changed on the way. Budget: 20. Used: 9.
- C4: Explore GET /booking filters and repeated/reordered actions (Back alley + Obsessive-compulsive tours) to discover wrong search results and inconsistent status codes. Budget: 18. Used: 15.
- Reserve: 2 requests. Reproductions and the extra PATCH-type probes used 11 more requests, taken from what C2 and C3 did not spend.

## Findings

### F1: PATCH with only `bookingdates.checkin` corrupts the stored checkout to "0NaN-aN-aN"
- Severity: high
- Request: `curl -X PATCH http://localhost:3002/booking/15 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=417eaf1f9483c1a' -d '{"bookingdates":{"checkin":"2018-06-01"}}'`
- Expected: Every PATCH body field is documented as optional, so fields that are not sent (here `bookingdates.checkout`) should stay unchanged (checkout was "2019-01-01").
- Actual: 200 `{"firstname":"Dep",...,"bookingdates":{"checkin":"2018-06-01","checkout":"0NaN-aN-aN"},...}`. A later `GET /booking/15` returned the same corrupted value, so it was saved.
- Reproduced: 2 (booking 11 and booking 15), plus a GET confirming it was saved.

### F2: `depositpaid=false` is stored as `true` for XML, urlencoded and string `"false"` input
- Severity: high
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking><firstname>Zoë &amp; Co</firstname><lastname>O&apos;Brien</lastname><totalprice>99.5</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2021-03-01</checkin><checkout>2021-03-05</checkout></bookingdates><additionalneeds>Late &lt;checkout&gt;</additionalneeds></booking>'`
- Expected: The docs show XML and urlencoded as supported formats with `depositpaid` as a Boolean. The value `false` should be stored as false, as it is for JSON boolean `false` (booking 19).
- Actual: 200 `<depositpaid>true</depositpaid>`. The same happened for XML PUT on booking 19 (it was false, PUT with `<depositpaid>false</depositpaid>` returned `"depositpaid":true`), for urlencoded `depositpaid=false` (booking 20, GET shows `true`), and for JSON string `"depositpaid":"false"` (bookings 17 and 22).
- Reproduced: 5 (XML POST, XML PUT, urlencoded POST, JSON string ×2).

### F3: Checkout search filter is inverted (returns checkout <= date, not >=)
- Severity: high
- Request: `curl 'http://localhost:3002/booking?checkout=2030-01-01'`
- Expected: Docs: "Return bookings that have a checkout date greater than or equal to the set checkout date." No booking has a checkout after 2030, so the result should be empty.
- Actual: 200 with all 20 ids. `?checkout=2021-03-05` returned booking 12 (checkout 2018-01-01) and 13 (2019-01-01), but not booking 20 (checkout 2022-01-02). `?checkout=2022-01-02` returned 20 and the earlier ones.
- Reproduced: 3 queries.

### F4: Checkin search filter excludes the exact date and matches bookings with invalid dates
- Severity: medium
- Request: `curl 'http://localhost:3002/booking?checkin=2022-01-01'`
- Expected: Docs say "greater than or equal to". Booking 20 has checkin 2022-01-01 and should be returned. Booking 14 (checkin "0NaN-aN-aN") should not match any date.
- Actual: 200 `[{"bookingid":4},{"bookingid":5},{"bookingid":6},{"bookingid":14}]`. 20 is missing and 14 is included. In the same way, `?checkin=2021-03-01` left out 18 and 19 (checkin exactly 2021-03-01) and included 14.
- Reproduced: 2.

### F5: Invalid input is stored silently: non-numeric price becomes null, invalid date becomes "0NaN-aN-aN"
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":111,"depositpaid":true,"bookingdates":{"checkin":"notadate","checkout":"2019-01-01"},"additionalneeds":"x"}'`
- Expected: A 400 rejection. `totalprice` is a Number and the dates are Dates, and none of them are optional.
- Actual: 200 with `"checkin":"0NaN-aN-aN"` (booking 14, saved as shown by GET). `"totalprice":"abc"` gave 200 with `"totalprice":null` (booking 13). The same happened through PATCH (`"totalprice":"abc"` on 11 and `"totalprice":"free"` on 22 → null).
- Reproduced: 4.

### F6: No business-rule validation: negative price and checkout before checkin are accepted
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg","lastname":"Price","totalprice":-500,"depositpaid":true,"bookingdates":{"checkin":"2019-01-01","checkout":"2018-01-01"},"additionalneeds":"Breakfast"}'`
- Expected: A 400 rejection. A booking cannot end before it starts, and a negative total price makes no sense.
- Actual: 200 `{"bookingid":12,"booking":{...,"totalprice":-500,...,"checkin":"2019-01-01","checkout":"2018-01-01"}}`
- Reproduced: 2 (bookings 12 and 22).

### F7: Server errors (500) for missing fields, wrong-typed names, unsupported content type and invalid filter dates
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Missing","totalprice":111,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"}}'`
- Expected: 400 for client input errors (PUT with an incomplete body correctly returns 400, and malformed JSON returns 400). 415 or 400 for an unsupported content type.
- Actual: 500 `Internal Server Error` for: a missing lastname; missing bookingdates; `"firstname":123`; `Content-Type: text/plain`; `GET /booking?checkin=notadate`; `GET /booking?checkout=2020-13-45`.
- Reproduced: each variant twice (missing field ×2, numeric firstname ×2, text/plain ×2, bad filter date ×2).

### F8: PATCH accepts wrong types that POST rejects (numeric/boolean/null names stored)
- Severity: medium
- Request: `curl -X PATCH http://localhost:3002/booking/21 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=417eaf1f9483c1a' -d '{"firstname":123,"lastname":null}'`
- Expected: A 400 rejection. The names are Strings, and POST rejects `"firstname":123`, though with a 500 (see F7).
- Actual: 200 `{"firstname":123,"lastname":null,...}`. A GET as XML shows `<lastname>null</lastname>`, so the literal string "null" reaches clients. PATCH `{"firstname":false}` on 22 also returned `"firstname":false`.
- Reproduced: 2.

### F9: `Accept: application/x-www-form-urlencoded` returns a code error with status 200; on POST the booking is created but its id is never returned
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/x-www-form-urlencoded' -d 'firstname=Url&lastname=Enc&totalprice=250&depositpaid=false&bookingdates%5Bcheckin%5D=2022-01-01&bookingdates%5Bcheckout%5D=2022-01-02&additionalneeds=a%26b'`
- Expected: The docs give a "URL Response" example: `bookingid=1&booking%5Bfirstname%5D=...`
- Actual: 200 `Content-Type: text/html`, body `formurlencoded is not a function`. The booking was still created (GET /booking/20 returns it), but the client has no way to learn its id. `GET /booking/20` with the same Accept gives the same error body with 200.
- Reproduced: 2 (POST, GET).

### F10: Decimal prices are silently truncated
- Severity: medium
- Request: `curl -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Dec","lastname":"False","totalprice":99.5,"depositpaid":false,"bookingdates":{"checkin":"2021-03-01","checkout":"2021-03-05"},"additionalneeds":"x"}'`
- Expected: `totalprice` is documented as a Number, so 99.5 should be stored as 99.5, or else rejected.
- Actual: 200 `"totalprice":99`
- Reproduced: 2 (JSON booking 19, XML booking 18).

### F11: POST /auth returns 200 for bad credentials
- Severity: low
- Request: `curl -X POST http://localhost:3002/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: A 401 (or 400) status, so that clients can detect a failed login without parsing the body.
- Actual: 200 `{"reason":"Bad credentials"}`
- Reproduced: 3 (wrong password, missing password, uppercase username).

### F12: PUT/PATCH/DELETE on a missing booking return 405 instead of 404
- Severity: low
- Request: `curl -X DELETE http://localhost:3002/booking/16 -H 'Cookie: token=417eaf1f9483c1a'` (after 16 was already deleted)
- Expected: 404 Not Found, which is what GET /booking/16 returns. The methods are allowed on this route, so 405 is misleading.
- Actual: 405 `Method Not Allowed` for DELETE, PATCH and PUT
- Reproduced: 3.

### F13: XML responses are sent with `Content-Type: text/html`
- Severity: low
- Request: `curl -i http://localhost:3002/booking/19 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`, because the client asked for it in Accept.
- Actual: 200 `Content-Type: text/html; charset=utf-8` with an XML body
- Reproduced: 3 (POST XML, GET 19, GET 21).

## Questions
- Name filters are case-sensitive: `?lastname=Brown` → [5,6,11], `?lastname=brown` → []. The docs example uses `firstname=sally&lastname=brown` while the data is "Sally Brown", so the documented example may return nothing. It is unclear whether this is intended.
- DELETE success is `201 Created`. The docs table says "Success 200" but the example shows 201, so the docs contradict themselves. 200/204 would be the conventional choice.
- Empty firstname/lastname ("") and a missing `additionalneeds` are accepted, even though the docs mark them as not optional. A missing lastname, however, gives a 500. The intended rules for required fields are unclear.
- The XML response escapes `<` but not `>` (`Late &lt;checkout>`). That is valid XML, but I noted it. Special characters (ë, &, ') otherwise survived the round trip and search.
- Extra fields (`bookingid`, `isAdmin`) in POST are silently ignored. That is fine, but it is undocumented.
- Tokens: a new /auth call did not visibly invalidate older tokens, though I did not test the old token after issuing a new one. Token expiry was not tested.
- Very large payloads were not tested (that request was blocked locally and never sent).

## Coverage
Explored: auth enforcement on PUT/PATCH/DELETE (no auth, fake/empty/truncated token, wrong Basic, valid cookie and valid Basic). Auth was enforced correctly in every case. Also: POST validation (types, missing fields, negative values, reversed dates, malformed JSON, unsupported content type); PATCH partial updates and types; PUT incomplete body; JSON/XML/urlencoded create, PUT and GET round trips; checkin/checkout/name filters and their boundaries; delete twice, then update/get after delete; non-numeric id.
Not covered: very large payloads, token expiry/rotation, concurrency/race conditions, XML malformed bodies, PATCH via XML/urlencoded, DELETE via Basic auth, HEAD/OPTIONS methods, combined filters.
Requests used: 68 of 80.
