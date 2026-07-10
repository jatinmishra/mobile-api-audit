# Scoring Model

Exact point allocations and scoring rules for each dimension.
Apply conservatively: absence of evidence = 0 points for that criterion.

**Spec-only exception:** Two runtime-only criteria cannot be confirmed from a spec alone and should be scored `unknown` (not `bad`) when no HAR is provided: **response compression** and **rate-limit headers (X-RateLimit-*)**. For these, write "Spec-only — unverifiable without HAR" in the Evidence column and do not deduct.

HTTP cache headers (Cache-Control / ETag) are **not** subject to this exception when the spec documents them in response header definitions. If `Cache-Control` or `ETag` is defined in the spec's `responses` headers, score based on the documented value. Score `unknown` only when the header is absent from **both** the spec and any provided HAR.

**N/A proportional scoring:** When a dimension is confirmed N/A, exclude it from the denominator entirely — do not award its points. Compute the adjusted score as `(sum of earned points) / (100 − sum of N/A dimension maxima) × 100`. Apply verdict bands to this adjusted score. Report both the raw earned points and the applicable maximum in Section 18.

**Double-penalization is intentional.** The base dimension score measures *presence* — does the feature exist? Deductions in Section 16 measure *consequence* — how harmful is this gap to a mobile client? An API with offset-only pagination may score 4/8 in Dimension 1 (feature present but suboptimal) AND receive a Minor −1 deduction (slow connections will drop sessions under load). Both are correct: the first reports the gap, the second quantifies its mobile impact. This is by design, not an error.

**Idempotency and offline mutations — no double-penalization:** Client-assigned `operationId` (offline mutation pattern) counts as idempotent by design in Dimension 2's write idempotency criterion (award 2 pts, same as PUT). The Dimension 3 offline mutation criterion (0–2 pts) is separately assessing whether mutation *status echoing* and *operation IDs* are present together. These are distinct features; scoring both is correct. However, if an API has *neither* `Idempotency-Key` nor `operationId`, penalize in Dimension 2 and raise a known issue — do not penalize again in Dimension 3.

**Weight rationale.** Performance carries the highest weight (17 pts) because it is the first failure mode on mobile: flaky networks, CPU throttling, and battery constraints make a slow API feel like a crash to users. Error handling (15 pts) ranks next because mobile clients cannot hot-fix server failures — a bad deploy breaks a shipped app until the next App Store release cycle. Offline and caching follow (14 and 10 pts) because mobile clients operate in disconnected or low-bandwidth environments by default. Security, RTM, and rate limiting (10, 10, 8 pts) are critical but more binary — they either meet a threshold or they don't. Conflict handling (6 pts, conditional) is weighted as a major correctness concern for apps with locally-persisted mutable data. Versioning (5 pts) matters for the mobile team's workflow. Testing (3 pts) and Observability (2 pts) are team-facing and less visible to the mobile client, but `X-Request-Id` is irreplaceable for field debugging.

Example: Offline (14 pts) and RTM (10 pts) confirmed N/A → applicable maximum = 76. Earned = 62 → adjusted score = 62 / 76 × 100 = 82 → Mobile-ready.

---

## Dimension ↔ report section map

Scoring dimensions and report sections use different numbers for the same
concept. This model numbers dimensions by weight; the report
(`report-template.md`) numbers sections by reading order. Use this table to
cross-reference — a "Dimension 3" note here maps to "Section 6" in the report.

| Scoring dimension | Max pts | Report section |
|-------------------|---------|----------------|
| 1 — Performance & scalability | 17 | Section 4 |
| 2 — Error handling & stability | 15 | Section 8 |
| 3 — Offline sync *(conditional)* | 14 | Section 6 |
| 4 — Caching & payload | 10 | Section 5 |
| 5 — Real-time / RTM *(conditional)* | 10 | Section 7 |
| 6 — Security | 10 | Section 10 |
| 7 — Rate limiting | 8 | Section 9 |
| 8 — Versioning & deprecation | 5 | Section 13 |
| 9 — Testing & mocks | 3 | Section 14 |
| 10 — Observability | 2 | Section 15 |
| 11 — Conflict handling *(conditional)* | 6 | Section 11 |

Non-scored report sections: 1 (API overview), 2 (data characteristics),
3 (mobile usage patterns), 12 (localisation), 16 (known issues),
17 (proposed improvements), 18 (final verdict).

---

