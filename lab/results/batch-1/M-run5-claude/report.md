# Prediction report

## Findings
### F1: DELETE /booking/:id returns 201 Created instead of 200/204
- Expected wrong behaviour: A successful delete with a valid token or Basic auth returns `HTTP 201 Created` with body "Created". This is the wrong status code for a deletion.
- Why: from the docs (the response table says "Success 200", but the example and description say "Default HTTP 201 response"). I also recognise this from Restful-Booker.
- Confidence: high

### F2: GET /ping returns 201 Created instead of 200 OK
- Expected wrong behaviour: The health check returns 201 Created, but nothing was created.
- Why: from the docs (the example shows 201 under the "Success 200" heading). I also know Restful-Booker does this.
- Confidence: high

### F3: POST /auth with bad credentials returns 200 OK instead of 401
- Expected wrong behaviour: Sending a wrong username or password, or an empty body, returns `200 {"reason":"Bad credentials"}` instead of a 401/400 error status.
- Why: from prior knowledge of Restful-Booker
- Confidence: high

### F4: POST /booking with missing required fields returns 500 instead of 400
- Expected wrong behaviour: Leaving out e.g. `firstname`, `totalprice` or the `bookingdates` object (or sending `{}`) returns 500 Internal Server Error, sometimes with an empty body, instead of a 400 validation error.
- Why: from prior knowledge (Restful-Booker returns 500 for invalid payloads)
- Confidence: high

### F5: POST/PUT /booking does not check field types
- Expected wrong behaviour: `totalprice: "abc"`, `depositpaid: "yes"` and `firstname: 123` are accepted (200) and get coerced or stored. A non-numeric totalprice may come back as null/NaN, and a string depositpaid may be coerced to true.
- Why: from prior knowledge, plus the docs mention no validation rules
- Confidence: medium

### F6: Invalid dates are accepted and stored as garbage
- Expected wrong behaviour: Sending `bookingdates.checkin: "not-a-date"` or `"2018-13-45"` returns 200 with `"0NaN-aN-aN"` (or an invalid/rolled-over date) instead of a 400.
- Why: from prior knowledge of Restful-Booker's date formatting
- Confidence: medium

### F7: A checkout date before the checkin date is accepted
- Expected wrong behaviour: POST/PUT with checkout `2018-01-01` and checkin `2019-01-01` succeeds with 200.
- Why: from prior knowledge, and the docs describe no cross-field validation
- Confidence: high

### F8: Negative or zero totalprice is accepted
- Expected wrong behaviour: `totalprice: -100` is stored and returned with 200.
- Why: from prior knowledge, and the docs describe no validation
- Confidence: medium

### F9: Decimal totalprice is truncated or rounded
- Expected wrong behaviour: `totalprice: 111.99` comes back as 111 (or 112), so the value is silently changed.
- Why: from prior knowledge (Restful-Booker stores totalprice as an integer)
- Confidence: low

### F10: Empty strings for firstname/lastname are accepted
- Expected wrong behaviour: `firstname: ""` is accepted with 200 and creates a booking without a name.
- Why: from prior knowledge, and the docs describe no validation
- Confidence: medium

### F11: GET /booking checkin filter is exclusive (>) rather than >= as documented
- Expected wrong behaviour: `GET /booking?checkin=2018-01-01` does not return bookings whose checkin is exactly 2018-01-01.
- Why: from the docs (they promise "greater than or equal"), and from prior knowledge that Restful-Booker's filter uses a strict comparison
- Confidence: medium

### F12: GET /booking checkout filter uses the wrong comparison direction or boundary
- Expected wrong behaviour: `GET /booking?checkout=2019-01-01` returns bookings with checkout before the date, or leaves out bookings with checkout exactly on the date, which contradicts the documented ">=".
- Why: from the docs (">=" is promised) and from prior knowledge (the implementation compares checkout with less-than / strict)
- Confidence: medium

### F13: Name filters are case-sensitive, contrary to the docs example
- Expected wrong behaviour: `GET /booking?firstname=sally&lastname=brown` returns `[]` for a booking stored as "Sally Brown".
- Why: from the docs (the example uses lowercase names while the stored data is capitalised)
- Confidence: medium

### F14: Invalid date format in the filter is not rejected
- Expected wrong behaviour: `GET /booking?checkin=foo` returns 200 with all or no results (or 500) instead of a 400, even though the docs say "Format must be CCYY-MM-DD".
- Why: from the docs and prior knowledge
- Confidence: medium

### F15: PUT/PATCH/DELETE on a non-existent id returns 405 Method Not Allowed instead of 404
- Expected wrong behaviour: `PUT /booking/999999` or `DELETE /booking/999999` with valid auth returns 405.
- Why: from prior knowledge of Restful-Booker
- Confidence: high

### F16: PUT/PATCH/DELETE with missing or invalid auth returns 403 instead of 401
- Expected wrong behaviour: Without a Cookie or Authorization header, or with `token=bogus`, the response is `403 Forbidden` rather than 401 Unauthorized.
- Why: from prior knowledge
- Confidence: medium

