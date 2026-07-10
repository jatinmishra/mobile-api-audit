# Report Template

Full HTML structure for the generated report. Write this as a single self-contained `.html` file.

---

## Page structure

```
<head> — styles (inline, no external deps)
<body>
  .header          — API name, score badge, verdict, meta row
  .score-panel     — dimension bars + deduction summary
  sections 1–18    — evaluation tables
```

---

## CSS design tokens

Design tokens used throughout the report:

```css
/* Colours */
--text:       #172B4D
--text-mid:   #42526E
--text-sub:   #6B778C
--text-hint:  #97A0AF
--surface:    #F4F5F7
--border:     #DFE1E6
--green-bg:   #E3FCEF   --green-txt:  #006644
--yellow-bg:  #FFFAE6   --yellow-txt: #974F0C
--red-bg:     #FFEBE6   --red-txt:    #BF2600
--blue-bg:    #DEEBFF   --blue-txt:   #0747A6

/* Typography */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif
font-size body: 14px

/* Tables */
th background: #F4F5F7
th/td border:  1px solid #DFE1E6
th padding:    8px 12px
td padding:    8px 12px
even rows:     background #FAFBFC
```

---

## Status value classes

Each evaluation row has a status pill. Use these classes:

| Class | Background | Text | When to use |
|-------|-----------|------|------------|
| `.s-good` | `#E3FCEF` | `#006644` | Feature confirmed present and working well |
| `.s-warn` | `#FFFAE6` | `#974F0C` | Feature present but suboptimal (e.g. offset pagination) |
| `.s-bad` | `#FFEBE6` | `#BF2600` | Feature missing where required, or confirmed problem |
| `.s-na` | `#F4F5F7` | `#6B778C` | Not applicable to this API |
| `.s-unknown` | `#F4F5F7` | `#97A0AF` | Not found in input — cannot determine |

---

## Panel types

Use coloured left-border panels above each section for guidance text:

```html
<div class="panel info">   <!-- blue  — informational -->
<div class="panel tip">    <!-- green — what good looks like -->
<div class="panel warn">   <!-- amber — failure modes to watch for -->
<div class="panel note">   <!-- gray  — neutral guidance -->
```

---

## Section row schema

Every evaluation table has these columns:

| Column | Width | Content |
|--------|-------|---------|
| Criterion | 26% | What is being assessed |
| Status | 22% | Status pill (s-good / s-warn / s-bad / s-na / s-unknown) |
| Notes | remaining | Finding details, parameter names, example values |
| Evidence | — | Exact source reference (e.g. `paths./events.get.parameters[2].name = "offset"`) — include when available |

---

## Section definitions

### Section 1 — API overview

Rows:
- API name
- Endpoint(s)
- Functional purpose
- Primary consumer(s)
- Data domain
- Team / owner
- Current version
- OpenAPI spec
- Staging / sandbox URL
- Runbook / documentation

### Section 2 — Data characteristics

Rows:
- Response type (list/detail/aggregated/mixed)
- Typical payload size (p50 from HAR or estimated)
- P95 payload size
- Max records per response
- Data sensitivity (PII fields listed)
- Schema formally documented
- Schema stability — default status: `unknown`. Mark as "Requires manual input — cannot be inferred from spec or HAR." Do not infer or assume a value.
- API dependency chain — default status: `unknown`. Mark as "Requires manual input — cannot be inferred from spec or HAR." Do not infer or assume a value.

### Section 3 — Mobile usage patterns

Rows (all sourced from context or inferred from endpoint names):
- Called on app launch
- Called on every screen load
- Called during foreground transition
- Called in background / silent push
- Called on user action
- Expected calls per session
- Expected concurrent callers

**Inference rule:** All rows in this section that are inferred (not user-confirmed or directly observed in HAR) must include the tag `[inferred]` in the Notes column and a brief explanation of the inference (e.g. `[inferred] GET-heavy traffic pattern with no explicit scheduling context`). User-confirmed answers from the clarifying questions step should be marked `[confirmed]`. Never present inferred values as facts — they feed latency scoring targets, so the user must be able to correct them.

### Section 4 — Performance & scalability (17 pts)

Rows:
- Pagination type (with param names)
- HTTP/2 / connection reuse
- Batching / bulk endpoint support
- Average latency p50
- Latency p95
- Field filtering / sparse fieldsets (including named projections)
- Response compression
- Minimal response data

### Section 5 — Caching & payload optimisation (10 pts)

