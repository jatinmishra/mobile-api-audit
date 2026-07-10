# Clarification Questions

This file defines how to derive targeted, context-aware clarifying questions
from the inputs — not a static list to ask every time.

---

## Core principle

**Read first, ask only what you can't determine.**

Before forming any question, build a context model from the inputs. Questions
must reference what was found. A question that could be asked without reading
the file is a bad question.

---

## Step 1 — Build the context model

After reading all inputs, answer these internally (do not ask the user):

### API identity
- What does this API do? (infer from path names, schema field names, info.description)
- What kind of data does it return? (schedules, payments, search results, user profiles...)
- Is it read-heavy, write-heavy, or mixed?
- What domain does it serve? (events, bookings, auth, content, payments...)

### Endpoint signals
- Are there list endpoints that return collections? (pagination matters)
- Are there write endpoints (POST/PUT/PATCH/DELETE)? (idempotency matters)
- Are there PATCH/PUT/DELETE endpoints on user-editable resources? (conflict handling matters — Dim 11)
- Are there endpoints that return time-sensitive or frequently-changing data? (RTM may matter)
- Are there endpoints returning data users act on in the field? (offline may matter)
- Are there locale or language parameters? (l10n may already be handled)
- Is there a config or capabilities endpoint? (minimum app version, feature flags)

### Locally-persisted mutable collections (Dim 11 N/A trigger)
Infer whether the API serves data that is both locally persisted AND mutable:
- Read-only APIs (only GET endpoints) → Dim 11 is N/A — mark conflict handling as not applicable
- Append-only APIs (POST creates, no PATCH/PUT/DELETE) → Dim 11 is N/A
- Auth/config-only APIs (login, token, session, capabilities) → Dim 11 is N/A
- APIs with PATCH/PUT/DELETE on user-editable resources → Dim 11 applies; do not mark N/A without asking
- When genuinely ambiguous (mixed API with some mutations), ask the offline mutations question below

### HAR signals (if present)
- How many requests per session? (infer usage frequency)
- Are requests clustered at app open or spread through a session? (infer usage pattern)
- Are requests sequential or parallel? (dependency chain)
- What are the actual latency p50/p95? (no need to ask)
- Are there 401s, 429s, 5xxs in the traffic? (auth and stability signals)
- Are there 409s or 412s? (conflicts occurring in real traffic)

### Inference rules — when NOT to ask

| Dimension | Skip the question if... |
|-----------|------------------------|
| RTM | Only POST/write endpoints — nothing to push. Or: ephemeral data (auth tokens, search). Or: HAR shows no websocket/SSE connections and data is clearly static (config, lookup tables) |
| Offline sync | Only skip if the spec is **explicitly auth-only** (contains only login, logout, token refresh, and OTP endpoints) AND no data retrieval endpoints exist. Do not infer offline is unnecessary based on domain alone (e.g. "payment" or "auth") — data retrieval may still be needed offline in low-connectivity contexts. |
| Conflict handling (Dim 11) | Skip (mark N/A) if: only GET endpoints; or only POST creates with no edit/delete; or spec is auth/config-only. Do NOT skip if PATCH/PUT/DELETE exist on user-editable resources — ask the offline mutations question to confirm. |
| Localisation | `Accept-Language` header already observed in HAR. Or: locale param already in spec. Or: API returns only IDs and timestamps (nothing to localise) |
| Usage pattern | HAR present — infer from request clustering and frequency |
| Observability | X-Request-Id or X-Trace-Id already in HAR responses |
| Rate limiting | X-RateLimit-* headers already in HAR responses |
| Versioning | Version segment already in URL path (e.g. `/v2/`) |

### N/A cross-validation

Before accepting an N/A answer (user-stated or inferred) for RTM, offline, or conflict handling, run these checks:

- **RTM N/A cross-check**: scan the spec for endpoints returning time-sensitive or push-relevant data (live status, order updates, notifications, event changes). If any exist, note the tension: *"The spec includes [endpoint] which returns [data type] — confirm RTM is truly not needed."* Record the tension in the report even if the user confirms N/A.
- **Offline N/A cross-check**: scan the spec for GET endpoints returning data that field workers or low-connectivity users could need locally. If any exist, note the tension before accepting N/A. Record it in the report regardless of the user's answer.
- **Conflict handling N/A cross-check**: scan the spec for PATCH/PUT/DELETE endpoints on user-editable resources. If any exist, note the tension: *"The spec includes [method] [endpoint] — confirm users cannot edit these records offline."* If confirmed offline-editable, Dim 11 applies.