## Dimension 1 — Performance & scalability (17 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Pagination type | 0–8 | Cursor-based = 8, Offset/page = 4, None = 0 |
| HTTP/2 / connection reuse | 0–1 | HTTP/2 confirmed in HAR (`_protocol: h2` or `alpn: h2`) = 1, HTTP/1.1 only or unknown = 0 |
| Multi-entity batching | 0–4 | Supported = 4, Single entity only = 0, N/A = 4 (N/A only when the API has exclusively single-resource lookup endpoints and no collection/list endpoints exist; if list endpoints exist, score normally) |
| Latency p50 | 0–3 | <150ms = 3, <300ms = 2, <600ms = 1, ≥600ms or unknown = 0 |
| Retry policy documented | 0–2 | Backoff guidance published (spec externalDocs, x- extension, or Retry-After on 5xx) = 2, Retry-After on 429/5xx only = 1, Not found = 0 |
| Field filtering / sparse fieldsets | 0–1 | Supported (including named projections like `projection=list_v3`) = 1, Not found = 0 |

**Total: 17**

Flag as known issue if:
- No pagination exists on any list endpoint
- Offset pagination used (not cursor) → mark as `warn` not deduction, but note in known issues
- p95 latency > 800ms (from HAR data)
- No retry or backoff guidance — mobile clients on flaky connections will hammer the API without it

---

## Dimension 2 — Error handling & stability (15 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Consistent error schema across endpoints | 0–3 | Same shape on all error responses = 3, inconsistent = 1, none defined = 0 |
| Machine-readable error codes | 0–3 | `code` field present and documented = 3, generic HTTP only = 0 |
| Error recovery fields | 0–2 | All three present (`retryable`, `userActionRequired`, `queueAction`) = 2, one or two present = 1, none = 0. `queueAction` values to look for: retain, drop, modify, reauth, rebase |
| GET endpoints retry-safe | 0–2 | Default: assume safe = 2 (per HTTP spec, GETs are idempotent). Score 0 only if HAR provides direct evidence of non-idempotent GET behavior (e.g. GET that mutates state or has confirmed side effects). Spec-only audits: always award 2 pts. |
| Write endpoint idempotency | 0–3 | Idempotency-Key header supported = 3, idempotent by design = 2, not found = 0, N/A = 3. **Idempotent by design:** PUT endpoints are idempotent per RFC 7231 — award 2 pts. POST endpoints without an `Idempotency-Key` header are not idempotent — award 0 pts. **Client operationId:** If offline mutations use a client-assigned `operationId` in the request body as operation identity, award 2 pts (idempotent by design). |
| 4xx vs 5xx correctly used | 0–2 | Both present and correct = 2, only 2xx observed = 1, mixed = 0 |

**Total: 15**

Flag as known issue if:
- No error schema defined at all
- Write endpoints (POST/PATCH) have no idempotency mechanism
- 5xx errors observed in HAR with no Retry-After
- No error recovery fields (`retryable`, `userActionRequired`, `queueAction`) — mobile operation queues cannot make safe decisions without them

---

## Dimension 3 — Offline sync (14 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Sync mechanism | 0–6 | Opaque cursor-based delta sync = 6, Timestamp-based delta sync = 4, Full sync = 2, Not needed (confirmed) = 6, Not found = 0. Opaque cursors score higher than timestamp-based because they are server-controlled and can encapsulate schema version, account scope, and projection — timestamp-based cursors break on re-ordering or clock drift. |
| Deleted record and access removal signalling | 0–2 | Tombstones/`deletedAt` present = 1, access removal / permission-loss signals (explicit removal events when user loses access to a record) = 1. Both required for full score. Absence of a record in a delta response does NOT constitute an access removal signal. |
| Offline mutation support | 0–2 | Client operation IDs present in request body AND mutation status echoed in response (`accepted`, `applied`, `conflicted`, `rejected_*`, `dependency_failed`) = 2, one or the other but not both = 1, neither = 0. Note: `accepted` ≠ `applied` — a client that treats `accepted` as `applied` will show stale data; check whether both states are distinct in the spec. |
| Cursor expiry error classes | 0–2 | All four error classes defined with distinct recovery guidance = 2, some defined = 1, none = 0. Required classes: `SYNC_CURSOR_EXPIRED` (history unavailable — full resync), `SYNC_CURSOR_INVALID` (malformed/tampered), `SYNC_CURSOR_INCOMPATIBLE` (schema/version changed), `SYNC_CURSOR_REVOKED` (security/auth reset — highest severity; no amount of retrying resolves this). |
| Cache-friendly responses | 0–2 | Stable IDs + ETag or Last-Modified = 2, Stable IDs only = 1, Neither = 0 |

