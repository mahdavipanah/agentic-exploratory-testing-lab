# Prediction report

## Findings
### F1: POST /auth with wrong credentials returns 200 instead of 401
- Expected wrong behaviour: `{"username":"admin","password":"wrong"}` (or an empty body) returns HTTP 200 with `{"reason":"Bad credentials"}`. No 401 status and no token.
- Why: from prior knowledge. This looks like Restful-Booker, which behaves this way.
- Confidence: high

### F2: POST /auth with missing or malformed body still returns 200
- Expected wrong behaviour: `{}`, missing fields, non-string username/password or invalid JSON returns 200 "Bad credentials" (or a 400 HTML error page for broken JSON) instead of a validation error.
- Why: from prior knowledge
- Confidence: medium

### F3: DELETE /booking/:id returns 201 Created instead of 200/204
- Expected wrong behaviour: a successful delete returns `201 Created` with body "Created".
- Why: from the docs (the success block is labelled 200 but shows 201) and from prior knowledge
- Confidence: high

### F4: GET /ping returns 201 Created instead of 200
- Expected wrong behaviour: the health check returns 201.
- Why: from the docs (labelled 200, example shows 201)
- Confidence: high

### F5: PUT/PATCH/DELETE without auth or with a bad token return 403 instead of 401
- Expected wrong behaviour: a missing Cookie/Authorization header, an invalid token or wrong Basic credentials all give `403 Forbidden`. A missing authentication should give 401.
- Why: from prior knowledge
- Confidence: high

### F6: PUT /booking/:id on a non-existent id returns 405 Method Not Allowed
- Expected wrong behaviour: an authenticated PUT to /booking/999999 returns 405 instead of 404.
- Why: from prior knowledge
- Confidence: high

### F7: PATCH /booking/:id on a non-existent id returns 405 (or 200/500)
- Expected wrong behaviour: an authenticated PATCH to a missing id returns 405 instead of 404.
- Why: from prior knowledge
- Confidence: medium

### F8: DELETE /booking/:id on a non-existent or already-deleted id returns 405
- Expected wrong behaviour: deleting a missing id returns 405 Method Not Allowed instead of 404. Deleting the same id twice gives 201 then 405.
- Why: from prior knowledge
- Confidence: high

### F9: POST /booking with missing required fields returns 500 instead of 400
- Expected wrong behaviour: omitting firstname, totalprice or bookingdates, or sending `{}`, returns `500 Internal Server Error`.
- Why: from prior knowledge. Restful-Booker throws on undefined fields.
- Confidence: high

### F10: POST /booking accepts wrong types without validation
- Expected wrong behaviour: `"totalprice":"abc"` gives 500 or stores null/NaN. `"depositpaid":"no"` is coerced to true. `"firstname":123` is accepted and stored. None of these give a 400.
- Why: from prior knowledge, plus the lack of any documented validation
- Confidence: medium

### F11: Invalid dates are accepted and stored as garbage
- Expected wrong behaviour: `"checkin":"not-a-date"` or `"2018-13-45"` returns 200 with `"0NaN-aN-aN"` or `"Invalid date"` in the booking instead of a 400.
- Why: from prior knowledge
- Confidence: high

### F12: checkout earlier than checkin is accepted
- Expected wrong behaviour: POST/PUT with `checkin=2019-01-01` and `checkout=2018-01-01` returns 200 and stores the booking.
- Why: from prior knowledge (no cross-field validation)
- Confidence: high

### F13: Negative or zero totalprice is accepted
- Expected wrong behaviour: `"totalprice":-100` is stored without error.
- Why: from prior knowledge
- Confidence: high

### F14: Decimal totalprice is truncated or rounded
- Expected wrong behaviour: `"totalprice":111.99` is returned as 111 (or 112).
- Why: from prior knowledge (Restful-Booker parses as integer)
- Confidence: medium

### F15: GET /booking?checkin= filter is exclusive or wrong instead of >=
- Expected wrong behaviour: a booking whose checkin equals the filter date is missing from the results, because the filter uses > instead of >=.
- Why: from prior knowledge plus the docs (">= " semantics are documented)
- Confidence: medium

### F16: GET /booking?checkout= filter uses the wrong comparison direction
- Expected wrong behaviour: the docs say checkout >= filter, but the implementation returns bookings with checkout < (or <=) the filter date. A booking with exactly the same checkout date may also be excluded.
- Why: from the docs (the documented semantics are odd) and prior knowledge
- Confidence: medium

### F17: firstname/lastname filters are case-sensitive, so the documented example fails
- Expected wrong behaviour: `GET /booking?firstname=sally&lastname=brown` (the docs example) returns `[]` for a booking stored as "Sally Brown".
- Why: from the docs (example uses lowercase while the data uses capitals)
- Confidence: medium

