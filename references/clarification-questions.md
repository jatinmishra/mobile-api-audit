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
- Are there endpoints that return time-sensitive or frequently-changing data? (RTM may matter)
- Are there endpoints returning data users act on in the field? (offline may matter)
- Are there locale or language parameters? (l10n may already be handled)

### HAR signals (if present)
- How many requests per session? (infer usage frequency)
- Are requests clustered at app open or spread through a session? (infer usage pattern)
- Are requests sequential or parallel? (dependency chain)
- What are the actual latency p50/p95? (no need to ask)
- Are there 401s, 429s, 5xxs in the traffic? (auth and stability signals)

### Inference rules — when NOT to ask

| Dimension | Skip the question if... |
|-----------|------------------------|
| RTM | Only POST/write endpoints — nothing to push. Or: ephemeral data (auth tokens, search). Or: HAR shows no websocket/SSE connections and data is clearly static (config, lookup tables) |
| Offline sync | Payment endpoints, auth flows, OTP/verification — these are inherently online. Or: spec explicitly has no list/get endpoints worth caching |
| Localisation | `Accept-Language` header already observed in HAR. Or: locale param already in spec. Or: API returns only IDs and timestamps (nothing to localise) |
| Usage pattern | HAR present — infer from request clustering and frequency |
| Observability | X-Request-Id or X-Trace-Id already in HAR responses |
| Rate limiting | X-RateLimit-* headers already in HAR responses |
| Versioning | Version segment already in URL path (e.g. `/v2/`) |

---

## Step 2 — Identify genuine gaps

For each dimension, classify it as one of:

- **Confirmed from input** — signal present, no question needed
- **Inferrable** — strong contextual signal, state your inference, offer chance to correct
- **Genuinely ambiguous** — must ask, because the answer changes scoring significantly

Only "Genuinely ambiguous" items become questions.

---

## Step 3 — Form the questions

### Question quality rules

**Reference what you found.** Every question must include a specific observation
from the input that motivated it.

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

**Cap at 5 questions.** If you have more than 5 genuinely ambiguous items,
prioritise by scoring impact (high-point dimensions first).

---

## Step 4 — Scoring impact of each answer

### RTM relevance
- **Not needed** → all RTM rows → N/A, award full 10 pts, no RTM issues raised
- **Needed** → evaluate normally
- **Inferred not needed** (write-only API, static config) → mark N/A with inference note

### Offline sync relevance
- **Not needed** → all offline rows → N/A, award full 12 pts, no offline issues raised
- **Needed** → evaluate normally
- **Inferred not needed** (payments, auth, verification) → mark N/A with inference note

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

**What Claude infers:**
- This is a scheduling/assignment API for field workers — offline access is plausible
- Staff assignments and event schedules are data workers need on-site
- POST /bookings creates a resource with no idempotency mechanism — retry risk
- No locale params, but the data (names, addresses) could benefit from localisation

**Questions Claude would ask:**

```
I've read the spec. A few things I can't determine from the file alone:

1. **Offline access** — This API serves staff assignments and event schedules,
   which field workers often need on-site without connectivity. Do mobile users
   need this data offline, or is internet always available?
   → Yes, offline needed / No, always online

2. **Real-time updates** — The spec has no push/websocket endpoints. If a
   schedule changes server-side, does the mobile app need to update
   automatically, or is a manual refresh acceptable?
   → Auto-update needed / Manual refresh is fine

3. **Booking retries** — POST /bookings has no idempotency key. If a booking
   request times out and the app retries, it would create a duplicate. How
   often does the mobile app create bookings — manually by a user, or
   automatically (e.g. bulk assignment flow)?
   → Manual only / Automated / Both

4. **Localisation** — Will this API serve users in multiple languages? The
   event names and venue addresses returned could potentially be localised.
   → Yes, multiple locales / No, single language only

One inference I'm applying — correct me if wrong:
→ Treating this as an on-screen-load API based on the GET-heavy pattern.
  This tightens the latency target to <200ms p50.
```

Notice: no question about auth (JWT confirmed), no question about versioning
(`/v2/` is in the server URL), no question about latency (no HAR, but the
spec structure gives enough signal to score other things), no question about
rate limiting (not in spec, will flag as unknown).

---

## Defaults if user skips

If the user says "skip", "just go", or similar:

| Dimension | Default |
|-----------|---------|
| RTM | Needed — score normally |
| Offline | Needed — score normally |
| Localisation | Not needed — mark N/A |
| Usage pattern | Every screen load — strictest latency target |
| Write frequency | Manual — medium severity for missing idempotency |
| Planned work | None — score current state |
