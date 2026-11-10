Explore this API using the four charters below. Each charter follows Elisabeth Hendrickson's template: *Explore (target) with (resources) to discover (information).*

Spend about 20 requests on each charter, in order. Within a charter, follow what you learn: when something looks odd, dig into it before moving on. Copy the charters into the Charters section of your report.

1. **Explore** the booking lifecycle (create, read, full update, partial update, delete, then read again) **with** JSON payloads and the admin token **to discover** whether every step does what the docs say and returns the documented status code. *Tour: Guidebook.*
2. **Explore** one booking's data across every endpoint and format (JSON, XML, URL-encoded; different Accept and Content-Type pairs) **with** a single distinctive booking **to discover** data that changes, disappears or is formatted differently along the way. *Tour: FedEx.*
3. **Explore** create, full update and partial update **with** bad and boundary data (missing or extra fields, wrong types, negative or huge prices, checkout before checkin, invalid dates, very long and non-ASCII names) **to discover** what the API wrongly accepts and what it rejects badly. *Tour: Antisocial.*
4. **Explore** authorization and search **with** no credentials, wrong tokens, Basic auth versus cookie, unknown ids, and the GET /booking filters **to discover** who can change what, and whether search follows the docs. *Tours: Saboteur and Back alley.*

> Written by the experimenter from the API docs only, before reading the server's source code.

{{TOURS}}