If no such endpoints exist, accept N/A silently.

---

## Step 2 — Identify genuine gaps

For each dimension, classify it as one of:

- **Confirmed from input** — signal present, no question needed
- **Inferrable** — strong contextual signal, state your inference, offer chance to correct
- **Genuinely ambiguous** — must ask, because the answer changes scoring significantly

Only "Genuinely ambiguous" items become questions.

---

## Step 3 — Form the questions

### Question format

Use a single `AskUserQuestion` tool call for all genuinely ambiguous dimensions. Do not make separate sequential calls — batch all questions into one call's `questions` array (1–4 entries; 4 is the tool's hard limit). State any inferences in a brief text message before the call — do not bundle inferences into a question.

Each entry in the `questions` array is a self-contained card:

- `header` — short label, ≤12 characters (e.g. `"Offline"`, `"Real-time"`)
- `question` — one or two sentences referencing a specific finding from the input
- `options` — 2–4 `{ label, description }` objects; `label` is the button text, `description` states the scoring consequence
- `multiSelect` — `false` unless the dimension genuinely allows multiple answers

Do not add a synthetic "skip all" option. The tool always renders an "Other" free-text field, so the user can always decline or answer in their own words.

### Response handling

Each `AskUserQuestion` call returns the user's selected option(s) or free-text answer per question. Handle gracefully:

| Response | How to handle |
|----------|---------------|
| Selected option | Accept and apply to scoring |
| Free text ("Other") | Extract intent, map to closest option |
| Declined / left blank | Apply default from the table at the bottom of this file; note the applied default |

After all calls complete, confirm interpretation before proceeding:

```
Got it. Applying:
- [Dimension]: [answer] → [one-line scoring effect]
- [Dimension]: [default applied] → [reason]
- Inference [accepted / corrected to: X]

Running the audit now...
```

Then proceed to Step 3 of the skill without further questions.

### Question quality rules

**Reference what you found.** Every question must include a specific observation
from the input that motivated it, and must offer explicit answer options.

Bad:
> "Do mobile users need offline access?"

Good:
> "I can see this API returns staff assignments and event schedules — data that
> field workers often need when on-site without reliable connectivity. Do mobile
> users need to access this data offline, or is internet always available in
> your deployment context?"

---

**State your inference when confident, ask for confirmation.**
Don't ask a question when you can make a good inference — state it and let the
user correct it.

Bad:
> "How frequently is this API called?"

Good:
> "The HAR shows ~40 calls to `/events` per session, clustered at launch —
> I'm treating this as a blocking on-launch call for latency scoring.
> Correct if that's wrong."

---

**Make answers easy.** One-word answers should be enough.
Don't write paragraph-length questions that require paragraph-length answers.

---

**Cap at 4 questions.** This is the tool's hard limit per call. If you have more
than 4 genuinely ambiguous items, prioritise by scoring impact (high-point
dimensions first) and apply defaults to the rest.

---

## Step 4 — Scoring impact of each answer

### RTM relevance
- **Not needed** → all RTM rows → N/A, RTM dimension (10 pts) excluded from denominator, no RTM issues raised
- **Needed** → evaluate normally
- **Inferred not needed** (write-only API, static config) → mark N/A with inference note

### Offline sync relevance
- **Not needed** → all offline rows → N/A, Offline dimension (14 pts) excluded from denominator, no offline issues raised
- **Needed** → evaluate normally
- **Inferred not needed** (payments, auth, verification) → mark N/A with inference note

### Offline mutations / locally-persisted mutable collections
- **No mutable collections** (read-only or append-only) → Conflict handling dimension (6 pts) excluded from denominator; all conflict rows → N/A
- **Mutable collections, no offline editing** → Dim 11 still applies (conflict policy matters even for online-only edits from multiple devices); Dim 3 offline mutations criterion → 0 pts if no operationId/queue pattern
- **Mutable collections + offline editing confirmed** → Dim 11 fully applies; Dim 3 offline mutations criterion weighted higher
- **Inferred mutable (PATCH/PUT/DELETE present)** → evaluate Dim 11 normally; state inference

### Localisation relevance
- **Not needed** → all l10n rows → N/A, no deductions for missing localisation
- **Needed** → evaluate and flag gaps as known issues
- **Inferred handled** (locale param in spec) → score as present

