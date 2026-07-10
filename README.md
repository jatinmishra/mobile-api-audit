# mobile-api-audit

A Claude Code skill that analyses API inputs and generates an exhaustive mobile consumption readiness report as a standalone HTML file.

Drop in an OpenAPI spec, HAR traffic capture, or cURL commands — the skill extracts every mobile-relevant signal, scores the API across 11 dimensions, and writes a complete report you can open in any browser.

---

## What it evaluates

| # | Section | Max pts |
|---|---------|---------|
| 1–3 | API overview, data characteristics, mobile usage patterns | — |
| 4 | Performance & scalability (pagination, batching, latency, compression) | 17 |
| 5 | Caching & payload optimisation (Cache-Control, ETag, CDN) | 10 |
| 6 | Offline sync (delta sync, tombstones, cursor expiry) | 14 |
| 7 | Real-time / RTM (coverage, contract match, reconnect) | 10 |
| 8 | Error handling & stability (schema, recovery fields, idempotency) | 15 |
| 9 | Rate limiting & throttling (headers, 429, Retry-After) | 8 |
| 10 | Security (auth, token refresh, PKCE, HTTPS, PII exposure) | 10 |
| 11 | Conflict handling (policy, response shape, code) — *conditional* | 6 |
| 12 | Localisation & i18n | — |
| 13 | Versioning & deprecation (sunset policy, min app version) | 5 |
| 14 | Testing & mock availability (spec, sandbox) | 3 |
| 15 | Monitoring & observability (request ID) | 2 |
| 16–18 | Known issues, improvements, final verdict | deductions |

Total: **100 pts**. Three dimensions — Offline sync, RTM, and Conflict handling — are *conditional*: when confirmed not applicable, they are excluded from both the earned total and the denominator (see `references/scoring-model.md`).

**Verdict bands:** 75–100 Mobile-ready · 50–74 Ready with changes · 0–49 Not mobile-ready

---

## Installation

### From skill.sh

```bash
claude skill install mobile-api-audit
```

### From GitHub

```bash
git clone https://github.com/jatinmishra/mobile-api-audit
cd mobile-api-audit
python scripts/package.py
claude skill install mobile-api-audit.skill
```

### Manual (copy into your project)

Copy the `mobile-api-audit/` folder into your project's skills directory and reference it from your `CLAUDE.md`.

---

## Usage

Once installed, just talk to Claude in your project:

```
Evaluate this API for mobile readiness: ./specs/events-api.yaml
```

```
Run a mobile readiness check on these files: ./openapi.json ./traffic.har
```

```
Is our bookings API mobile-ready? Here's the spec and some captured requests.
[attach files]
```

Claude will automatically detect the input types, extract signals, score, and write `mobile-readiness-report.html`.

### With explicit options

You can also be specific:

```
Run mobile readiness evaluation on ./specs/events.yaml
  - API name: Events API
  - Team: Platform
  - Consumer: iOS app, Android app
  - Output: ./reports/events-mobile-readiness.html
```

---

## Accepted input formats

| Format | Extensions | What the skill extracts |
|--------|-----------|------------------------|
| OpenAPI / Swagger | `.yaml`, `.yml`, `.json` | Paths, schemas, auth, pagination params, error shapes, headers defined, versioning |
| HAR traffic capture | `.har`, `.json` | Real latency (p50/p95), payload sizes, response headers, status codes, auth type |
| cURL commands | `.txt`, `.sh`, `.curl` | Endpoints, headers, auth type, methods |
| Mixed / notes | Any | Best-effort extraction |

Pass multiple files — the skill correlates signals across all of them.

---

## Output

A single `mobile-readiness-report.html` file that:

- Opens in any browser with no server needed
- Shows a score panel with per-dimension bars
- Has all 18 sections fully filled from your inputs
- Marks anything not found in inputs as "Not found in input" (never fabricates)

---

## Project structure

```
mobile-api-audit/
├── SKILL.md                        ← skill entry point (read by Claude Code)
├── LICENSE.txt
├── README.md
├── references/
│   ├── clarification-questions.md  ← question bank and defaults for Step 2
│   ├── extraction-guide.md         ← full signal extraction checklist
│   ├── scoring-model.md            ← exact point allocations per criterion
│   ├── report-template.md          ← HTML structure and all section definitions
│   └── design-review.md            ← recorded design debate behind the scoring model
├── examples/
│   └── acme-events-api.yaml        ← example OpenAPI spec for testing
├── evals/
│   ├── README.md                   ← how to run and extend evals
│   ├── trigger/                    ← does the skill activate on the right prompts?
│   ├── questions/                  ← are clarifying questions grounded in the spec?
│   └── report/                     ← does the report identify issues and avoid fabrication?
└── scripts/
    ├── package.py                  ← bundles skill into .skill archive
    ├── run_evals.py                ← runs all three eval suites
    └── eval_quick.py               ← fast single-suite smoke test
```

---

## Example output

Given `acme-events-api.yaml` (the deliberately-flawed example spec in this repo):

```
Score:   Not mobile-ready  (low earned score after deductions)
Verdict: Not mobile-ready

Top issues:
  [high]  Offset pagination on /events — will drift on live data
  [high]  POST /bookings has no idempotency mechanism — retry will duplicate bookings
  [med]   No Cache-Control headers defined — mobile client cannot cache responses
  [med]   No rate limiting documented — backoff logic cannot be written

Report:  ./mobile-readiness-report.html
```

> The exact number depends on the clarifying answers (which conditional
> dimensions apply). See `examples/acme-events-api-report.html` for a full
> generated report.

---

## Evals

Three suites validate the skill end-to-end:

| Suite | What it tests |
|-------|--------------|
| `trigger` | Skill activates on the right prompts and stays quiet on others |
| `questions` | Clarifying questions are grounded in the spec, not generic boilerplate |
| `report` | Report correctly flags issues, scores N/A dimensions, and never fabricates |

```bash
python scripts/run_evals.py              # all suites
python scripts/run_evals.py --suite report --verbose
python scripts/run_evals.py --no-trigger # skip trigger (no claude CLI needed)
```

Exit code 0 if overall pass rate ≥80%, exit code 1 otherwise — suitable for CI. See `evals/README.md` for full details and CI integration instructions.

---

## Contributing

Issues and PRs welcome. The scoring model is in `references/scoring-model.md` — if you think a criterion is weighted incorrectly or is missing, that's the place to start.

---

## License

MIT — see `LICENSE.txt`
