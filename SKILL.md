---
name: mobile-api-audit
description: >
  Evaluates whether an API is ready for mobile consumption. Use this skill
  whenever a user wants to assess, audit, or evaluate an API for mobile use,
  even if they do not use those exact words. Triggers include: dropping an
  OpenAPI spec, HAR file, or cURL commands and asking for a review, analysis,
  audit, or report; asking if an API is mobile-friendly; asking what is wrong
  with an API for mobile; asking to check or grade an API; or any request to
  generate a mobile readiness report. Input can be OpenAPI or Swagger JSON or
  YAML, HAR traffic captures, raw cURL commands, or any mix of these. Before
  proceeding, if the user provides no mobile context and no mobile endpoints
  are evident from the input, ask: "Is this API consumed by a mobile client?"
  — if the answer is no, decline politely and explain the skill is scoped to
  mobile API readiness. Only use this skill when the API is confirmed or likely
  mobile-consumed.
license: MIT
---

# API Mobile Readiness Skill

Analyse API inputs (OpenAPI specs, HAR files, cURL commands) and produce an exhaustive mobile consumption readiness report as a standalone HTML file.

---

## Process overview

1. **Read inputs** — detect and parse every file the user provides
2. **Ask clarifying questions** — use `AskUserQuestion` to collect context that cannot be inferred from the spec
3. **Extract signals** — pull every mobile-relevant signal from the inputs
4. **Score** — apply the scoring model, using answers from step 2 to set N/A correctly
5. **Write report** — generate a self-contained HTML file
6. **Present** — hand the file back to the user

---

### Step 1 — Detect and read inputs

Accept any combination of:

| Format | Extensions | What to look for |
|--------|-----------|-----------------|
| OpenAPI / Swagger | `.yaml`, `.yml`, `.json` | `openapi:`, `swagger:`, or `paths:` key at root |
| HAR capture | `.har`, `.json` with `log.entries` | `log.entries[].request` and `log.entries[].response` |
| cURL commands | `.txt`, `.sh`, `.curl`, or pasted text | Lines starting with `curl ` |
| Mixed / notes | Any | Extract what you can, note the rest |

Read every file the user provides. If a `.json` file is ambiguous, peek at its root keys to distinguish HAR from OpenAPI.

#### Partially supported formats

| Format | How to handle |
|--------|--------------|
| GraphQL SDL (`.graphql`, `.gql`) | Extract query/mutation/subscription types, field names, auth directives. Note coverage gaps: compression, caching, and HTTP-level headers are not derivable from SDL. |
| gRPC `.proto` files | Extract service methods, message shapes, streaming patterns. Note that HTTP/2 headers and latency scoring require a HAR from a gRPC-web proxy. |
| Multi-file OpenAPI with external `$ref` | Resolve local `$ref` targets. For unresolvable external `$ref` (remote URLs, missing files), note which schemas are unresolved and score only available portions. |

For partially supported formats: extract what is available, state coverage gaps in Section 1, and score only what can be determined.

Context the user may provide via flags or conversation:

```
--name      API name (fallback: infer from spec info.title or first path)
--team      Owning team
--consumer  Mobile consumer(s), e.g. "iOS app, Android app"
--domain    Data domain, e.g. "Events", "Bookings"
--output    Output path (default: ./mobile-readiness-report.html)
--mode      Output verbosity: full (default) or quick (Sections 16–18 only)
```

In `--mode quick`, skip Sections 1–15 and generate only the Known Issues (S16), Proposed Improvements (S17), and Final Verdict (S18) tables. Add a note at the top of the file: *"Quick mode — full report available by re-running without --mode quick."*

### Step 2 — Ask clarifying questions via AskUserQuestion

Read `references/clarification-questions.md` for question-building rules before this step.

**You are running inside Claude Code. Use the `AskUserQuestion` tool for each clarifying question.** This tool pauses execution, renders an interactive prompt with selectable options, waits for the user's input, and returns their answer — exactly like Claude Code's native Q&A. Do NOT print a text block of questions. Call the tool instead.

