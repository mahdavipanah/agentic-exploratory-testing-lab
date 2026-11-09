# Exploration report

## Charters

Risks (from reading the docs, ranked by client harm):
- R1 Auth on PUT/PATCH/DELETE: bad, missing or expired tokens, a wrong Basic header, or a bad login still being accepted. Anyone could change or delete bookings.
- R2 Data integrity: a booking created via POST is changed when it is read back through GET, PUT, PATCH or the list filters (types, dates, nested object, XML/urlencoded formats). PATCH might wipe fields it was not given.
- R3 Input validation on POST/PUT: missing required fields, wrong types, negative price, checkout before checkin, or malformed body are accepted and stored, or cause a 500.
- R4 Status codes differ from the docs: ping/delete documented as 201, 404 for unknown ids, 200 for create.
- R5 Search filters (firstname/lastname/checkin/checkout) return wrong subsets, for example in case sensitivity or in the ">=" date semantics.

Charters:
1. Explore PUT/PATCH/DELETE auth with missing/forged/garbage tokens and Basic headers to discover whether unauthenticated callers can modify data. Tour: Saboteur. Budget: ~18 requests.
2. Explore a single booking's lifecycle (POST -> GET json/xml -> list filters -> PATCH -> PUT -> DELETE -> GET) with one distinctive record to discover data loss or mutation between endpoints and formats. Tour: FedEx. Budget: ~20 requests.
3. Explore POST/PUT /booking with missing, wrong-type, negative, huge and malformed payloads to discover weak validation and server errors. Tour: Antisocial. Budget: ~20 requests.
4. Explore documented examples, status codes and GET /booking filter semantics with the docs as the oracle to discover deviations from the documented contract. Tour: Guidebook. Budget: ~12 requests.
5. Explore repeated/duplicated actions (double delete, double create, reuse of a token) with the remaining budget to discover state inconsistencies. Tour: Obsessive-compulsive. Budget: ~10 requests.

## Findings
### F1: PATCH with a partial `bookingdates` object corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -X PATCH http://localhost:3004/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=7c3ff355aacbace' -d '{"bookingdates":{"checkin":"2031-01-02"}}'`
- Expected: PATCH is a partial update. Docs mark `bookingdates.checkin` and `bookingdates.checkout` as separately optional, so the field left out should keep its stored value.
- Actual: 200 `{..."bookingdates":{"checkin":"2031-01-02","checkout":"0NaN-aN-aN"},...}`. The corrupt value is saved (a later GET returns the same thing). Because of it, the booking also disappears from date searches (`GET /booking?checkin=1900-01-01` left out booking 11 while it was corrupt).
- Reproduced: 2 times (booking 11 with checkout-only gave a corrupt checkin; booking 12 with checkin-only gave a corrupt checkout), and confirmed both times with a GET.

### F2: `depositpaid: false` is stored as `true` unless sent as a JSON boolean (XML, urlencoded, JSON string)
- Severity: high
- Request: `curl -X POST http://localhost:3004/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking><firstname>Xml</firstname><lastname>Doc</lastname><totalprice>111</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2018-01-01</checkin><checkout>2019-01-01</checkout></bookingdates><additionalneeds>Breakfast</additionalneeds></booking>'`
- Expected: Docs show XML and urlencoded as supported input formats, so `false` should be stored as `false`. Any non-boolean value should be rejected with 400.
- Actual: 200 with `<depositpaid>true</depositpaid>`, and GET /booking/20 returns `"depositpaid":true`. The same happened with a PUT in XML (`depositpaid` false gave true), a urlencoded POST `depositpaid=false` (booking 22), a urlencoded PATCH `depositpaid=false`, and a JSON `"depositpaid":"false"` string (bookings 16 and 19). Clients are told no deposit was paid when one was, or the other way round.
- Reproduced: XML 2 times (POST and PUT), urlencoded 2 times (POST and PATCH), JSON string 2 times.