**Total: 14**

"Not needed" only scores full if there is a clear reason — ephemeral data (search results, payment sessions, auth flows).

Flag as known issue if:
- No sync mechanism where locally-persisted mutable data is expected
- Timestamp-based cursors used instead of opaque cursors — broken by clock drift and server re-ordering
- Access removal not signalled — users who lose permission to a record will retain it locally indefinitely
- No cursor expiry error classes defined — client cannot distinguish a recoverable from a security-triggered reset
- Offline mutations present but mutation status not echoed — queues cannot determine applied vs pending state

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
| Authentication method | 0–4 | OAuth2/JWT Bearer = 4, API key = 0, Session/Basic = 0, None = 0 |
| OAuth flow appropriate for mobile | 0–1 | PKCE flow confirmed = 1, OAuth without PKCE or flow unspecified = 0, N/A (non-OAuth2) = 1 |
| Auth completeness for mobile | 0–3 | Score one point each for: (1) refresh token flow documented; (2) step-up auth challenge shape defined (`STEP_UP_REQUIRED` error with challenge descriptor); (3) session/device revocation behavior documented (what happens to queued mutations when a session is revoked). Max 3. Not found = 0. Concurrent refresh behavior (how simultaneous 401s are handled) counts toward criterion (1) if documented alongside refresh. |
| HTTPS enforced | 0–2 | Confirmed (HSTS header or HTTPS-only server URL) = 2, HTTP URL observed = 0, Unknown (spec-only, no server URL) = 1 |

**Total: 10**

Flag as known issue if:
- No authentication found (critical)
- API key auth on a confirmed mobile-facing endpoint (major — trivially extractable from app binary)
- Sensitive data or tokens found in URL query parameters (critical)
- Basic auth used on a mobile-facing endpoint (major)
- OAuth2 used without PKCE on a mobile-facing endpoint (major)
- No step-up auth or session revocation defined — queued mutations can be replayed after a revoked session (major)

---

## Dimension 7 — Rate limiting (8 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Rate limits exist and are documented | 0–3 | Documented with values = 3, Exist but undocumented = 1, None found = 0 |
| Standard rate limit headers returned | 0–3 | X-RateLimit-* headers present in HAR = 3, Retry-After on 429 only = 1, Neither = 0 |
| 429 returned (not silent failure) | 0–2 | 429 observed in HAR or confirmed in spec = 2, Not confirmed = 0 |

**Total: 8**

---

## Dimension 8 — Versioning & deprecation (5 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Explicit versioning strategy | 0–3 | Version in URL path = 3, Version header = 2, No versioning = 0 |
| Deprecation / sunset mechanism | 0–1 | Sunset header defined or deprecation policy found = 1, Not found = 0 |
| Minimum supported app version | 0–1 | Config or capabilities endpoint declares minimum supported app version per platform (iOS/Android) = 1, Not found = 0. Capability negotiation (`features` block) also counts. |

**Total: 5**

---

## Dimension 9 — Testing & mocks (3 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| OpenAPI spec completeness | 0–2 | All paths, schemas, and responses fully defined = 2, Partial = 1, No spec = 0 |
| Sandbox / staging environment | 0–1 | Server URL for staging present in spec = 1, Not found = 0 |

**Total: 3**

---

## Dimension 10 — Observability (2 pts)

| Criterion | Points | Rule |
|-----------|--------|------|
| Request ID returned | 0–2 | X-Request-Id or X-Trace-Id in response headers (HAR) = 2, Not found = 0. This is the single most important debugging tool for mobile field issues — without it, correlating a user crash report to server logs is guesswork. |

**Total: 2**

---

## Dimension 11 — Conflict handling (6 pts) ⚠️ CONDITIONAL

**Conditional:** Exclude from denominator when the API has no locally-persisted mutable collections. Read-only APIs, append-only APIs (logs, comments with no edit), and auth/config-only APIs do not need conflict handling. When N/A is applied, mark all rows N/A with note "No locally-persisted mutable collections confirmed."

