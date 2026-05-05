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
  - Named projections: `projection` (values like `list_v3`, `detail_v2`, `sync_v4`) — extraction only, not separately scored; informs field-filtering criterion in Dim 1
  - Locale: `locale`, `lang`, `language`
- Request body schema — shape, required fields, look for:
  - `operationId` or `clientId` → client-assigned operation identity (offline mutation pattern)
  - `idempotencyKey` or equivalent → mutation identity
  - `baseVersion`, `baseEtag`, `ifMatch` → optimistic concurrency fields (conflict detection)
- Response schema for 200/201 — field count, nesting depth, any large arrays, look for:
  - `id` field → stable resource identity
  - `version` field (integer or string counter) → **logical version** for sync and conflict detection. Prefer over `updatedAt` alone — timestamps break on clock drift and concurrent writes
  - `createdAt`, `updatedAt` → temporal metadata
  - `deletedAt` (nullable) → tombstone pattern; `null` = active, non-null = deleted
  - Mutation status in mutation responses: `status` field with values `accepted`, `applied`, `replayed`, `conflicted`, `rejected_validation`, `rejected_permission`, `blocked_auth`, `dependency_failed`, `processing`. Note: `accepted` ≠ `applied` — a client that treats them equivalently will show stale data
  - `operationId` echo in mutation responses → confirms server acknowledges client identity
  - `syncCursor` in mutation responses → optional sync hint after a write
- Response schemas for 4xx/5xx — consistent structure? Fields:
  - `code`, `message`, `error`, `request_id` — basic shape
  - `retryable` (boolean) → can the client safely retry this error?
  - `userActionRequired` (boolean) → does the user need to do something?
  - `queueAction` → what should a persistent operation queue do? Values: `retain`, `drop`, `modify`, `reauth`, `rebase`
  - `fields` → field-level validation errors
  - `conflict` → conflict payload (see Conflict signals below)

### Conflict signals
For error responses with 409 or 412 status, or `CONFLICT_*` codes:
- `conflict.clientBaseVersion` or equivalent → what version the client was editing from
- `conflict.serverVersion` → current server version
- `conflict.serverResource` → full current server state (allows client-side merge)
- `conflict.conflictingFields` → list of fields that conflict
- `conflict.mergeStrategy` → declared resolution approach
- `queueAction: rebase` → server signals client can replay operation on top of current state (meaningfully better than bare 409)
- Machine-readable `CONFLICT_*` code → `CONFLICT_RESOURCE_VERSION_MISMATCH`, `CONFLICT_CONCURRENT_EDIT`, etc.

### Sync signals
- Delta sync parameters: `cursor`, `syncToken`, `after`, `modifiedSince`, `changePosition`
- Opaque cursor: value is a non-interpretable string (base64, UUID, opaque token) → scores higher than timestamp
- Timestamp cursor: value is an ISO 8601 date string → lower score, broken by clock drift
- Sync response envelope: `changes[]` array with `type: upsert|delete`, `resourceType`, `id`, `version`
- `deletedAt` in sync change payloads → tombstone
- Access removal events: explicit `type: remove` or `access_revoked` events in sync response for records where permission was lost — absence of a record in a delta response does NOT constitute removal
- Cursor expiry error codes: `SYNC_CURSOR_EXPIRED`, `SYNC_CURSOR_INVALID`, `SYNC_CURSOR_INCOMPATIBLE`, `SYNC_CURSOR_REVOKED`
  - `SYNC_CURSOR_REVOKED` is the most critical — it is a security/auth reset and no retry resolves it; it requires full re-sync and pending-write preservation

### Security
- `components.securitySchemes` — type: `oauth2`, `http` (bearer/basic), `apiKey`
- OAuth2 flows and scopes defined
- Which endpoints require which scopes
- `security` at root (global) vs per-endpoint
- Step-up auth: look for `STEP_UP_REQUIRED` error code or step-up challenge descriptor in error schemas
- Session/device revocation: look for `SESSION_REVOKED` error code or documentation of what happens to queued mutations on session termination

