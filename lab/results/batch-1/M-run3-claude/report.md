# Prediction report

## Findings
### F1: POST /auth with wrong credentials returns 200 instead of 401
- Expected wrong behaviour: `{"username":"admin","password":"wrong"}` returns HTTP 200 with body `{"reason":"Bad credentials"}`, not a 401/403.
- Why: from prior knowledge. This API is Restful-Booker, which is known to do this.
- Confidence: high

### F2: POST /auth with missing or empty fields returns 200 instead of 400
- Expected wrong behaviour: `{}`, a missing password, or a non-JSON body returns 200 `{"reason":"Bad credentials"}` (or a 500) instead of a 400 validation error.
- Why: from prior knowledge (Restful-Booker).
- Confidence: medium

### F3: DELETE /booking/:id returns 201 Created on success
- Expected wrong behaviour: a successful delete returns `201 Created` with body "Created", not 200/204. The docs even mix the two up ("Success 200" table, 201 example).
- Why: from the docs and prior knowledge.
- Confidence: high

### F4: GET /ping returns 201 Created instead of 200
- Expected wrong behaviour: the health check returns `201 Created`.
- Why: from the docs (example shows 201) and prior knowledge.
- Confidence: high

### F5: PUT/PATCH/DELETE on a booking id that doesn't exist returns 405 instead of 404
- Expected wrong behaviour: with a valid token, `PUT /booking/999999`, `PATCH /booking/999999` or `DELETE /booking/999999` returns `405 Method Not Allowed`, not 404.
- Why: from prior knowledge (Restful-Booker).
- Confidence: high

### F6: Deleting an already-deleted booking returns 405 instead of 404
- Expected wrong behaviour: a second DELETE on the same id returns 405 Method Not Allowed.
- Why: from prior knowledge.
- Confidence: high

### F7: Missing or invalid auth on PUT/PATCH/DELETE returns 403 instead of 401
- Expected wrong behaviour: no Cookie/Authorization header, or a bad token, returns `403 Forbidden` and no `WWW-Authenticate` header, where 401 is correct.
- Why: from prior knowledge.
- Confidence: medium

### F8: POST /booking with missing required fields returns 500 instead of 400
- Expected wrong behaviour: leaving out `firstname`, `totalprice` or `bookingdates`, or sending `{}`, gives `500 Internal Server Error` rather than a 400 validation error.
- Why: from prior knowledge (Restful-Booker validation throws a server error).
- Confidence: high

### F9: PUT /booking/:id with an incomplete body returns 400 or 500 inconsistently, or partially accepts it
- Expected wrong behaviour: a PUT missing required fields returns a 400/500 with no useful message; it may also accept a missing `additionalneeds`.
- Why: from prior knowledge.
- Confidence: medium

### F10: POST/PUT accept wrong types (no type validation)
- Expected wrong behaviour: `"totalprice":"abc"`, `"depositpaid":"yes"`, or a number for `firstname` is accepted with 200 and stored coerced (e.g. totalprice becomes null/NaN, depositpaid becomes true), instead of a 400.
- Why: from prior knowledge.
- Confidence: medium

### F11: Invalid dates are stored as garbage
- Expected wrong behaviour: `"checkin":"not-a-date"` or `"2018-13-45"` is accepted, and GET returns `"0NaN-aN-aN"` or a shifted date instead of the request being rejected with 400.
- Why: from prior knowledge (Restful-Booker date formatting).
- Confidence: high

### F12: Checkout before checkin is accepted
- Expected wrong behaviour: `checkin=2020-01-10, checkout=2020-01-01` creates the booking with 200.
- Why: from prior knowledge; there is no cross-field validation.
- Confidence: high

### F13: Negative or zero totalprice accepted, decimals truncated
- Expected wrong behaviour: `"totalprice":-100` is accepted, and `111.99` is stored and returned as `111` (or rounded).
- Why: from prior knowledge.
- Confidence: medium

### F14: GET /booking/:id for a non-existent or non-numeric id returns plain-text 404 or 500
- Expected wrong behaviour: `/booking/999999` returns 404 with plain-text "Not Found" whatever the Accept header says. `/booking/abc` may return 404 or 500 rather than 400.
- Why: from prior knowledge.
- Confidence: medium

### F15: Unsupported Accept header returns 418 I'm a Teapot
- Expected wrong behaviour: `Accept: text/plain` (or another unsupported type) on GET/POST/PUT returns `418` rather than `406 Not Acceptable`.
- Why: from prior knowledge (Restful-Booker).
- Confidence: high