Rows:
- Cache-Control header
- ETag / Last-Modified
- CDN-cacheable
- Vary header correct
- Response includes only needed fields
- Image/media URLs via CDN
- Pagination cursor stable

### Section 6 — Offline sync (14 pts)

Rows:
- Sync mechanism (opaque cursor delta / timestamp delta / full / none / not-required)
- Sync key type and parameter name
- Deleted record signalling (tombstones / deletedAt)
- Access removal signalling (explicit removal events when user loses permission — absence ≠ removal)
- Offline mutation support (client operationId + mutation status echoing: accepted/applied/conflicted/rejected_*)
- Cursor expiry error classes (SYNC_CURSOR_EXPIRED / SYNC_CURSOR_INVALID / SYNC_CURSOR_INCOMPATIBLE / SYNC_CURSOR_REVOKED)
- Results safely cacheable on device
- Sync tested under large dataset
- Impact if offline sync missing

### Section 7 — RTM / change notifications (10 pts)

Rows:
- RTM transport
- RTM updates available (event types listed)
- RTM data contract matches REST
- Reconnect behaviour documented
- Event ordering guaranteed
- RTM tested in staging

### Section 8 — Error handling & stability (15 pts)

Rows:
- Consistent error response schema
- Machine-readable error codes
- Error recovery fields (`retryable`, `userActionRequired`, `queueAction`)
- GET endpoints retry-safe
- Write endpoints idempotent (Idempotency-Key or client operationId)
- Timeout behaviour documented
- Circuit breaker / graceful degradation
- 4xx vs 5xx correctly distinguished
- Error messages safe for display

### Section 9 — Rate limiting & throttling (8 pts)

Rows:
- Rate limits exist and are documented
- Rate limit headers returned
- 429 returned (not silent failure)
- Retry-After on 429
- Burst limit defined
- Backoff guidance published
- Limits sufficient for mobile usage

### Section 10 — Security (10 pts)

Rows:
- Authentication method
- Token refresh documented
- Step-up auth challenge defined (STEP_UP_REQUIRED error shape)
- Session / device revocation behaviour (what happens to queued mutations on revocation)
- Token expiry / 401 behaviour
- Scopes / permissions required
- HTTPS enforced
- PII in response body
- Sensitive data in URL params
- Mobile-specific risks

### Section 11 — Conflict handling (6 pts) ⚠️ CONDITIONAL

Mark entire section N/A if API has no locally-persisted mutable collections (read-only, append-only, or auth/config-only). Include a note explaining why.

Rows:
- Conflict policy declared per mutable resource (client_resolves / server_merges / last_writer_wins / append_only / reject_when_stale)
- Conflict response includes client base version (clientBaseVersion or equivalent)
- Conflict response includes current server version (serverVersion or current ETag)
- Conflict response includes conflicting field list (conflictingFields) or full server resource
- queueAction in conflict errors (rebase = server confirms replay is safe; retain/drop/modify also valid)
- Machine-readable conflict error code (CONFLICT_* separate from generic 409)
- User-authored content does not default to last-writer-wins

### Section 12 — Localisation & i18n

Rows:
- Localisation support (full/partial/none/not-required)
- Locale input method
- Locale-aware date formatting
- Locale-aware currency formatting
- RTL text supported
- Supported locales
- Fallback locale behaviour

### Section 13 — Versioning & deprecation (5 pts)

Rows:
- Versioning strategy
- Backward-compatible change policy
- Deprecation notice period
- Sunset header used
- Old versions still supported
- Minimum supported app version declared (per iOS/Android platform)
- Mobile team notified of changes

### Section 14 — Testing & mock availability — mobile team impact (3 pts)

> **Mobile team impact:** These rows assess whether the backend team's testing practices protect the mobile team from silent breaking changes. Mobile releases take 1–2 weeks through App Store review — a backend deploy can break a shipped app with no ability to hotfix in minutes. A sandbox and contract tests are not backend-quality concerns; they are the mobile team's safety net.

Rows:
- OpenAPI spec current and complete
- Sandbox / staging environment
- Mock server available
- Representative test data
- Postman / Bruno collection
- Known staging limitations

### Section 15 — Monitoring & observability — mobile team impact (2 pts)

> **Mobile team impact:** These rows assess what debugging capability the mobile team has after shipping. When a user files a crash report from the field, `X-Request-Id` is the only thread available to correlate the crash with server logs. Without it, diagnosing production issues in a shipped mobile release is guesswork.

