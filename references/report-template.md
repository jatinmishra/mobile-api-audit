# Report Template

Full HTML structure for the generated report. Write this as a single self-contained `.html` file.

---

## Page structure

```
<head> — styles (inline, no external deps)
<body>
  .copy-bar        — "Select all + Copy for Confluence" instruction bar
  .header          — API name, score badge, verdict, meta row
  .score-panel     — dimension bars + deduction summary
  sections 1–17    — evaluation tables
  <script>         — select-all helper only
```

---

## CSS design tokens

Use these exact values for Confluence paste compatibility:

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
- Schema stability
- API dependency chain

### Section 3 — Mobile usage patterns

Rows (all sourced from context or inferred from endpoint names):
- Called on app launch
- Called on every screen load
- Called during foreground transition
- Called in background / silent push
- Called on user action
- Expected calls per session
- Expected concurrent callers

### Section 4 — Performance & scalability (20 pts)

Rows:
- Pagination type (with param names)
- Max page size configurable
- Batching / bulk endpoint support
- Average latency p50
- Latency p95
- Field filtering / sparse fieldsets
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

### Section 6 — Offline sync (12 pts)

Rows:
- Sync mechanism (delta/full/none/not-required)
- Sync key type and parameter name
- Deleted record signalling (tombstones)
- Results safely cacheable on device
- Conflict resolution strategy
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
- GET endpoints retry-safe
- Write endpoints idempotent
- Idempotency-Key header support
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
- Token expiry / 401 behaviour
- Scopes / permissions required
- Principle of least privilege
- HTTPS enforced
- PII in response body
- Sensitive data in URL params
- Mobile-specific risks

### Section 11 — Localisation & i18n

Rows:
- Localisation support (full/partial/none/not-required)
- Locale input method
- Locale-aware date formatting
- Locale-aware currency formatting
- RTL text supported
- Supported locales
- Fallback locale behaviour

### Section 12 — Versioning & deprecation (6 pts)

Rows:
- Versioning strategy
- Backward-compatible change policy
- Deprecation notice period
- Sunset header used
- Old versions still supported
- Changelog maintained
- Mobile team notified of changes

### Section 13 — Testing & mock availability (5 pts)

Rows:
- OpenAPI spec current and complete
- Sandbox / staging environment
- Mock server available
- Representative test data
- Contract tests in CI
- Consumer-driven contract tests
- Postman / Bruno collection
- Known staging limitations

### Section 14 — Monitoring & observability (4 pts)

Rows:
- Request ID returned in responses
- Latency dashboard exists
- Error rate dashboard exists
- Alerting configured
- SLA / SLO defined
- Distributed tracing available
- Mobile-specific metrics
- Incident history / status page

### Section 15 — Known issues

Table with columns: Issue | Severity (high/med/low) | Impact / Notes

Only include confirmed issues with direct evidence.
Each issue deducts 2 points.

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
- Conflict resolution undefined
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
- Over-scoped permissions
- PII exposure risk
- No versioning strategy
- No sunset/deprecation policy
- No sandbox environment
- OpenAPI spec missing/outdated
- No contract tests
- No observability dashboards
- No SLA/SLO defined
- Data model mismatch
- Localisation gaps (where needed)

### Section 16 — Proposed improvements

Table: Improvement | Priority (High/Med/Low) | Reasoning

Every confirmed known issue must have a row.
Prioritise: High = blocks mobile shipment, Med = degrades UX, Low = best practice.

### Section 17 — Final verdict

Table:
- Raw score (sum of dimensions)
- Deductions (N issues × 2)
- Adjusted total
- Verdict (Mobile-ready / Ready with changes / Not mobile-ready)
- Top 3 risks
- Engineering recommendation
- Conditions for approval (if Ready with changes)

---

## Copy-for-Confluence button

Add this at the top of the page (position: fixed, does not get copied):

```html
<div class="copy-bar">
  <span>Open in browser → <strong>Select all</strong> (Cmd/Ctrl+A) → Copy → Paste into Confluence</span>
  <button onclick="selectContent()">Select all</button>
</div>
```

Script:
```js
function selectContent() {
  const el = document.getElementById('content');
  const range = document.createRange();
  range.selectNodeContents(el);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}
```

Wrap all report content in `<div id="content">`.

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
    <div class="deductions">−4 (2 issues × 2)</div>
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
