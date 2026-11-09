# Exploration report

## Charters

Risks (from the docs, ranked by client harm):
1. Auth on PUT/PATCH/DELETE: missing/invalid tokens or bad Basic creds accepted; wrong credentials still returning a token; auth applied inconsistently across verbs. (High: data loss/tampering.)
2. Input validation on POST/PUT: missing required fields, wrong types, negative price, checkout before checkin, invalid dates, huge payloads accepted or causing 500s. (High: corrupt data.)
3. Data fidelity: a booking created via JSON / XML / urlencoded and read back via JSON/XML is not identical (dates shifted, booleans/numbers coerced, PATCH dropping fields). (Medium-high.)
4. Search filters on GET /booking: checkin/checkout ">=" semantics, name case sensitivity, combined filters, malformed dates. (Medium.)
5. Lifecycle/idempotency: deleting twice, updating a deleted booking, unknown/non-numeric ids, status codes. (Medium.)

Charters (budget 80 requests):
- C1 (Saboteur tour, ~20 req): Explore auth on POST /auth, PUT, PATCH, DELETE with valid/invalid/absent tokens and Basic headers to discover whether any write succeeds without valid credentials.
- C2 (Antisocial tour, ~20 req): Explore POST/PUT /booking with missing, wrong-type, negative, huge and logically invalid fields to discover what invalid data the API stores or where it crashes.
- C3 (FedEx tour, ~15 req): Explore one booking through POST (JSON/XML/form), GET (JSON/XML), PATCH and PUT to discover whether data is altered in transit.
- C4 (Back alley tour, ~12 req): Explore GET /booking filters with name/date/combined/malformed values to discover whether search returns wrong subsets.
- C5 (Obsessive-compulsive tour, ~10 req): Explore delete/update/get sequences on the same id to discover inconsistent state and status codes.

## Findings

### F1: XML depositpaid=false is silently stored as true
- Severity: high
- Request: `curl -s -X POST http://localhost:3001/booking -H 'Content-Type: text/xml' -H 'Accept: application/json' -d '<booking><firstname>Dep</firstname><lastname>False</lastname><totalprice>50</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2020-05-05</checkin><checkout>2020-05-10</checkout></bookingdates></booking>'`
- Expected: `depositpaid` is a Boolean (docs line 201/216). `false` sent should be stored and returned as `false`, exactly as the equivalent JSON request does.
- Actual: 200 OK, body `{"bookingid":15,"booking":{...,"depositpaid":true,...}}`. The value flipped to `true`. Identical JSON POST (booking 16) correctly stored `false`. So any client that creates bookings via XML records every deposit as paid — a financial-state corruption.
- Reproduced: 2 (bookingid 14 and 15)

### F2: Invalid field types are silently coerced and garbage is stored
- Severity: high
- Request: `curl -s -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Co","lastname":"Erce","totalprice":"abc","depositpaid":"maybe","bookingdates":{"checkin":"bad","checkout":"2019-01-01"}}'`
- Expected: `totalprice` is Number, `depositpaid` Boolean, `checkin` Date (docs lines 200-203). Bad types should be rejected (400), not coerced.
- Actual: 200 OK, `{"bookingid":18,"booking":{...,"totalprice":null,"depositpaid":true,"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2019-01-01"}}}`. Price became `null`, the string "maybe" became boolean `true`, and the bad date was stored as the literal invalid value `0NaN-aN-aN`. The record persists and reads back corrupted.
- Reproduced: 2 (bookingid 13 and 18)

### F3: POST /booking with missing required fields returns 500, not 400
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Jim"}'`
- Expected: All body fields are documented as required ("Optional: no", docs lines 198-204). A missing required field should give a 4xx client error (400 Bad Request). PUT /booking with the same incomplete body correctly returns 400 — so the behaviour is also internally inconsistent.
- Actual: 500 Internal Server Error, body "Internal Server Error". The server throws instead of validating.
- Reproduced: 2