Apply this dimension when: the API exposes PATCH, PUT, or DELETE on resources users can edit, especially where offline mutations (Dimension 3) are relevant.

| Criterion | Points | Rule |
|-----------|--------|------|
| Conflict policy declared | 0–3 | Per-resource conflict policy documented = 3, implied but not explicit = 1, no policy (bare 409/412 only) = 0. Valid policies: `client_resolves`, `server_merges`, `last_writer_wins`, `append_only`, `reject_when_stale`. User-authored content should not default to last-writer-wins; flag if it does. |
| Conflict response shape | 0–2 | Conflict response includes client base version (`clientBaseVersion` or `baseEtag`), server version (`serverVersion` or current ETag), and conflicting field list (`conflictingFields`) or server resource — 2 pts. Partial (one or two fields present) = 1. `queueAction: rebase` in conflict error response counts toward this criterion (it signals the client can replay on top of current server state — meaningfully better than a bare 409). Bare 409/412 with no payload = 0. |
| Conflict error code | 0–1 | Machine-readable `CONFLICT_*` code separate from generic HTTP 409 = 1, only HTTP 409 = 0. Example: `CONFLICT_RESOURCE_VERSION_MISMATCH`, `CONFLICT_CONCURRENT_EDIT`. |

**Total: 6**

Flag as known issue if:
- Mutable resources with no declared conflict policy (major)
- Conflict response is a bare 409/412 with no version metadata (major — mobile client cannot surface a meaningful merge/retry UX)
- No machine-readable conflict code (minor)

---

## Deductions

Known issues carry tiered deductions based on severity. Assign severity before deducting; when uncertain between tiers, use the lower (less severe) one.

| Severity | Deduction | Examples |
|----------|-----------|---------|
| Critical | −5 pts | No authentication on any endpoint; PII or tokens confirmed in URL query params; HTTP (not HTTPS) confirmed in traffic |
| Major | −3 pts | No idempotency on automated write endpoints; no error schema defined at all; no pagination on unbounded list endpoints; OAuth2 without PKCE on confirmed mobile consumer; API key auth on confirmed mobile-facing endpoint; no conflict policy on mutable resources; access removal not signalled through sync; no step-up auth or session revocation; offline mutations without operation IDs (when offline + mutable) |
| Minor | −1 pt | Offset pagination used instead of cursor; no sandbox environment; rate limits undocumented; no error recovery fields (retryable/userActionRequired/queueAction); cursor expiry codes undocumented; no minimum app version in config; no conflict machine-readable code |

Only deduct for issues with direct evidence. No floor below 0.

---

## Blockers

The following conditions **hard-cap the verdict at "Ready with changes"** regardless of numeric score. A score of 75+ does not override a blocker.

| Blocker | Evidence required |
|---------|------------------|
| No authentication on any endpoint | No `securitySchemes` in spec AND no `Authorization` header in HAR |
| No HTTPS enforced | HTTP server URL present in spec OR non-HTTPS requests observed in HAR |
| No pagination on any list endpoint returning unbounded collections | List endpoints confirmed present with no pagination params of any kind AND no known fixed upper bound on collection size |
| No idempotency on automated write endpoints | POST/PUT/PATCH endpoints present, no `Idempotency-Key` and no client `operationId` pattern, and write frequency is Automated or Both (default when user skips) |
| OAuth2 without PKCE on a mobile consumer | OAuth2 security scheme confirmed AND mobile consumer confirmed AND PKCE flow not specified in any OAuth2 flow definition |

If any blocker applies: set verdict to "Ready with changes" regardless of score, and list the triggered blocker in Section 18 under "Blocker triggered."

---

## Verdict

| Adjusted score | Verdict |
|---------------|---------|
| 75–100 | Mobile-ready |
| 50–74 | Ready with changes |
| 0–49 | Not mobile-ready |

### Evidence confidence

Include a confidence tier in Section 18 alongside the verdict. Count the proportion of scored criteria (excluding N/A rows) whose status is `unknown`.

| Tier | Condition |
|------|-----------|
| High | Spec + HAR provided; ≤20% of scored criteria are `unknown` |
| Medium | Spec only or HAR only; 20–50% of scored criteria are `unknown` |
| Low | HAR only (no spec), or >50% of scored criteria are `unknown` |

A "Mobile-ready" verdict at Low confidence should be explicitly qualified in the Engineering recommendation row of Section 18: "Score reflects limited input coverage — provide a HAR capture to confirm."