### F17: Auth tokens never expire, are reusable, and stay valid indefinitely
- Expected wrong behaviour: A token from POST /auth keeps working for as long as the server runs. Tokens are short (15 chars) and there is no logout or revocation.
- Why: from prior knowledge
- Confidence: low

### F18: Hard-coded default credentials admin/password123 work
- Expected wrong behaviour: Basic auth `admin:password123` (shown in the docs) grants full update/delete access. The credentials are published and cannot be changed.
- Why: from the docs
- Confidence: high

### F19: GET /booking/:id with a non-numeric id returns 500 or 404 inconsistently
- Expected wrong behaviour: `GET /booking/abc` returns a 500 or a plain-text "Not Found" instead of a 400. Non-existent ids return a plain-text 404 body even when JSON is requested.
- Why: from the docs (id is typed as String for GET but Number elsewhere) and from prior knowledge
- Confidence: medium

### F20: An unsupported Accept header returns 418 I'm a teapot
- Expected wrong behaviour: `Accept: text/plain` (or any unsupported type) on GET/POST /booking returns 418 instead of 406.
- Why: from prior knowledge of Restful-Booker
- Confidence: high

### F21: An unsupported Content-Type returns 500 (or is processed as empty) instead of 415
- Expected wrong behaviour: POST /booking with `Content-Type: text/plain` returns 500 or creates a booking with empty fields.
- Why: from prior knowledge
- Confidence: medium

### F22: Malformed JSON body returns 500 or an HTML error page instead of 400
- Expected wrong behaviour: Sending `{"firstname":` produces an Express HTML stack trace or a 500 (or a 400 with an HTML body).
- Why: from prior knowledge (Express body-parser default error handling)
- Confidence: medium

### F23: PATCH with a partial bookingdates object wipes the sibling date
- Expected wrong behaviour: `PATCH {"bookingdates":{"checkout":"2020-01-01"}}` replaces the whole bookingdates object, so `checkin` is lost (or becomes null/NaN).
- Why: from prior knowledge (a shallow merge of nested objects)
- Confidence: medium

### F24: PATCH accepts invalid types or nulls and corrupts the stored booking
- Expected wrong behaviour: `PATCH {"totalprice":"abc"}` or `{"firstname":null}` returns 200 and stores invalid data.
- Why: from prior knowledge
- Confidence: medium

### F25: PUT with a partial body returns 400 inconsistently, or 500
- Expected wrong behaviour: A PUT that leaves out a required field returns 400 Bad Request in some cases and 500 in others, rather than consistent validation.
- Why: from prior knowledge
- Confidence: low

### F26: additionalneeds is documented as required but is optional
- Expected wrong behaviour: POST without `additionalneeds` succeeds and the response leaves the field out. This contradicts the docs, which say it is required in both the request and the response.
- Why: from the docs and prior knowledge
- Confidence: medium

### F27: Unknown extra fields are silently ignored or stored
- Expected wrong behaviour: POST with `{"isAdmin":true, ...}` is accepted without error.
- Why: from prior knowledge
- Confidence: low

### F28: URL-encoded responses do not include additionalneeds
- Expected wrong behaviour: With `Accept: application/x-www-form-urlencoded` the response leaves out `additionalneeds` (as the docs examples show), so data is lost. This Accept value is also not listed as supported, yet it is used.
- Why: from the docs (the URL Response examples have no additionalneeds)
- Confidence: low

### F29: The XML response root is inconsistent between create and get/update
- Expected wrong behaviour: POST returns a `<created-booking>` root with an XML declaration, while GET/PUT return `<booking>` without one.
- Why: from the docs
- Confidence: low

### F30: Very long strings or huge numbers are accepted without limits
- Expected wrong behaviour: A 100k-character firstname or a totalprice of 1e308 is accepted, or a huge totalprice causes a 500.
- Why: from prior knowledge, and the docs give no limits
- Confidence: low

### F31: GET /booking/:id for a deleted booking returns a plain-text 404 body
- Expected wrong behaviour: After DELETE, GET returns 404 with the text "Not Found", not JSON. A second DELETE returns 405.
- Why: from prior knowledge
- Confidence: medium

### F32: XSS/HTML in fields is stored and reflected without escaping
- Expected wrong behaviour: `firstname: "<script>alert(1)</script>"` is stored and returned unchanged. In XML responses, special characters may break the XML or cause a 500.
- Why: from prior knowledge
- Confidence: low

## Questions

## Coverage
I used every endpoint in the docs: POST /auth, GET /booking/:id, POST /booking, PUT /booking/:id, PATCH /booking/:id, DELETE /booking/:id, GET /booking (with the firstname/lastname/checkin/checkout filters) and GET /ping. That includes the Content-Type and Accept headers, the Cookie and Basic auth options, the response examples (JSON/XML/URL-encoded) and the documented status codes. I also drew on prior knowledge of the Restful-Booker API, which this documentation matches.