### F3: The `checkout` search filter is inverted (it returns checkout <= date, not >=)
- Severity: medium
- Request: `curl 'http://localhost:3004/booking?checkout=1990-01-01'` and `curl 'http://localhost:3004/booking?firstname=Xml&checkout=2025-01-01'`
- Expected: Docs say "Return bookings that have a checkout date greater than or equal to the set checkout date". So 1990-01-01 should match every booking, and booking 20 (checkout 2019-01-01) should not match 2025-01-01.
- Actual: 200 `[]` for 1990-01-01. `checkout=2099-01-01` returns every booking. `firstname=Xml&checkout=2025-01-01` returns `[{"bookingid":20}]`. With booking 11 (checkout 2030-05-10), `checkout=2030-05-09` left it out and `2030-05-11` included it.
- Reproduced: 5 times, with different dates and bookings.

### F4: The `checkin` search filter leaves out bookings whose checkin equals the date ("greater than or equal" behaves as "greater than")
- Severity: medium
- Request: `curl 'http://localhost:3004/booking?firstname=Xml&checkin=2018-01-01'`
- Expected: Docs say "checkin date greater than or equal to the set checkin date", so booking 20 (checkin 2018-01-01) should match.
- Actual: 200 `[]`. For booking 11 (checkin 2030-05-01), `checkin=2030-05-01` gave `[]` while `checkin=2030-04-30` gave `[{"bookingid":11}]`. Together with F3, a search in the style of the docs' combined example (`?checkin=..&checkout=..`) using a booking's exact dates returns `[]`.
- Reproduced: 3 times.

### F5: `Accept: application/x-www-form-urlencoded` returns 200 with an internal error message, but the write still happens
- Severity: medium
- Request: `curl -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/x-www-form-urlencoded' -d '{"firstname":"Url2","lastname":"Acc2","totalprice":5,"depositpaid":false,"bookingdates":{"checkin":"2034-01-01","checkout":"2034-01-02"},"additionalneeds":"x"}'`
- Expected: Docs give a "URL Response" example for GET, POST and PUT (`bookingid=1&booking%5Bfirstname%5D=...`). If the format is not supported, the API should return an error status and not save anything.
- Actual: 200 with body `formurlencoded is not a function` (an internal JS error leaked to the client). The booking was still created: `GET /booking?firstname=Url2&lastname=Acc2` returns `[{"bookingid":23}]` (booking 21 was created the same way earlier). A client that sees the error and retries will create duplicates. GET /booking/1 and /booking/11 with this Accept header return the same error.
- Reproduced: 4 times (2 POSTs with the creation confirmed each time, 2 GETs).

### F6: POST /booking with a missing or wrong-type required field returns 500 instead of 400
- Severity: medium
- Request: `curl -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"lastname":"NoFirst","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2032-01-01","checkout":"2032-01-02"},"additionalneeds":"x"}'`
- Expected: 400 Bad Request. Docs mark firstname and lastname as required, and PUT with a missing field (bookingdates) correctly returns 400.
- Actual: 500 `Internal Server Error`. The same happens with a missing lastname and with `"firstname":12345,"lastname":""`.
- Reproduced: 3 times.

### F7: A non-numeric `totalprice` is accepted and stored as `null`
- Severity: medium
- Request: `curl -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"Price","totalprice":"abc","depositpaid":"yes","bookingdates":{"checkin":"2032-01-01","checkout":"2032-01-02"},"additionalneeds":"x"}'`
- Expected: 400. Docs say totalprice is a Number and not optional.
- Actual: 200 `"totalprice":null`. An object (`{"a":1}`) gives the same result. A PATCH with `{"totalprice":"cheap"}` on booking 11 erased its price of 124 and set it to `null`.
- Reproduced: 3 times.

### F8: Invalid dates are accepted: impossible dates roll over silently and garbage is stored as "0NaN-aN-aN"
- Severity: medium
- Request: `curl -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2032-02-30","checkout":"notadate"},"additionalneeds":"x"}'`
- Expected: 400. Docs give the fields the Date type, and say the format must be CCYY-MM-DD.
- Actual: 200, `"checkin":"2032-03-01","checkout":"0NaN-aN-aN"`. With `2033-04-31` / `garbage`, the result was `"2033-05-01"` / `"0NaN-aN-aN"`.
- Reproduced: 2 times.

