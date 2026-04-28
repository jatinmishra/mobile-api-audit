---
name: mobile-api-audit
description: >
  Evaluates whether an API is ready for mobile consumption. Use this skill
  whenever a user wants to assess, audit, or evaluate an API for mobile use,
  even if they do not use those exact words. Triggers include dropping an
  OpenAPI spec, HAR file, or cURL commands and asking for a review, analysis,
  audit, or report; asking if an API is mobile-friendly; asking what is wrong
  with an API for mobile; asking to check or grade an API; or any request to
  generate a mobile readiness report. Input can be OpenAPI or Swagger JSON or
  YAML, HAR traffic captures, raw cURL commands, or any mix of these. Always
  use this skill when the user provides API specs or traffic data and wants any
  kind of quality or readiness assessment.
license: MIT
---

# API Mobile Readiness Skill

Analyse API inputs (OpenAPI specs, HAR files, cURL commands) and produce an exhaustive mobile consumption readiness report as a standalone HTML file.

---

## Process overview

1. **Parse inputs** — detect and read each file the user provides
2. **Ask clarifying questions** — ask the human about context that cannot be inferred from the spec
3. **Extract signals** — pull every mobile-relevant signal from the inputs
4. **Score** — apply the scoring model, using answers from step 2 to set N/A correctly
5. **Write report** — generate a self-contained HTML file
6. **Present** — hand the file back to the user

Do not skip step 2. The clarification answers directly change which dimensions are scored vs marked N/A, which determines whether a missing feature is a real gap or irrelevant noise.

---

## Step 1 — Detect and read inputs

Accept any combination of:

| Format | Extensions | What to look for |
|--------|-----------|-----------------|
| OpenAPI / Swagger | `.yaml`, `.yml`, `.json` | `openapi:`, `swagger:`, or `paths:` key at root |
| HAR capture | `.har`, `.json` with `log.entries` | `log.entries[].request` and `log.entries[].response` |
| cURL commands | `.txt`, `.sh`, `.curl`, or pasted text | Lines starting with `curl ` |
| Mixed / notes | Any | Extract what you can, note the rest |

Read every file the user provides. If a `.json` file is ambiguous, peek at its root keys to distinguish HAR from OpenAPI.

Context the user may provide via flags or conversation:

```
--name      API name (fallback: infer from spec info.title or first path)
--team      Owning team
--consumer  Mobile consumer(s), e.g. "iOS app, Android app"
--domain    Data domain, e.g. "Events", "Bookings"
--output    Output path (default: ./mobile-readiness-report.html)
```

---

## Step 2 — Ask clarifying questions

Read `references/clarification-questions.md` before this step.

**Read the inputs fully first. Then ask only what you cannot determine.**

### The process

1. **Build a context model** from the inputs — what does this API do, what data does it serve, what signals are present or absent across each dimension
2. **Classify each dimension** as: confirmed from input / inferrable / genuinely ambiguous
3. **For inferrable items** — state your inference in the message, offer the user a chance to correct it. Do not ask a question.
4. **For genuinely ambiguous items** — ask one targeted question per item that references a specific observation from the input
5. **Cap at 5 questions**. If more than 5 items are ambiguous, prioritise by scoring weight

### What makes a good question

Every question must:
- Reference something specific found in the input (a field name, endpoint, observed behaviour)
- Be answerable in one word
- Only be asked if the answer materially changes the score or verdict

A question that could be asked without reading the file is a bad question.

### Applying the answers

| Answer | Effect on scoring |
|--------|------------------|
| RTM not needed | All RTM rows → N/A, award full 10 pts, no RTM issues |
| Offline not needed | All offline rows → N/A, award full 12 pts, no offline issues |
| Localisation not needed | All l10n rows → N/A, no deductions for missing l10n |
| Usage = launch/every-screen | Latency target tightens to <200ms p50; pagination gaps → high severity |
| Usage = background/rare | Latency less critical; offline sync weighted higher |
| Planned improvements noted | Record in Notes as "Planned: [desc]"; score current state only |

### If the user skips

If the user says "skip", "just run it", or similar — apply the defaults from `references/clarification-questions.md` and proceed immediately. Do not ask again.

---

## Step 3 — Extract signals

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

---

## Step 4 — Score across 10 dimensions

Read `references/scoring-model.md` for exact scoring rules and point allocations.
Apply clarification answers first — dimensions marked N/A by the user score their full points and are excluded from the known issues list.