### Usage pattern
- **Blocking at launch / every screen** → latency target tightens to <200ms p50; pagination gaps = high severity
- **Background / timer** → latency less critical; offline sync more critical
- **On user action / rare** → standard targets apply
- **Inferred from HAR** → apply inference, note it in report

### Write operation frequency
- **Frequent / automated** → missing idempotency = high severity
- **Rare / manual only** → missing idempotency = medium severity

### Planned improvements
- Record in Notes as "Planned: [description]"
- Score current state only — planned work earns no points

---

## Example: what good dynamic questions look like

Given `acme-events-api.yaml` (the example spec):

**What Claude observes from the spec:**
- Endpoints: `/events` (GET list), `/events/:id` (GET detail), `/events/:id/staff` (GET list), `/bookings` (POST create)
- Pagination: `offset` + `limit` params on `/events` — offset pagination confirmed
- Auth: JWT Bearer — confirmed
- Data: event schedules, staff assignments, bookings — field-worker data
- No RTM endpoints visible
- No locale params
- No cache headers defined
- No idempotency key on POST /bookings
- No PATCH/PUT/DELETE endpoints → Dim 11 inferred N/A (append-only API)

**What Claude infers:**
- This is a scheduling/assignment API for field workers — offline access is plausible
- Staff assignments and event schedules are data workers need on-site
- POST /bookings creates a resource with no idempotency mechanism — retry risk
- No locale params, but the data (names, addresses) could benefit from localisation
- No edit/delete endpoints → conflict handling is N/A; state this as an inference

**Question Claude would ask (batched format):**

First, state inferences in a brief message:
> "Two inferences I'm applying — correct me if wrong: (1) treating this as an on-screen-load API (GET-heavy, no background triggers), which tightens the latency target to <200ms p50; (2) no PATCH/PUT/DELETE endpoints found, so I'm treating conflict handling as N/A — users can create bookings but not edit existing records offline."

Then make one batched call — one entry per ambiguous dimension:

```
AskUserQuestion(
  questions: [
    {
      header: "Offline",
      question: "This API returns staff assignments (/events/{id}/staff) and event schedules — exactly the data field workers need on-site, often with poor connectivity. Do mobile users need this data offline?",
      options: [
        { label: "Yes, offline needed", description: "Score the offline-sync dimension normally" },
        { label: "No, always online",   description: "Mark offline sync N/A" }
      ],
      multiSelect: false
    },
    {
      header: "Real-time",
      question: "The spec has no push, WebSocket, or SSE endpoints. If a schedule changes server-side, does the mobile app need to update automatically?",
      options: [
        { label: "Auto-update needed",    description: "Score the RTM dimension normally" },
        { label: "Manual refresh is fine", description: "Mark RTM N/A" }
      ],
      multiSelect: false
    },
    {
      header: "Idempotency",
      question: "POST /bookings has no Idempotency-Key. A timeout + retry would create a duplicate booking. How often does the mobile app create bookings?",
      options: [
        { label: "Manual only", description: "Missing idempotency = medium severity" },
        { label: "Automated",   description: "Missing idempotency = high severity; blocker applies" },
        { label: "Both",        description: "Missing idempotency = high severity; blocker applies" }
      ],
      multiSelect: false
    },
    {
      header: "Localisation",
      question: "Event names and venue addresses are returned as strings. Will this API serve users in multiple languages or locales?",
      options: [
        { label: "Multiple locales", description: "Score localisation and flag gaps" },
        { label: "Single language",  description: "Mark localisation N/A" }
      ],
      multiSelect: false
    }
  ]
)
```

Notice: no question about auth (JWT confirmed), no question about versioning
(`/v2/` is in the server URL), no question about latency (no HAR, but the
spec structure gives enough signal to score other things), no question about
rate limiting (not in spec, will flag as unknown), no conflict handling question
(no editable resources found).

---

## Defaults if user skips

If the user says "skip", "just go", or similar:

| Dimension | Default |
|-----------|---------|
| RTM | Needed — score normally |
| Offline | Needed — score normally |
| Mutable collections / conflict handling | Mutable — if PATCH/PUT/DELETE exist, score Dim 11 normally; if read-only, mark N/A |
| Localisation | Not needed — mark N/A |
| Usage pattern | Every screen load — strictest latency target |
| Write frequency | Automated — high severity for missing idempotency; idempotency blocker applies if no Idempotency-Key or operationId |
| Planned work | None — score current state |