### F18: Invalid date format in the checkin/checkout query returns 500 or ignores the filter
- Expected wrong behaviour: `GET /booking?checkin=abc` returns 500, or all ids, instead of 400.
- Why: from prior knowledge
- Confidence: medium

### F19: GET /booking/:id with an unknown or non-numeric id
- Expected wrong behaviour: an unknown id returns 404 with plain-text "Not Found" rather than a JSON error. A non-numeric id (`/booking/abc`) may return 500 or 404 instead of 400.
- Why: from prior knowledge
- Confidence: medium

### F20: An unsupported Accept header returns 418 I'm a teapot
- Expected wrong behaviour: `Accept: text/plain` (or another unsupported type) on GET /booking/:id or POST /booking returns 418 instead of 406.
- Why: from prior knowledge (well-known Restful-Booker behaviour)
- Confidence: high

### F21: An unsupported or missing Content-Type on POST/PUT returns 500 or 418 instead of 415
- Expected wrong behaviour: `Content-Type: text/plain` on POST /booking returns 500 or 418 rather than 415/400.
- Why: from prior knowledge
- Confidence: medium

### F22: URL-encoded bodies and responses are supported, though the docs say only JSON/XML
- Expected wrong behaviour: `application/x-www-form-urlencoded` is accepted, which contradicts the header table. Values such as `totalprice` and `depositpaid` come back as strings ("111", "true"), so types are lost.
- Why: from the docs (inconsistency between the examples and the header tables)
- Confidence: medium

### F23: Malformed JSON or XML body returns 500 or an HTML error page
- Expected wrong behaviour: a broken JSON or XML body on POST/PUT returns 400 with an HTML stack trace, or 500.
- Why: from prior knowledge (Express body-parser defaults)
- Confidence: medium

### F24: PUT /booking/:id with a partial body
- Expected wrong behaviour: a missing field returns 400 with an unclear body, or 500. It may also store undefined fields.
- Why: from prior knowledge
- Confidence: low

### F25: PATCH with bookingdates containing only checkin wipes checkout
- Expected wrong behaviour: `{"bookingdates":{"checkin":"2020-01-01"}}` replaces the whole bookingdates object, so checkout is dropped, nulled or becomes an invalid date.
- Why: from prior knowledge (shallow merge)
- Confidence: medium

### F26: PATCH accepts an empty body, unknown fields and invalid types
- Expected wrong behaviour: `{}` returns 200 without changes. `{"totalprice":"abc"}` is stored or causes a 500. Unknown fields are silently ignored.
- Why: from prior knowledge
- Confidence: medium

### F27: Auth tokens never expire and are not invalidated
- Expected wrong behaviour: a token from POST /auth works indefinitely. Every call to /auth issues a new token, and all of them stay valid.
- Why: from prior knowledge
- Confidence: medium

### F28: Hard-coded Basic auth credentials and no brute-force protection on /auth
- Expected wrong behaviour: admin/password123 (published in the docs) always works. Unlimited failed /auth attempts are allowed and none are rate limited.
- Why: from the docs and prior knowledge
- Confidence: high

### F29: Stored XSS/injection in string fields
- Expected wrong behaviour: `firstname: "<script>alert(1)</script>"` or very long strings are stored and returned unescaped. There is no length limit.
- Why: from prior knowledge
- Confidence: medium

### F30: XML response escaping and inconsistent root elements
- Expected wrong behaviour: values containing `<` or `&` are not escaped in XML output, so the XML is malformed. The created-booking XML response may lack the declaration, or vice versa.
- Why: from the docs and prior knowledge
- Confidence: low

### F31: Duplicate bookings are allowed
- Expected wrong behaviour: posting an identical booking twice creates two bookings with different ids.
- Why: from prior knowledge
- Confidence: low

### F32: POST /booking returns 200 instead of 201
- Expected wrong behaviour: creation returns `200 OK` rather than `201 Created`, while DELETE (which doesn't create anything) returns 201.
- Why: from the docs
- Confidence: high

### F33: Extra or unknown fields in POST /booking are silently ignored or echoed
- Expected wrong behaviour: unknown properties are accepted without error. They may be stored and echoed back.
- Why: from prior knowledge
- Confidence: low

### F34: Token is accepted in places that don't match the docs
- Expected wrong behaviour: `Authorization: Bearer <token>` is not accepted (403), and only Cookie works for tokens. Basic auth with different case or extra whitespace may give a 500.
- Why: from prior knowledge
- Confidence: low

## Questions

## Coverage
I based the predictions on every endpoint in the docs:
- POST /auth
- GET /booking/:id
- POST /booking (JSON, XML and URL-encoded)
- PUT /booking/:id
- PATCH /booking/:id
- DELETE /booking/:id
- GET /booking with its firstname/lastname/checkin/checkout filters
- GET /ping

I also used the header tables (Accept, Content-Type, Cookie, Authorization) and the documented status codes. I recognise this API as Restful-Booker and drew on its known behaviour.