| Dimension | Max pts | Conditional? | Key signals |
|-----------|---------|-------------|-------------|
| Performance & scalability | 20 | No — always scored | Pagination type, batching, latency p50/p95, field filtering, compression |
| Error handling & stability | 15 | No — always scored | Error schema consistency, idempotency, timeout behaviour, 4xx vs 5xx |
| Offline sync | 12 | **Yes — skip if user says not needed** | Delta/full sync support, sync key, tombstones, cacheability |
| Caching & payload | 10 | No — always scored | Cache-Control, ETag, CDN, minimal fields returned |
| Real-time / RTM | 10 | **Yes — skip if user says not needed** | RTM coverage, contract match, reconnect behaviour |
| Security | 10 | No — always scored | Auth method, token refresh, scopes, HTTPS, PII exposure |
| Rate limiting | 8 | No — always scored | Limits exist, documented, 429 returned, Retry-After header |
| Versioning & deprecation | 6 | No — always scored | Version in URL/header, sunset policy, changelog |
| Testing & mocks | 5 | No — always scored | OpenAPI spec currency, sandbox URL, contract tests |
| Observability | 4 | No — always scored | Dashboard links, SLA defined, tracing |
| **Total** | **100** | | Deduct 2 pts per confirmed known issue |

Verdict bands: **75–100** Mobile-ready · **50–74** Ready with changes · **0–49** Not mobile-ready

---

## Step 5 — Generate the HTML report

Read `references/report-template.md` for the full HTML template and all section definitions before writing the file.

The report must be:
- **Self-contained** — single `.html` file, no external dependencies, works offline
- **Copy-pasteable into Confluence** — selecting all and pasting must produce native tables and headings
- **Complete** — all 17 sections present; use "Not found in input" for anything not determinable, never omit a section

Sections:

| # | Section | Scored |
|---|---------|--------|
| 1 | API overview | — |
| 2 | Data characteristics | — |
| 3 | Mobile usage patterns | — |
| 4 | Performance & scalability | ✓ 20 pts |
| 5 | Caching & payload optimisation | ✓ 10 pts |
| 6 | Offline sync compatibility | ✓ 12 pts |
| 7 | Real-time / RTM | ✓ 10 pts |
| 8 | Error handling & stability | ✓ 15 pts |
| 9 | Rate limiting & throttling | ✓ 8 pts |
| 10 | Security | ✓ 10 pts |
| 11 | Localisation & i18n | — |
| 12 | Versioning & deprecation | ✓ 6 pts |
| 13 | Testing & mock availability | ✓ 5 pts |
| 14 | Monitoring & observability | ✓ 4 pts |
| 15 | Known issues | deductions |
| 16 | Proposed improvements | — |
| 17 | Final verdict | — |

Each evaluation row has four fields:
- **Criterion** — what is being assessed
- **Status** — the finding (with a colour class: `good` / `warn` / `bad` / `na` / `unknown`)
- **Notes** — specific evidence from the input, parameter names, example values, or "Not found in input"
- **Evidence** — the exact line/field in the source that led to this finding (e.g. `paths./events.get.parameters[2].name = "offset"`)

---

## Step 6 — Write and present the file

Write the report to the output path (default: `./mobile-readiness-report.html`).

Then tell the user:
- The output path
- The final score and verdict
- The top 3 confirmed issues
- How to paste into Confluence (select all → copy → paste)

Keep this summary to 5–8 lines. The report has the full detail.

---

## Rules

- **Always ask before scoring.** Never skip the clarification step. The answers determine which dimensions are N/A vs scored.
- **N/A ≠ skip.** When a dimension is N/A, still include its section in the report — mark every row as N/A with a note explaining why (e.g. "User confirmed: offline access not required for this API").
- **N/A dimensions score full points.** A dimension that doesn't apply is not a gap — it scores its maximum and is excluded from known issues.
- **Never omit a section.** If you cannot determine a value from the inputs, write "Not found in input" and set status to `unknown`. Do not skip the row.
- **Never fabricate.** If a signal is absent from the inputs, say so — do not assume a best-case value.
- **Be specific.** Notes must reference actual field names, header values, or parameter names from the input. "Pagination not found" is not specific. "No `cursor`, `after`, `before`, or `next_cursor` parameter found in any path" is specific.
- **Score conservatively.** Absence of evidence is evidence of absence for mobile readiness. If a feature isn't in the spec, assume it doesn't exist.
- **Known issues = confirmed only.** Only list issues you found direct evidence for. Speculative issues go in the notes column of the relevant section row, not in the known issues list.
- **Planned work = noted, not scored.** If the user mentions planned improvements, record them in Notes as "Planned: [description]". Score the current state only.