#### Process

1. **Build a context model** from the inputs — classify each dimension as confirmed / inferrable / genuinely ambiguous
2. **Skip confirmed dimensions** — no call needed if the signal is present in the spec or HAR
3. **State inferences** — if you can infer a value confidently, say so in a brief message before the question call: *"I'm treating this as an on-screen-load API based on the GET-heavy pattern — correct me if wrong."*
4. **Batch all genuinely ambiguous dimensions into a single `AskUserQuestion` call.** Pass every question in one call's `questions` array — one array entry per dimension. Do not make separate sequential calls.
5. **Cap at 4 questions per call** — this is the tool's hard limit. If more than 4 items are ambiguous, prioritise by scoring weight and drop the rest to defaults.

#### AskUserQuestion call format

`AskUserQuestion` takes a `questions` array (1–4 entries). Each entry is a self-contained card with its own selectable options — **not** a single free-text prompt. Each entry has:

- `header` — a short label, ≤12 characters (e.g. `"Offline"`, `"Real-time"`, `"Idempotency"`)
- `question` — one or two sentences that reference a specific finding from the input
- `options` — 2–4 objects, each `{ label, description }`. The `label` is the button text; the `description` explains the scoring consequence
- `multiSelect` — `false` unless the dimension genuinely allows multiple answers

Do not add a synthetic "skip all" option — the tool always renders an "Other" free-text field and the user can decline. Handle a skip/decline by applying defaults from `references/clarification-questions.md`.

**Example call for acme-events-api.yaml** (four genuinely-ambiguous dimensions):

```
AskUserQuestion(
  questions: [
    {
      header: "Offline",
      question: "This API returns staff assignments (/events/{id}/staff) and event schedules — data field workers often need on-site with poor connectivity. Do mobile users need offline access?",
      options: [
        { label: "Yes, offline needed", description: "Score the offline-sync dimension normally" },
        { label: "No, always online",   description: "Mark offline sync N/A — excluded from the denominator" }
      ],
      multiSelect: false
    },
    {
      header: "Real-time",
      question: "The spec has no WebSocket, SSE, or push endpoints. If a schedule changes server-side, does the mobile app need to update automatically?",
      options: [
        { label: "Auto-update needed",  description: "Score the RTM dimension normally" },
        { label: "Manual refresh is fine", description: "Mark RTM N/A — excluded from the denominator" }
      ],
      multiSelect: false
    },
    {
      header: "Idempotency",
      question: "POST /bookings has no Idempotency-Key. A timeout + retry would silently create a duplicate booking. How often does the app create bookings?",
      options: [
        { label: "Manual only", description: "Missing idempotency = medium severity" },
        { label: "Automated",   description: "Missing idempotency = high severity; idempotency blocker applies" },
        { label: "Both",        description: "Missing idempotency = high severity; idempotency blocker applies" }
      ],
      multiSelect: false
    },
    {
      header: "Localisation",
      question: "Event names, venue addresses, and staff contact details are plain strings. Will this API serve users in multiple languages or locales?",
      options: [
        { label: "Multiple locales", description: "Score localisation and flag gaps" },
        { label: "Single language",  description: "Mark localisation N/A — no deductions" }
      ],
      multiSelect: false
    }
  ]
)
```

#### If the user skips or declines a question

If the user picks "Other" and declines, leaves a question unanswered, or says "just go" / "skip", apply the default for that dimension from `references/clarification-questions.md` and proceed to Step 3 without further interaction.

#### Applying the answers

