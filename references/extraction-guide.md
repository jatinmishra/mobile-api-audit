# Extraction Guide

Full checklist of every signal to extract from each input type before scoring.

---

## OpenAPI / Swagger

### Identity
- `info.title` → API name
- `info.version` → current version
- `info.description` → purpose
- `servers[0].url` → base URL, extract version segment (e.g. `/v2/`)
- `externalDocs.url` → documentation link

### Endpoints
For each path + method combination:
- HTTP method (GET, POST, PUT, PATCH, DELETE)
- Path parameters
- Query parameters — **record exact names**, look for:
  - Pagination: `offset`, `limit`, `page`, `cursor`, `after`, `before`, `next_cursor`, `page_token`, `starting_after`
  - Filtering: `fields`, `include`, `select`, `expand`
  - Locale: `locale`, `lang`, `language`
- Request body schema — shape, required fields
- Response schema for 200/201 — field count, nesting depth, any large arrays
- Response schemas for 4xx/5xx — consistent structure? Fields: `code`, `message`, `error`, `request_id`

### Security
- `components.securitySchemes` — type: `oauth2`, `http` (bearer/basic), `apiKey`
- OAuth2 flows and scopes defined
- Which endpoints require which scopes
- `security` at root (global) vs per-endpoint

### Headers
Look for these response headers defined in any operation's `responses`:
- `Cache-Control`, `ETag`, `Last-Modified`, `Vary`
- `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- `Retry-After`
- `Sunset`, `Deprecation`
- `X-Request-Id`, `X-Trace-Id`
- `Content-Encoding` (gzip/br support)

### Extensions (x- fields)
- `x-rateLimit`, `x-throttling` — custom rate limit docs
- `x-deprecated`, `x-sunset` — deprecation markers
- `x-pagination` — pagination metadata
- Any mobile-specific extensions

### Versioning signals
- Version in path: `/v1/`, `/v2/`, `/api/v3/`
- Version in header: `API-Version`, `X-API-Version`
- Version query param: `?version=`
- `deprecated: true` on any operations

---

## HAR Files

### Latency (compute from `entries[].time`, in ms)
- p50 (median)
- p95 (95th percentile)
- p99 if enough samples
- Min and max
- Flag any request > 1000 ms

### Payload sizes (from `entries[].response.content.size`, in bytes)
- p50 and p95 response sizes
- Convert to KB: size / 1024
- Flag any response > 200 KB
- Note the endpoint for the largest response

### Request headers observed
From `entries[].request.headers[]`:
- `Authorization` → value prefix: `Bearer ` (JWT/OAuth), `Basic ` (session), `ApiKey ` / `X-API-Key`
- `Accept-Encoding` → gzip, br, deflate
- `Accept-Language` → locale values
- `Content-Type`
- `X-Request-Id`, `Idempotency-Key`

### Response headers observed
From `entries[].response.headers[]`:
- `Cache-Control` → record exact value
- `Content-Encoding` → actual compression used
- `ETag`, `Last-Modified`
- `Vary`
- `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- `Retry-After`
- `Sunset`, `Deprecation`
- `Strict-Transport-Security` → HTTPS enforced
- `X-Request-Id`, `X-Trace-Id`

### Response bodies (from `entries[].response.content.text`)
Parse any available JSON responses:
- Pagination keys: `cursor`, `next_cursor`, `next_page`, `has_more`, `total`, `offset`, `limit`
- Error shape: look for `code`, `message`, `error`, `errors[]`, `request_id`
- Data shape: field count, nesting, presence of large embedded arrays
- Auth tokens in body (security risk)

### Status codes observed
From `entries[].response.status`:
- List all unique status codes
- Note any 4xx or 5xx responses
- Check: is 429 present? (rate limiting works)
- Check: are there 401s? (auth failure observed)

### URL patterns
From `entries[].request.url`:
- Version segment in path
- Query parameters actually used in real traffic
- Any sensitive data in query params (tokens, PII)

---

## cURL Commands

Parse each `curl` command:

### URL
- Base URL → extract host and version segment
- Path → endpoint name and parameters
- Query string → parameter names and example values

### Headers (`-H "..."`)
- `Authorization: Bearer ...` → token-based auth
- `Authorization: Basic ...` → basic/session auth
- `X-API-Key: ...` → API key auth
- `Accept-Encoding: gzip, br` → compression requested
- `Accept-Language: fr-FR` → localisation
- `Content-Type: application/json`
- `Idempotency-Key: ...` → idempotency support
- `X-Request-Id: ...`

### Method (`-X` or inferred)
- GET → should be retry-safe
- POST → check for idempotency key
- PUT/PATCH/DELETE → check for idempotency

### Request body (`-d`, `--data`, `--data-raw`)
- Shape of request payload
- Fields sent

---

## Signal confidence levels

When reporting findings, note confidence:

| Confidence | Meaning | When to use |
|-----------|---------|-------------|
| `confirmed` | Directly observed in input | Header present in HAR, param in OpenAPI |
| `inferred` | Reasonable inference from indirect evidence | No `cursor` param → likely offset pagination |
| `not found` | Signal absent from all inputs | Feature may exist but not documented/captured |
| `n/a` | Not applicable to this API type | RTM for a batch-only API |

Use `confirmed` only when you have a direct reference. Use `inferred` for logical conclusions. Use `not found` when you've looked and can't find it. Never leave a finding blank.
