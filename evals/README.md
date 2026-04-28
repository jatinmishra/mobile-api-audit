# Evals

Three eval suites that together validate the skill end-to-end.

---

## Suites

### 1. Trigger (`evals/trigger/`)

**What it tests:** Does the skill activate on the right prompts and stay quiet on the wrong ones?

**How it works:** Runs each query through `claude -p` and detects whether Claude reads `SKILL.md`. Uses the [skill-creator](https://github.com/anthropics/skill-creator) runner if available, otherwise falls back to a subprocess heuristic.

**Eval set:** `eval_set.json` — 10 should-trigger + 5 should-not-trigger queries

**Pass criteria:** Skill triggers (or doesn't) on ≥50% of runs per query

---

### 2. Question quality (`evals/questions/`)

**What it tests:** Are the clarifying questions actually derived from what's in the file, or are they generic boilerplate?

**How it works:** Feeds each fixture through the skill's Step 2 prompt, captures the questions Claude generates, then uses an LLM judge to check each assertion:
- `should_ask` — question is present AND references a specific finding from the file
- `should_not_ask` — question is absent because the answer is determinable from the spec
- `should_infer_not_ask` — output states an inference instead of asking

**Fixtures:**
- `fixtures/` — `payment-api.yaml`, `har-with-headers.har`
- `../../examples/acme-events-api.yaml` — the main example spec

**Why this matters:** A skill that asks "do you need offline sync?" without referencing the staff assignment endpoints it found is no better than a static questionnaire. This suite enforces that questions show understanding.

---

### 3. Report accuracy (`evals/report/`)

**What it tests:** Does the generated report correctly identify issues, correctly score N/A dimensions, and never fabricate features that aren't in the spec?

**How it works:**
1. Runs the full skill process (with pre-answered context questions) to generate an HTML report
2. Uses the grader agent (`grader.md`) to check each expectation against the report
3. Specifically checks for fabrication — positive claims about features not in the input

**Fixtures:**
- `../../examples/acme-events-api.yaml` — deliberately flawed (offset pagination, missing idempotency, PII, no cache headers)
- `fixtures/well-formed-api.yaml` — well-formed (cursor pagination, idempotency key, cache headers, OAuth2 with refresh)

**Key expectations checked:**
- Offset pagination flagged as warn/bad
- POST /bookings missing idempotency flagged
- PII in StaffMember + Event schemas flagged
- Auth correctly scored as good (JWT confirmed)
- Cache-Control NOT fabricated (not in spec)
- RTM/offline sections correctly marked N/A when user said not needed
- Score between 35–60 for flawed spec, 75–100 for well-formed spec
- Correct verdict derived from score

**Output:** HTML reports and `grading.json` saved to `evals/report/outputs/`

---

## Running evals

```bash
# Run all suites
python scripts/run_evals.py

# One suite only
python scripts/run_evals.py --suite trigger
python scripts/run_evals.py --suite questions
python scripts/run_evals.py --suite report

# Skip trigger suite (faster, no claude CLI needed)
python scripts/run_evals.py --no-trigger

# Verbose output — shows failure evidence
python scripts/run_evals.py --verbose

# Control trigger suite runs (default: 3 per query)
python scripts/run_evals.py --suite trigger --runs 5 --workers 8
```

**Requirements:**
- `claude` CLI on PATH
- Python 3.10+

---

## Interpreting results

| Pass rate | Meaning |
|-----------|---------|
| ≥80% | Healthy — skill is working correctly |
| 60–79% | Needs attention — run with `--verbose` to identify failures |
| <60% | Something is broken — check the grading.json files in `outputs/` |

Exit code 0 if overall ≥80%, exit code 1 otherwise — suitable for CI.

---

## Adding evals

**New trigger case:** Add to `evals/trigger/eval_set.json`
```json
{
  "id": "t16",
  "query": "your new query here",
  "should_trigger": true,
  "notes": "Why this should trigger"
}
```

**New question case:** Add a fixture to `evals/questions/fixtures/` and add a case to `evals/questions/eval_set.json`

**New report case:** Add a fixture to `evals/report/fixtures/` and add a case to `evals/report/eval_set.json`

---

## CI integration

```yaml
# .github/workflows/evals.yml
name: Skill Evals
on: [push, pull_request]
jobs:
  evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: python scripts/run_evals.py --no-trigger --suite questions
      - run: python scripts/run_evals.py --no-trigger --suite report
```

Note: The trigger suite is excluded from CI because it requires the `claude` CLI.
Run it locally before publishing changes to `SKILL.md`'s description field.
