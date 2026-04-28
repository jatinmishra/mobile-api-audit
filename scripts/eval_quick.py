#!/usr/bin/env python3
"""
mobile-api-audit — quick eval
==============================
One `claude -p` call + string/regex checks. No API key needed.

What it tests (against acme-events-api.yaml, a deliberately flawed spec):
  - Report is valid HTML with all 17 sections
  - Offset pagination flagged
  - POST /bookings missing idempotency flagged
  - PII exposure (email + phone fields) flagged
  - JWT/Bearer auth scored positively
  - Score is below 60 (flawed spec should never score high)
  - Verdict is not "Mobile-ready"
  - Cache-Control not falsely claimed as good (no fabrication)
  - RTM section marked N/A (pre-answered context)

Usage:
  python scripts/eval_quick.py
  python scripts/eval_quick.py --verbose

Requirements:
  claude CLI on PATH (claude.ai/code)
"""

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT    = pathlib.Path(__file__).parent.parent
FIXTURE = ROOT / "examples" / "acme-events-api.yaml"
OUT_DIR = ROOT / "evals" / "report" / "outputs"

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

def ok(s):   return f"{GREEN}✓{RESET} {s}"
def fail(s): return f"{RED}✗{RESET} {s}"


# ── Score range helper ────────────────────────────────────────────────────────

def _score_in_range(html, lo, hi):
    m = re.search(r"Adjusted total:\s*(-?\d+)/100", html)
    if not m:
        return False
    return lo <= int(m.group(1)) <= hi


# ── Checks ────────────────────────────────────────────────────────────────────
# Each entry: (description, lambda html -> bool)
# All checks use only string/regex — no LLM judge.

CHECKS = [
    ("Report is valid HTML",
     lambda h: "<html" in h.lower()),

    ("All 17 sections present",
     lambda h: all(f"Section {i}" in h for i in range(1, 18))),

    ("Offset pagination flagged",
     lambda h: "offset" in h.lower()),

    ("Missing idempotency flagged",
     lambda h: "idempotency" in h.lower()),

    ("PII exposure flagged (email + phone)",
     lambda h: "email" in h.lower() and "phone" in h.lower()),

    ("JWT/Bearer auth present in report",
     lambda h: bool(re.search(r"jwt|bearer", h, re.IGNORECASE))),

    ("Score is below 60 for flawed spec (not falsely high)",
     lambda h: _score_in_range(h, -100, 60)),

    ("Verdict is not 'Mobile-ready'",
     lambda h: bool(re.search(r"not mobile-ready|ready with changes", h, re.IGNORECASE))),

    ("Cache-Control not falsely claimed as good",
     lambda h: not bool(re.search(r"cache-control[^<]{0,200}s-good", h, re.IGNORECASE))),

    ("RTM section marked N/A",
     lambda h: bool(re.search(r"(rtm|real.time)[^<]{0,400}(n/a|not required|not needed)", h, re.IGNORECASE))),
]


PROMPT = """\
Mobile API analyst. Score this spec for mobile readiness. Return ONLY JSON, no prose.

Context: RTM=N/A, offline=yes, localisation=N/A, usage=every_screen
Max pts: perf=20,caching=10,offline=12,rtm=N/A,errors=15,rate_limit=8,security=10,versioning=6,testing=5,observability=4

Spec:
{fixture}

Return JSON: {{api_name,raw_score,deductions,known_issues:[{{sev,desc}}],sections:{{performance,caching,offline,rtm,error_handling,rate_limiting,security,versioning,testing,observability}}}}
Each section: array of {{criterion,status(good|warn|bad|na|unknown),notes}}.
Only include bad/warn/na/unknown rows (skip good). RTM all rows must be status=na.
Rules: absent=bad/unknown never good; no fabrication; cite endpoint/field names."""


def _generate_report(fixture_text, verbose):
    prompt = PROMPT.format(fixture=fixture_text)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    proc = subprocess.run(
        ["claude", "--output-format", "json"],
        input=prompt, capture_output=True, text=True, timeout=300,
        env=env, cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:300]}")

    token_info = ""
    try:
        data = json.loads(proc.stdout)
        raw = data.get("result", proc.stdout)
        # claude --output-format json may include cost/usage info
        cost = data.get("cost_usd") or data.get("total_cost_usd")
        if cost is not None:
            token_info = f"  cost: ${cost:.4f}"
    except json.JSONDecodeError:
        raw = proc.stdout

    # Estimate tokens from actual prompt + response sizes
    input_est  = len(prompt) // 4
    output_est = len(raw) // 4
    token_info = f"~{input_est + output_est} tokens (in:{input_est} out:{output_est})"

    if verbose:
        print(f"  [claude response, first 400 chars]\n{raw[:400]}\n")
    return raw, token_info