### Headers
Look for these response headers defined in any operation's `responses`:
- `Cache-Control`, `ETag`, `Last-Modified`, `Vary`
- `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- `Retry-After`
- `Sunset`, `Deprecation`
- `X-Request-Id`, `X-Trace-Id`
- `Content-Encoding` (gzip/br support)

### Capabilities and version metadata
- Config or capabilities endpoint (`/v1/config`, `/v1/capabilities`, `/v1/session`, `/v1/me`):
  - `minimumSupportedApp` with `ios` and `android` version strings
  - `features` capability block with feature flags
  - Both count toward Dim 8 minimum supported app version criterion

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
- `Authorization` → value prefix: `Bearer ` (JWT/OAuth), `Basic ` (session), `ApiKey ` / `X-API-Key`. If the value is `[redacted]`, `[REDACTED]`, empty, or a placeholder string, check the OpenAPI spec for a `securitySchemes` definition. If the spec confirms an auth scheme, use that to score; set HAR auth status to `unknown` with note "redacted in capture — type inferred from spec." If no spec is available, set auth status to `unknown` (not 0) with note "redacted in capture — cannot determine auth type." Do not penalize for redaction, but do not award full auth points unless the spec confirms the scheme type.
- `Accept-Encoding` → gzip, br, deflate
- `Accept-Language` → locale values
- `Content-Type`
- `X-Request-Id`, `Idempotency-Key`
- **Client context headers** (extraction only — not directly scored, but used for observability and compatibility assessment):
  - `X-App-Version` → app version string (e.g. `8.14.2`)
  - `X-App-Build` → build number
  - `X-Platform` → `ios` or `android`
  - `X-OS-Version` → OS version (e.g. `18.4`)
  - `X-Device-Class` → `phone`, `tablet`
  - `X-Client-Capabilities` → capability negotiation string
  - Presence of these headers signals the API is designed for mobile-version-aware routing; absence does not penalize but is noted

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
- Error recovery fields: `retryable`, `userActionRequired`, `queueAction`
- Conflict payload: `conflict.clientBaseVersion`, `conflict.serverVersion`, `conflict.conflictingFields`
- Mutation status: `status` in mutation responses (`accepted`, `applied`, `conflicted`, `rejected_*`)
- Resource version fields: `version` (logical counter), `updatedAt`, `deletedAt`
- Sync envelope: `changes[]` with `type`, `resourceType`, `id`, `version`
- Data shape: field count, nesting, presence of large embedded arrays
- Auth tokens in body (security risk)

### Status codes observed
From `entries[].response.status`:
- List all unique status codes
- Note any 4xx or 5xx responses
- Check: is 429 present? (rate limiting works)
- Check: are there 401s? (auth failure observed)
- Check: are there 409s or 412s? (conflicts observed — inspect body for conflict payload)

### URL patterns
From `entries[].request.url`:
- Version segment in path
- Query parameters actually used in real traffic
- Any sensitive data in query params (tokens, PII)

### HAR quality filtering

Before computing any statistics, filter out noise entries:
- `OPTIONS` requests (CORS preflight — not application traffic)
- Requests with `response.status = 0` (aborted before response received)
- Requests where `timings.receive = -1` (incomplete capture)
- Duplicate requests to the same URL within 50 ms of each other (capture-tool retry artefacts)

After filtering, note the sample count:
- **≥ 10 requests**: statistics are reliable. Compute p50 and p95 normally.
- **5–9 requests**: note *"Small sample (N = X) — statistics are directional, not precise."* Score latency one band lower than raw p50 would suggest; do not award full points.
- **< 5 requests**: do not compute percentile statistics. Set latency status to `unknown`. Write *"Insufficient sample (N = X) — latency scoring requires at least 5 filtered requests."*

### HAR provenance check

Before scoring latency from HAR data, inspect all `entries[].request.url` host values:

- If **all** request hosts are `localhost`, `127.0.0.1`, or match `*.local` — flag as **"local capture"**: *"Latency values reflect a loopback/local environment and may not represent production network conditions."* Set latency status to `warn` even if raw numbers are fast. Do not award full latency points.
- If host contains any of: `staging`, `stage`, `sandbox`, `dev`, `test`, `qa`, `uat`, `preview`, `pre-prod`, `preprod` (case-insensitive substring match) — flag as **"non-production capture"** with the same caveat. Set latency status to `warn`.
- If host is a bare IP address or uses a non-standard port (not 80 or 443) — flag as **"non-production capture"**.
- If the host's TLD is an internal/non-public TLD — any of `.internal`, `.corp`, `.intranet`, `.lan`, `.local`, `.private`, `.home`, `.test`, or any single-label hostname (no dot in the hostname) — flag as **"internal/VPN capture"**: *"Hostname suggests a corporate internal or VPN-routed endpoint. Latency values do not reflect production mobile network conditions."* Set latency status to `warn`.
- If capture is **mixed** (some non-production or internal hosts, some production) — exclude non-production/internal entries from all latency and payload calculations. Note the exclusion count.
- If all hosts are production domains with standard ports and public TLDs — no caveat needed, score normally.

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
- `X-App-Version: ...`, `X-Platform: ...` → client context (extraction only)

### Method (`-X` or inferred)
- GET → should be retry-safe
- POST → check for idempotency key or operationId in body
- PUT/PATCH/DELETE → check for idempotency and base version (optimistic concurrency)

### Request body (`-d`, `--data`, `--data-raw`)
- Shape of request payload
- Fields sent
- Look for `operationId`, `clientId`, `baseVersion`, `ifMatch` (conflict detection)

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