### F4: No business-rule validation — negative price and checkout-before-checkin accepted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg2","lastname":"P","totalprice":-999,"depositpaid":true,"bookingdates":{"checkin":"2025-01-01","checkout":"2020-01-01"}}'`
- Expected: A booking price should not be negative and checkout should not precede checkin. (Reasoning: these are logically impossible bookings; a client would never want them stored.)
- Actual: 200 OK, `{"bookingid":17,"booking":{...,"totalprice":-999,...,"bookingdates":{"checkin":"2025-01-01","checkout":"2020-01-01"}}}`. Stored as-is. (Docs are silent on validation, so this is a design weakness rather than a doc contradiction.)
- Reproduced: 2 (bookingid 12 and 17)

### F5: Malformed date in GET /booking query returns 500
- Severity: medium
- Request: `curl -s -o /dev/null -w "%{http_code}" "http://localhost:3001/booking?checkin=garbage"`
- Expected: `checkin` filter format "must be CCYY-MM-DD" (docs line 623). A bad value should yield 400 or be ignored — not crash the endpoint.
- Actual: 500 Internal Server Error. An unparseable date filter takes down the request.
- Reproduced: 2

### F6: PUT/DELETE to a non-existent booking id returns 405 instead of 404
- Severity: low
- Request: `curl -s -o /dev/null -w "%{http_code}" -X PUT http://localhost:3001/booking/88888 -H 'Content-Type: application/json' -H 'Cookie: token=07acd09c6a2768c' -d '{"firstname":"X","lastname":"Y","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2020-01-01","checkout":"2020-02-01"}}'`
- Expected: Updating/deleting a missing resource should be 404 Not Found (GET /booking/16 after deletion correctly returns 404).
- Actual: 405 Method Not Allowed (same for DELETE of an already-deleted id). Misleading status; a client cannot tell "method not supported" from "id gone".
- Reproduced: 2 for PUT (ids 99999, 88888), 1 for repeat DELETE (id 16)

## Questions
- Auth looks solid: PUT/PATCH/DELETE returned 403 for absent token, empty token (`token=`), bogus token, truncated-prefix token, `Bearer <token>`, wrong Basic creds, and `guest:password123`; only the valid Cookie token and the documented Basic header succeeded. POST /auth returns 200 with `{"reason":"Bad credentials"}` for wrong password and for a mis-cased username ("Admin") — a 200 for a failed login is unusual but did not leak a token. Not flagged as a finding since no unauthorized write occurred.
- XML and URL-encoded responses are served with `Content-Type: text/html; charset=utf-8` instead of `application/xml` / `application/x-www-form-urlencoded`. Could confuse strict clients; not confirmed as a contract breach.
- GET /booking name filters are case-sensitive (`firstname=DEP&lastname=falsej` returned `[]` while the stored value was `Dep/FalseJ`). Docs' own example uses lowercase "sally" — unclear whether case-insensitive matching is intended.
- `GET /ping` and `DELETE /booking/:id` return HTTP 201 (documented as such, odd for a GET/health check, but matches the docs so not flagged).

## Coverage
Explored all six endpoints. C1 Saboteur (auth) — covered thoroughly across PUT/PATCH/DELETE and POST /auth; no auth bypass found. C2 Antisocial (input validation) — found F2, F3, F4, F5. C3 FedEx (format fidelity) — found F1; JSON round-trips cleanly, XML read-back of an untouched booking was faithful. C4 Back alley (filters) — name and date filters work for valid input (correctly returned the single matching id); found F5 on malformed dates and the case-sensitivity question. C5 Obsessive-compulsive (lifecycle) — found F6 and confirmed delete→get→404.
Not covered: huge/oversized payloads, concurrent/double-submit POST duplication, PATCH field-dropping semantics in depth, urlencoded request body round-trip, XInclude/XXE in XML parsing. Requests used: 37 of 80.