| Answer | Effect on scoring |
|--------|------------------|
| RTM not needed | Cross-validate first: check if spec contains time-sensitive data endpoints (live status, notifications, order changes). If so, note the tension before applying N/A. If confirmed, all RTM rows → N/A, RTM dimension (10 pts) excluded from denominator, no RTM issues raised. |
| Offline not needed | Cross-validate first: check if spec contains GET endpoints returning data users act on in the field. If so, note the tension before applying N/A. If confirmed, all offline rows → N/A, Offline dimension (14 pts) excluded from denominator, no offline issues raised. |
| No locally-persisted mutable collections | All conflict handling rows → N/A, Conflict handling dimension (6 pts) excluded from denominator, no conflict issues raised. Apply when API is read-only, append-only, or auth/config-only. Cross-validate: if PATCH/PUT/DELETE endpoints exist on user-editable resources, note the tension before accepting N/A. |
| Localisation not needed | All l10n rows → N/A, no deductions for missing l10n |
| Usage = launch/every-screen | Latency target tightens to <200ms p50; pagination gaps → high severity |
| Usage = background/rare | Latency less critical; offline sync weighted higher |
| Planned improvements noted | Record in Notes as "Planned: [desc]"; score current state only |

After all calls complete, briefly confirm your interpretation then proceed immediately to Step 3:

```
Got it. Applying:
- [Dimension]: [answer] → [one-line scoring effect]
- Inference [accepted / corrected to: X]

Running the audit now...
```

---

### Step 3 — Extract signals

Read `references/extraction-guide.md` for the full extraction checklist before analysing.

Quick reference — signals to extract per input type:

**From OpenAPI:**
- `info.title`, `info.version`, `servers[]`
- `paths` — HTTP methods, parameter names (detect `offset`/`limit` vs cursor params), response schemas
- `components.securitySchemes` — auth type
- `components.schemas` — response shape, field count, nesting depth
- `security` — required scopes
- Response headers defined: `Cache-Control`, `ETag`, `X-RateLimit-*`, `Retry-After`, `Sunset`
- Pagination patterns: `cursor`, `after`, `before`, `next_cursor`, `page`, `offset`, `limit`
- Error response schemas — consistent shape across endpoints?
- `x-` extensions that indicate versioning, deprecation, or rate limits

**From HAR:**
- `entries[].request.url` — base URL, path patterns, version in path
- `entries[].request.method` — HTTP methods used
- `entries[].request.headers` — `Authorization` type, `Accept-Encoding`, `Accept-Language`
- `entries[].response.status` — error codes present
- `entries[].response.headers` — `Cache-Control`, `Content-Encoding`, `ETag`, `X-RateLimit-*`, `Retry-After`, `Content-Type`
- `entries[].response.content.size` — payload sizes (compute p50 and p95)
- `entries[].time` — latency values (compute p50 and p95)
- `entries[].response.content.text` — response body shape (pagination keys, error structure)

**From cURL:**
- URL path — version segment, endpoint name
- `-H "Authorization: ..."` — auth type
- `-H "Accept-Encoding: ..."` — compression requested
- `-H "Accept-Language: ..."` — localisation
- `--data` / `-d` — request body shape
- `-X` — HTTP method

### Step 4 — Score across 11 dimensions

Read `references/scoring-model.md` for exact scoring rules and point allocations.
Apply clarification answers first — dimensions marked N/A by the user are excluded from both the earned total and the applicable maximum, and are excluded from the known issues list.

| Dimension | Max pts | Conditional? | Key signals |
|-----------|---------|-------------|-------------|
| Performance & scalability | 17 | No — always scored | Pagination type, batching, HTTP/2, latency p50, retry policy, field filtering |
| Error handling & stability | 15 | No — always scored | Error schema consistency, machine-readable codes, recovery fields (retryable/userActionRequired/queueAction), idempotency, 4xx vs 5xx |
| Offline sync | 14 | **Yes — excluded from denominator if N/A** | Sync mechanism (opaque cursor > timestamp > full), tombstones + access removal, offline mutations + status echoing, cursor expiry error classes, cache-friendly |
| Caching & payload | 10 | No — always scored | Cache-Control, ETag, CDN, minimal fields returned |
| Real-time / RTM | 10 | **Yes — excluded from denominator if N/A** | RTM coverage, contract match, reconnect behaviour |
| Security | 10 | No — always scored | Auth method (OAuth2/JWT only), PKCE, auth completeness (refresh + step-up + revocation), HTTPS |
| Rate limiting | 8 | No — always scored | Limits exist, documented, 429 returned, Retry-After header |
| Versioning & deprecation | 5 | No — always scored | Version in URL/header, sunset policy, minimum supported app version |
| Testing & mocks | 3 | No — always scored | OpenAPI spec currency, sandbox URL |
| Observability | 2 | No — always scored | Request ID in responses |
| Conflict handling | 6 | **Yes — excluded from denominator if N/A** | Conflict policy declared per resource, conflict response shape (clientBaseVersion/serverVersion/conflictingFields), machine-readable conflict code |
| **Total** | **100** | | |

