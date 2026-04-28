# Scoring Model

Exact point allocations and scoring rules for each dimension.
Apply conservatively: absence of evidence = 0 points for that criterion.

---

## Dimension 1 — Performance & scalability (20 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Pagination type | 0–8 | Cursor-based = 8, Offset/page = 4, None = 0 |
| Max page size configurable | 0–2 | Configurable = 2, Fixed reasonable ≤100 = 1, Fixed large or none = 0 |
| Multi-entity batching | 0–4 | Supported = 4, Single entity only = 0, N/A = 4 |
| Latency p50 | 0–4 | <150ms = 4, <300ms = 3, <600ms = 1, ≥600ms or unknown = 0 |
| Field filtering / sparse fieldsets | 0–2 | Supported = 2, Not found = 0 |

**Total: 20**

Flag as known issue if:
- No pagination exists on any list endpoint
- Offset pagination used (not cursor) → mark as `warn` not deduction, but note in known issues
- p95 latency > 800ms (from HAR data)

---

## Dimension 2 — Error handling & stability (15 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Consistent error schema across endpoints | 0–5 | Same shape on all error responses = 5, inconsistent = 2, none defined = 0 |
| Machine-readable error codes | 0–3 | `code` field present and documented = 3, generic HTTP only = 0 |
| GET endpoints retry-safe | 0–2 | All GETs safe = 2, Not confirmed = 0 (GETs should always be safe) |
| Write endpoint idempotency | 0–3 | Idempotency-Key header supported = 3, idempotent by design = 2, not found = 0, N/A = 3 |
| 4xx vs 5xx correctly used | 0–2 | Both present and correct = 2, only 2xx observed = 1, mixed = 0 |

**Total: 15**

Flag as known issue if:
- No error schema defined at all
- Write endpoints (POST/PATCH) have no idempotency mechanism
- 5xx errors observed in HAR with no Retry-After

---

## Dimension 3 — Offline sync (12 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Sync mechanism | 0–8 | Delta sync (timestamp/cursor param) = 8, Full sync = 4, Not needed (confirmed) = 8, Not found = 0 |
| Deleted record signalling | 0–2 | Tombstones / `deleted_at` / `is_deleted` in schema = 2, Not found = 0, N/A = 2 |
| Cache-friendly responses | 0–2 | Stable IDs + ETag or Last-Modified = 2, Stable IDs only = 1, Neither = 0 |

**Total: 12**

"Not needed" only scores full if there is a clear reason — ephemeral data (search results, payment sessions, auth flows).

---

## Dimension 4 — Caching & payload (10 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Cache-Control header | 0–4 | Present with meaningful max-age = 4, Present with no-store/no-cache = 1, Absent = 0 |
| ETag or Last-Modified | 0–2 | Present = 2, Absent = 0 |
| Response compression | 0–2 | gzip or br confirmed (Content-Encoding in HAR or Accept-Encoding handled) = 2, Not found = 0 |
| Minimal payload (no excess fields) | 0–2 | Schema appears minimal = 2, Large/bloated schema = 0, Cannot assess = 1 |

**Total: 10**

---

## Dimension 5 — Real-time / RTM (10 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| RTM / push mechanism exists | 0–6 | Full coverage = 6, Partial = 3, Not needed (confirmed) = 6, Not found = 0 |
| RTM contract matches REST | 0–4 | Confirmed match = 4, Gaps documented = 2, Unknown = 0, N/A = 4 |

**Total: 10**

"Not needed" only for APIs where real-time state updates are genuinely irrelevant (e.g. a batch export endpoint).

---

## Dimension 6 — Security (10 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Authentication method | 0–4 | OAuth2/JWT Bearer = 4, API key = 2, Session/Basic = 1, None = 0 |
| Token refresh documented | 0–2 | Refresh token flow defined = 2, Not found = 0, N/A = 2 |
| Principle of least privilege | 0–2 | Scopes granular and minimal = 2, Over-broad or undefined = 0 |
| HTTPS enforced | 0–1 | Confirmed (HSTS header or HTTPS-only server URL) = 1, HTTP URL observed = 0, Unknown = 0 |
| No sensitive data in URLs | 0–1 | No tokens/PII in query params = 1, Found in HAR = 0 |

**Total: 10**

Flag as known issue if:
- No authentication found
- Token in URL query parameter
- Basic auth used on mobile-facing endpoint

---

## Dimension 7 — Rate limiting (8 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Rate limits exist and are documented | 0–3 | Documented with values = 3, Exist but undocumented = 1, None found = 0 |
| Standard rate limit headers returned | 0–3 | X-RateLimit-* headers present in HAR = 3, Retry-After on 429 only = 1, Neither = 0 |
| 429 returned (not silent failure) | 0–2 | 429 observed in HAR or confirmed in spec = 2, Not confirmed = 0 |

**Total: 8**

---

## Dimension 8 — Versioning & deprecation (6 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Explicit versioning strategy | 0–3 | Version in URL path = 3, Version header = 2, No versioning = 0 |
| Deprecation / sunset mechanism | 0–2 | Sunset header defined or deprecation policy found = 2, Not found = 0 |
| Changelog maintained | 0–1 | Link found in spec or server info = 1, Not found = 0 |

**Total: 6**

---

## Dimension 9 — Testing & mocks (5 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| OpenAPI spec completeness | 0–2 | All paths, schemas, and responses fully defined = 2, Partial = 1, No spec = 0 |
| Sandbox / staging environment | 0–2 | Server URL for staging present in spec = 2, Not found = 0 |
| Contract / consumer tests | 0–1 | Referenced in spec extensions or x- fields = 1, Not found = 0 |

**Total: 5**

---

## Dimension 10 — Observability (4 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Request ID returned | 0–2 | X-Request-Id or X-Trace-Id in response headers (HAR) = 2, Not found = 0 |
| SLA / SLO referenced | 0–1 | Found in spec externalDocs or x- extension = 1, Not found = 0 |
| Monitoring endpoints | 0–1 | Health check or status endpoint found in paths = 1, Not found = 0 |

**Total: 4**

---

## Deductions

Each confirmed known issue: **−2 points**

Only deduct for issues with direct evidence. Maximum deduction: no floor below 0.

---

## Verdict

| Adjusted score | Verdict |
|---------------|---------|
| 75–100 | Mobile-ready |
| 50–74 | Ready with changes |
| 0–49 | Not mobile-ready |