### F9: Negative price and checkout before checkin are accepted
- Severity: low
- Request: `curl -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Rev","lastname":"Dates","totalprice":-1,"depositpaid":true,"bookingdates":{"checkin":"2033-12-31","checkout":"2033-01-01"},"additionalneeds":"x"}'`
- Expected: 400. A booking cannot have a negative price or end before it starts. The docs don't state this rule; it is my reasoning.
- Actual: 200, booking 17 stored with `"totalprice":-1` and checkout before checkin.
- Reproduced: 2 times (-500 and -1).

### F10: PUT/PATCH/DELETE on a booking id that doesn't exist return 405 Method Not Allowed instead of 404
- Severity: low
- Request: `curl -X DELETE http://localhost:3004/booking/99999 -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='`
- Expected: 404 Not Found, which is what GET returns for a deleted id. The methods are allowed on this route.
- Actual: 405 `Method Not Allowed`. The same happened for DELETE, PUT and PATCH on the deleted booking 12.
- Reproduced: 4 times.

### F11: POST /auth with bad credentials returns 200 OK
- Severity: low
- Request: `curl -X POST http://localhost:3004/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"nope"}'`
- Expected: 401 (or 400 for an empty body), so clients can detect a failed login from the status code.
- Actual: 200 `{"reason":"Bad credentials"}`. The same for `{}` and for `"username":"ADMIN"`.
- Reproduced: 3 times.

## Questions
- The name filter is case-sensitive: `?firstname=zelda&lastname=qwerty` returns `[]`, while `Zelda/Qwerty` returns the booking. The docs' example uses lowercase `sally`/`brown`, which hints at case-insensitive matching, but the docs never state it.
- Seed booking 1 has no `additionalneeds` field, but the docs list it as not optional in the GET response. Possibly fine for seed data.
- Tokens don't seem to expire or get replaced: the first token still worked after a new one was issued. I did not test expiry over time.
- DELETE and ping return 201 Created, as the response example shows, but the docs' section header says "Success 200". The docs contradict themselves; 201 is an odd code for a delete either way.
- The docs' PATCH examples use `curl -X PUT`. This is a documentation error, not tested as an API bug.
- `depositpaid:"yes"` was coerced to `true`. This is related to F2: the API seems to treat any non-empty value as true.
- Not tested: whether XML or urlencoded input with a missing field also gives a 500, and how the API handles very large payloads (my one attempt was not run).

## Coverage
- Charter 1 (Saboteur, auth): 14 requests. No auth bypass found. Missing, empty, forged, prefix-only and Bearer tokens, a wrong or empty Basic password and a different Basic user were all rejected with 403. Valid cookie and Basic auth both worked.
- Charter 2 (FedEx, lifecycle): ~25 requests. POST in JSON, urlencoded and XML; GET in JSON and XML; list filters; PATCH, PUT and DELETE. This found F1, F3, F4 and F10, plus the urlencoded side of F2.
- Charter 3 (Antisocial, validation): ~15 requests. This found F6, F7, F8 and F9, and the JSON-string side of F2. PUT validation (missing bookingdates) correctly returns 400.
- Charter 4 (Guidebook): ~12 requests. Ping returns 201, a non-numeric id returns 404, the XML POST example works. This found F5 and the XML side of F2.
- Charter 5 (Obsessive-compulsive): ~8 requests. Double DELETE gives 405, an old token can be reused, and retrying after F5 creates duplicate bookings.
- No new charters added. The "write happens despite an error response" risk from F5 was folded into Charter 5.
- Not covered: very large or unicode inputs, XML/urlencoded validation errors, concurrent updates, token expiry, extra or unknown fields, HTTP method override, and urlencoded nested PATCH.
- Requests used: 75 of 80.