Rows:
- Request ID returned in responses
- Latency dashboard exists
- Error rate dashboard exists
- Alerting configured
- Distributed tracing available
- Mobile-specific metrics (sliced by app version, platform, OS version)
- Incident history / status page

### Section 16 — Known issues

Table with columns: Issue | Severity (Critical/Major/Minor) | Deduction | Impact / Notes

Only include confirmed issues with direct evidence.
Deductions by severity: Critical = −5 pts, Major = −3 pts, Minor = −1 pt.

Checklist to verify against (mark only confirmed):
- No pagination on list endpoints
- Offset pagination (not cursor)
- No batching support
- High latency (>300ms p50 or >800ms p95)
- Heavy payload (>200 KB p95)
- No response compression
- No HTTP cache headers
- No offline sync (where needed)
- No tombstones for deleted records
- Access removal not signalled through sync (users retain records after losing permission)
- Offline mutations without client operation IDs (queue cannot track applied state)
- Cursor expiry error classes not defined (client cannot distinguish security reset from expired history)
- No conflict policy declared on mutable resources
- Conflict response is bare 409/412 with no version metadata (client cannot surface merge UX)
- No machine-readable conflict error code
- Error responses lack recovery fields (retryable / userActionRequired / queueAction)
- No step-up auth challenge defined
- No session revocation behaviour documented
- No RTM (where needed)
- RTM/REST contract mismatch
- Multiple sequential calls required
- Inconsistent error schema
- Write endpoints not idempotent
- Timeout behaviour undefined
- Rate limits undocumented
- No Retry-After on 429
- Non-token auth
- Token refresh not handled
- PII exposure risk
- No versioning strategy
- No sunset/deprecation policy
- No minimum app version in config/capabilities endpoint
- No sandbox environment
- OpenAPI spec missing/outdated
- No observability dashboards
- Data model mismatch
- Localisation gaps (where needed)

### Section 17 — Proposed improvements

Table: Improvement | Priority (High/Med/Low) | Reasoning

Every confirmed known issue must have a row.
Prioritise: High = blocks mobile shipment, Med = degrades UX, Low = best practice.

### Section 18 — Final verdict

Table:
- Earned score (sum of scored dimension points, excluding N/A dimensions)
- Applicable maximum (100 − sum of N/A dimension maxima)
- Deductions (itemised by severity: Critical −5, Major −3, Minor −1)
- Adjusted score ((earned − deductions) / applicable maximum × 100, rounded to nearest integer)
- Verdict (Mobile-ready / Ready with changes / Not mobile-ready)
- Evidence confidence (High / Medium / Low — see scoring model)
- Score position — where score sits within its band (e.g. "83/100 — upper end of Mobile-ready (75–100 band)")
- Audit coverage — input types provided (e.g. "Spec only", "Spec + HAR", "HAR only", "Spec + cURL")
- Blocker triggered — any hard-cap condition that applied, or "None"
- Top 3 risks
- Engineering recommendation
- Conditions for approval (if Ready with changes)

---

## Score panel (below header, above sections)

Show a summary panel with:
- Large score number (coloured green/amber/red by band)
- Horizontal bar for each dimension showing score/max with colour
- Verdict chip
- Deduction count

Example structure:
```html
<div class="score-panel">
  <div class="score-display">
    <span class="score-num" style="color: [green|amber|red]">72</span>
    <span class="score-denom">/100</span>
    <!-- If N/A dimensions applied, show: earned/applicable e.g. "56 of 78 applicable pts → 72" -->
    <div class="deductions">−6 (1 critical × 5, 1 minor × 1)</div>
  </div>
  <div class="dimension-bars">
    <!-- one row per dimension -->
    <div class="dim-row">
      <span class="dim-name">Performance</span>
      <div class="bar-track"><div class="bar-fill" style="width:75%; background:#10B981"></div></div>
      <span class="dim-pts">15/20</span>
    </div>
    ...
  </div>
  <div class="verdict-box">
    <span class="verdict warn">Ready with changes</span>
  </div>
</div>
```

When no HAR is present, add this caveat below the score panel:

```html
<div class="panel note">
  <strong>Audit coverage: spec only.</strong> Three dimensions cannot be confirmed
  without live traffic data: response compression, HTTP cache headers, and rate-limit
  headers. These rows default to <code>unknown</code> rather than <code>bad</code>.
  Latency scores are estimated, not measured. Client context headers (X-App-Version,
  X-Platform, X-OS-Version) and actual conflict/error shapes are also unverifiable
  without a HAR capture. Providing a HAR will produce a more accurate score.
</div>
```