### F16: Unsupported Content-Type on POST/PUT returns 500 or 418 instead of 415
- Expected wrong behaviour: `Content-Type: text/plain` or a missing Content-Type on POST /booking gives 500 (or 418), not 415. Malformed JSON gives 400 with an HTML/stack-trace body, or 500.
- Why: from prior knowledge.
- Confidence: medium

### F17: GET /booking date filters use the wrong comparison
- Expected wrong behaviour: `?checkin=X` leaves out bookings whose checkin equals X (uses `>` rather than `>=`). `?checkout=X` behaves inconsistently with the docs (uses `<`/`<=`, or leaves out equal dates).
- Why: from the docs (>= semantics stated) and prior knowledge of Restful-Booker filter quirks.
- Confidence: medium

### F18: GET /booking name filter is case-sensitive
- Expected wrong behaviour: `?firstname=sally&lastname=brown` (lowercase, as in the docs example) does not match a booking stored as "Sally Brown".
- Why: from the docs (example uses lowercase) and prior knowledge.
- Confidence: medium

### F19: Invalid filter values are ignored or cause a 500
- Expected wrong behaviour: `?checkin=garbage` returns all bookings or a 500 instead of a 400. Unknown query params are silently ignored.
- Why: from prior knowledge.
- Confidence: low

### F20: PATCH with a partial bookingdates replaces the whole sub-object
- Expected wrong behaviour: `PATCH {"bookingdates":{"checkin":"2020-01-01"}}` wipes out `checkout` (null or missing in the response), where it should merge.
- Why: from prior knowledge; a shallow merge is common.
- Confidence: medium

### F21: PATCH accepts wrong types and invalid values with no validation
- Expected wrong behaviour: `PATCH {"totalprice":"abc"}` or `{"depositpaid":"x"}` returns 200 and corrupts the stored booking.
- Why: from prior knowledge.
- Confidence: medium

### F22: PATCH/PUT can change or inject fields not in the schema, e.g. bookingid
- Expected wrong behaviour: extra fields (e.g. `"bookingid":5`, `"foo":"bar"`) are stored and echoed back in later GETs.
- Why: from prior knowledge.
- Confidence: low

### F23: Auth tokens never expire, and old tokens stay valid
- Expected wrong behaviour: a token from POST /auth keeps working indefinitely, and every call to /auth issues a new token without revoking the old ones.
- Why: from prior knowledge.
- Confidence: medium

### F24: Basic auth accepted with weak, hard-coded credentials
- Expected wrong behaviour: `Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=` (admin:password123) is hard-coded and public in the docs. Malformed Basic headers may return 500 rather than 403.
- Why: from the docs.
- Confidence: medium

### F25: Unsanitised input is stored and reflected (XSS / injection)
- Expected wrong behaviour: `firstname: "<script>alert(1)</script>"` is stored and returned verbatim, and in the XML response it is unescaped or breaks the XML. Very long strings are accepted.
- Why: from prior knowledge.
- Confidence: medium

### F26: POST /booking returns 200 instead of 201 Created
- Expected wrong behaviour: a successful create returns 200 with no Location header.
- Why: from the docs (Success 200) and REST conventions.
- Confidence: high

### F27: Inconsistent XML response root and format
- Expected wrong behaviour: POST with `Accept: application/xml` returns `<created-booking>`, while GET returns `<booking>` with no XML declaration. Booleans/numbers come back as strings in XML, and the urlencoded responses use a different shape.
- Why: from the docs.
- Confidence: low

### F28: Accept header missing defaults inconsistently
- Expected wrong behaviour: GET /booking/:id with no Accept header, or `Accept: */*`, returns 418 or an unexpected format instead of defaulting to JSON.
- Why: from prior knowledge.
- Confidence: low

### F29: additionalneeds actually optional (docs say required)
- Expected wrong behaviour: POST without `additionalneeds` succeeds with 200, which contradicts the docs marking it required.
- Why: from prior knowledge.
- Confidence: medium

### F30: Large or non-integer ids handled badly
- Expected wrong behaviour: `GET /booking/1.5`, `/booking/-1` or `/booking/99999999999999999999` returns 500 or matches an unexpected booking instead of 404/400.
- Why: from prior knowledge.
- Confidence: low

## Questions

## Coverage
Based on every endpoint in api.md: POST /auth, GET /booking/:id, POST /booking, PUT /booking/:id, PATCH /booking/:id, DELETE /booking/:id, GET /booking (filters) and GET /ping. That includes the header tables (Accept, Content-Type, Cookie, Authorization), the request and response field tables, and the documented status-code examples. I recognised this API as Restful-Booker, so I also drew on known behaviour of that project.