**Scoring:** Adjusted score = (earned pts) / (100 − N/A dimension maxima) × 100. Deductions are tiered: Critical −5, Major −3, Minor −1 per issue.

Verdict bands: **75–100** Mobile-ready · **50–74** Ready with changes · **0–49** Not mobile-ready

### Step 5 — Generate the HTML report

Read `references/report-template.md` for the full HTML template and all section definitions before writing the file.

The report must be:
- **Self-contained** — single `.html` file, no external dependencies, works offline
- **Copy-paste friendly** — selecting all and pasting into any doc tool (Confluence, Notion, Jira, etc.) must produce native tables and headings
- **Complete** — all 18 sections present; use "Not found in input" for anything not determinable, never omit a section

Each evaluation row has four fields:
- **Criterion** — what is being assessed
- **Status** — the finding (with a colour class: `good` / `warn` / `bad` / `na` / `unknown`)
- **Notes** — specific evidence from the input, parameter names, example values, or "Not found in input"
- **Evidence** — the exact line/field in the source that led to this finding (e.g. `paths./events.get.parameters[2].name = "offset"`)

### Step 6 — Write and present the file

Write the report to the output path (default: `./mobile-readiness-report.html`).

Then tell the user:
- The output path
- The final score and verdict (from Section 18)
- The top 3 confirmed issues

Keep this summary to 5–8 lines. The report has the full detail.

---

## Rules

- **One turn if pre-supplied, two turns otherwise.** If the user's first message includes explicit answers to all clarification dimensions (RTM, offline, locale, usage pattern), skip the question step and proceed in one turn. State the applied context before scoring (e.g. *"Applying: RTM not needed, offline needed, single locale, blocking on launch — running audit now..."*). If any dimension is ambiguous, make one batched `AskUserQuestion` call with all questions (max 4) as entries in a single `questions` array. After the user replies, run the audit in a final turn.
- **Ask before scoring when needed.** If any clarification dimension is genuinely ambiguous and not pre-supplied, use the AskUserQuestion step. The answers determine which dimensions are N/A vs scored.
- **N/A ≠ skip.** When a dimension is N/A, still include its section in the report — mark every row as N/A with a note explaining why.
- **N/A dimensions are excluded from both numerator and denominator.** A dimension that doesn't apply neither helps nor hurts the score — exclude its points from both the earned total and the applicable maximum. Do not award its points; do not penalise their absence. See scoring-model.md for the adjusted-score formula.
- **Never omit a section.** If you cannot determine a value from the inputs, write "Not found in input" and set status to `unknown`. Do not skip the row.
- **Never fabricate.** If a signal is absent from the inputs, say so — do not assume a best-case value.
- **Be specific.** Notes must reference actual field names, header values, or parameter names from the input.
- **Score conservatively.** Absence of evidence is evidence of absence for mobile readiness. If a feature isn't in the spec, assume it doesn't exist.
- **Known issues = confirmed only.** Only list issues you found direct evidence for. Speculative issues go in the notes column, not the known issues list.
- **Planned work = noted, not scored.** If the user mentions planned improvements, record them in Notes as "Planned: [description]". Score the current state only.