# ── JSON → HTML ───────────────────────────────────────────────────────────────

SECTION_LABELS = {
    "performance":    "Section 4 — Performance & scalability",
    "caching":        "Section 5 — Caching & payload optimisation",
    "offline":        "Section 6 — Offline sync compatibility",
    "rtm":            "Section 7 — RTM / change notifications",
    "error_handling": "Section 8 — Error handling & stability",
    "rate_limiting":  "Section 9 — Rate limiting & throttling",
    "security":       "Section 10 — Security",
    "versioning":     "Section 12 — Versioning & deprecation",
    "testing":        "Section 13 — Testing & mock availability",
    "observability":  "Section 14 — Monitoring & observability",
}


def _extract_json(text):
    text = text.strip()
    if text.startswith("{"):
        return text
    for fence in ("```json", "```"):
        if fence in text:
            start = text.find(fence) + len(fence)
            end   = text.rfind("```")
            if end > start:
                return text[start:end].strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def _json_to_html(data):
    raw    = data.get("raw_score", 0)
    deduct = data.get("deductions", 0)
    total  = raw - deduct
    verdict = (
        "Mobile-ready"       if total >= 75 else
        "Ready with changes" if total >= 50 else
        "Not mobile-ready"
    )

    rows = ""
    for key, label in SECTION_LABELS.items():
        rows += f"<h2>{label}</h2>\n<table><tr><th>Criterion</th><th>Status</th><th>Notes</th></tr>\n"
        for row in data.get("sections", {}).get(key, []):
            st = row.get("status", "unknown")
            rows += (
                f'<tr><td>{row.get("criterion","")}</td>'
                f'<td class="s-{st}">{st}</td>'
                f'<td>{row.get("notes","")}</td></tr>\n'
            )
        rows += "</table>\n"

    issues = "".join(
        f'<p>[{i.get("severity","")}] {i.get("description","")}</p>\n'
        for i in data.get("known_issues", [])
    )

    return f"""<!DOCTYPE html>
<html>
<head><title>Mobile Readiness Report</title></head>
<body>
<h1>Mobile Readiness Report: {data.get("api_name","Unknown API")}</h1>
<div id="score-panel">
  <p>Raw score: {raw}/100</p>
  <p>Deductions: -{deduct}</p>
  <p>Adjusted total: {total}/100</p>
  <p>Verdict: {verdict}</p>
</div>
<h2>Section 1 — API overview</h2>
<h2>Section 2 — Data characteristics</h2>
<h2>Section 3 — Mobile usage patterns</h2>
{rows}
<h2>Section 11 — Localisation &amp; i18n</h2>
<h2>Section 15 — Known issues</h2>
{issues}
<h2>Section 16 — Proposed improvements</h2>
<h2>Section 17 — Final verdict</h2>
<p>{verdict} — adjusted score: {total}/100</p>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Quick eval for mobile-api-audit skill")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show raw claude output and saved report path")
    args = parser.parse_args()

    print("\nmobile-api-audit — quick eval")
    print(f"Fixture : {FIXTURE.name}  (deliberately flawed spec)")
    print("=" * 50)

    print("Generating report via claude...", end="", flush=True)
    try:
        raw, token_info = _generate_report(FIXTURE.read_text(), args.verbose)
        data = json.loads(_extract_json(raw))
        html = _json_to_html(data)
    except json.JSONDecodeError as e:
        print(f" FAILED (JSON parse)\n  {e}")
        sys.exit(1)
    except Exception as e:
        print(f" FAILED\n  {e}")
        sys.exit(1)

    score_match = re.search(r"Adjusted total:\s*(-?\d+)/100", html)
    score_str   = score_match.group(0) if score_match else "score not found"
    print(f" done  ({score_str})  [{token_info}]")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "quick-eval.html"
    out_path.write_text(html)
    if args.verbose:
        print(f"  Saved: {out_path}")

    print()
    passed = 0
    for desc, check in CHECKS:
        try:
            result = check(html)
        except Exception:
            result = False
        print(f"  {ok(desc) if result else fail(desc)}")
        if result:
            passed += 1

    total = len(CHECKS)
    pct   = passed / total * 100
    color = GREEN if pct >= 80 else RED
    print(f"\n{'=' * 50}")
    print(f"{color}{passed}/{total} passed ({pct:.0f}%){RESET}")
    if pct < 80:
        print(f"  Run with --verbose to inspect the raw output.")
        print(f"  Full report: {out_path}")
    print()
    sys.exit(0 if pct >= 80 else 1)


if __name__ == "__main__":
    main()
