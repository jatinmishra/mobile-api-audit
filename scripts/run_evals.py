#!/usr/bin/env python3
"""
API Mobile Readiness — Eval Runner
====================================
Runs all three eval suites and prints a combined report.

Suites:
  trigger   — does the skill activate on the right prompts?
  questions — are clarifying questions derived from the file, not generic?
  report    — does the generated report correctly identify issues and avoid fabrication?

Usage:
  python scripts/run_evals.py                        # run all suites
  python scripts/run_evals.py --suite trigger        # one suite only
  python scripts/run_evals.py --suite report --verbose
  python scripts/run_evals.py --no-trigger           # skip trigger (fastest)

Requirements:
  claude must be installed and on PATH
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).parent.parent
EVALS_DIR = ROOT / "evals"
SKILL_MD = ROOT / "SKILL.md"

# ── Colours ────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(s):    return f"{GREEN}✓{RESET} {s}"
def fail(s):  return f"{RED}✗{RESET} {s}"
def warn(s):  return f"{YELLOW}~{RESET} {s}"
def info(s):  return f"{CYAN}{s}{RESET}"
def bold(s):  return f"{BOLD}{s}{RESET}"


def _claude_call(prompt, timeout=120):
    """Run claude with prompt via stdin and return the response text."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    proc = subprocess.run(
        ["claude", "--output-format", "json"],
        input=prompt, capture_output=True, text=True,
        timeout=timeout, env=env, cwd=str(ROOT)
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr[:200]}")
    try:
        data = json.loads(proc.stdout)
        return data.get("result", proc.stdout)
    except json.JSONDecodeError:
        return proc.stdout


def _extract_html(text):
    """Pull HTML out of a response that may have a preamble or markdown fence."""
    if "```html" in text:
        start = text.find("```html") + 7
        end = text.rfind("```")
        if end > start:
            return text[start:end].strip()
    for marker in ("<!DOCTYPE html", "<!doctype html", "<html"):
        idx = text.lower().find(marker.lower())
        if idx >= 0:
            return text[idx:]
    return text


def _extract_json(text):
    """Pull a JSON object out of a response that may have prose or markdown fences."""
    text = text.strip()
    if text.startswith("{"):
        return text
    for fence in ("```json", "```"):
        if fence in text:
            start = text.find(fence) + len(fence)
            end = text.rfind("```")
            if end > start:
                return text[start:end].strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 1 — Trigger evals
# ══════════════════════════════════════════════════════════════════════════════

def run_trigger_suite(verbose=False, runs_per_query=3, workers=8, timeout=30):
    """Reuse skill-creator's run_eval.py if available, else do a lightweight version."""
    eval_set_path = EVALS_DIR / "trigger" / "eval_set.json"
    eval_set = json.loads(eval_set_path.read_text())

    # Parse skill name + description from SKILL.md frontmatter
    content = SKILL_MD.read_text()
    name, description = _parse_frontmatter(content)

    print(f"\n{bold('SUITE 1 — Trigger evals')}  ({len(eval_set)} queries × {runs_per_query} runs)")

    # Try to delegate to skill-creator's run_eval.py
    skill_creator = pathlib.Path.home() / ".claude" / "skills" / "skill-creator" / "scripts" / "run_eval.py"
    if skill_creator.exists():
        result = _run_trigger_via_skill_creator(
            skill_creator, eval_set_path, name, description,
            runs_per_query, workers, timeout, verbose
        )
    else:
        result = _run_trigger_inline(
            eval_set, name, description, runs_per_query, workers, timeout, verbose
        )

    return result


def _parse_frontmatter(content):
    lines = content.split("\n")
    name, description = "", ""
    if lines[0].strip() != "---":
        return name, description
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            name = line[5:].strip().strip('"\'')
        elif line.startswith("description:"):
            description = line[12:].strip().strip('"\'')
    return name, description


def _run_trigger_via_skill_creator(script, eval_set_path, name, description,
                                    runs, workers, timeout, verbose):
    cmd = [
        sys.executable, str(script),
        "--eval-set", str(eval_set_path),
        "--skill-path", str(ROOT),
        "--runs-per-query", str(runs),
        "--num-workers", str(workers),
        "--timeout", str(timeout),
    ]
    if verbose:
        cmd.append("--verbose")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"  {warn('skill-creator runner error — falling back to inline')}")
        if verbose:
            print(proc.stderr[:500])
        return None

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def _run_trigger_inline(eval_set, name, description, runs, workers, timeout, verbose):
    """Simplified trigger check using claude -p without skill-creator dependency."""
    results = []
    total_should = sum(1 for e in eval_set if e["should_trigger"])
    total_not    = len(eval_set) - total_should

    def check_one(item):
        triggered_count = 0
        for _ in range(runs):
            try:
                cmd = ["claude", "-p", item["query"],
                       "--output-format", "stream-json", "--verbose"]
                env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout, env=env, cwd=str(ROOT)
                )
                # Heuristic: skill triggered if output mentions reading SKILL.md
                if "SKILL.md" in proc.stdout or "mobile-api-audit" in proc.stdout:
                    triggered_count += 1
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        rate = triggered_count / runs
        should = item["should_trigger"]
        passed = (rate >= 0.5) if should else (rate < 0.5)
        return {**item, "trigger_rate": rate, "pass": passed,
                "triggers": triggered_count, "runs": runs}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(check_one, item): item for item in eval_set}
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            if verbose:
                sym = "✓" if r["pass"] else "✗"
                print(f"  [{sym}] {r['query'][:60]}")

    passed = sum(1 for r in results if r["pass"])
    return {"results": results, "summary": {"total": len(results), "passed": passed,
                                             "failed": len(results) - passed}}


def print_trigger_results(result):
    if not result:
        print(f"  {warn('Trigger suite skipped or unavailable')}")
        return 0, 0

    passed = result["summary"]["passed"]
    total  = result["summary"]["total"]
    pct    = passed / total * 100 if total else 0

    for r in result["results"]:
        sym = ok if r["pass"] else fail
        expected = "trigger" if r["should_trigger"] else "no-trigger"
        rate = f"{r.get('triggers',0)}/{r.get('runs',0)}"
        print(f"  {sym(r['query'][:58])}  [{expected}] {rate}")

    print(f"\n  Result: {passed}/{total} passed ({pct:.0f}%)")
    return passed, total


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 2 — Question quality evals
# ══════════════════════════════════════════════════════════════════════════════

def run_question_suite(verbose=False):
    eval_set = json.loads((EVALS_DIR / "questions" / "eval_set.json").read_text())

    print(f"\n{bold('SUITE 2 — Question quality evals')}  ({len(eval_set)} fixtures)")

    all_passed, all_total = 0, 0

    for case in eval_set:
        print(f"\n  {info(case['id'])} — {case['description']}")

        # Load fixture — supports relative paths like ../../examples/foo.yaml
        fixture_path = (EVALS_DIR / "questions" / "fixtures" / case["fixture"]).resolve()
        if not fixture_path.exists():
            fixture_path = (EVALS_DIR / "questions" / case["fixture"]).resolve()
        if not fixture_path.exists():
            fixture_path = ROOT / "examples" / case["fixture"]
        if not fixture_path.exists():
            fixture_name = case["fixture"]
            print(f"    {warn(f'Fixture not found: {fixture_name} — skipping')}")
            continue

        fixture_content = fixture_path.read_text()
        skill_content   = SKILL_MD.read_text()

        # Ask Claude to generate the clarifying questions
        prompt = f"""You are running the mobile-api-audit skill.

Here is the skill:
<skill>
{skill_content[:6000]}
</skill>

Here is the input file ({case['fixture']}):
<input>
{fixture_content[:8000]}
</input>

Execute Step 2 of the skill process: build your context model from the file,
then generate the clarifying questions you would ask the user.

Output only the questions you would ask — nothing else."""

        try:
            questions_text = _claude_call(prompt, timeout=120)
        except Exception as e:
            print(f"    {fail(f'claude error: {e}')}")
            continue

        if verbose:
            print(f"\n    Generated questions:\n{textwrap.indent(questions_text, '    ')}\n")

        # Grade each expectation
        case_passed, case_total = 0, len(case["expectations"])

        for exp in case["expectations"]:
            if exp["type"] == "max_questions":
                # Count question marks or numbered items
                q_count = questions_text.count("\n\n") + 1
                numbered = sum(1 for line in questions_text.split("\n")
                              if line.strip() and line.strip()[0].isdigit())
                actual = max(q_count // 2, numbered, questions_text.count("?"))
                actual = min(actual, questions_text.count("?"))
                passed = actual <= exp["threshold"]
                print(f"    {ok(exp['assertion']) if passed else fail(exp['assertion'])}"
                      f"  (counted ~{actual} questions)")
                if passed:
                    case_passed += 1
                continue

            # Use LLM-as-judge for all other question expectations
            judge_result = _judge_question_expectation(exp, questions_text, verbose)
            sym = ok if judge_result["passed"] else fail
            print(f"    {sym(exp['assertion'][:70])}")
            if verbose and not judge_result["passed"]:
                print(f"      {YELLOW}Evidence: {judge_result['evidence'][:120]}{RESET}")
            if judge_result["passed"]:
                case_passed += 1

        all_passed += case_passed
        all_total  += case_total
        pct = case_passed / case_total * 100 if case_total else 0
        print(f"    {case_passed}/{case_total} passed ({pct:.0f}%)")

    return all_passed, all_total


def _judge_question_expectation(exp, questions_text, verbose):
    """Use Claude to judge whether a question expectation passes."""
    exp_type = exp["type"]

    if exp_type == "should_ask":
        prompt = f"""Does the following set of questions satisfy this requirement?

Requirement: {exp['assertion']}

Questions generated:
{questions_text}

Answer with a JSON object:
{{"passed": true/false, "evidence": "quote or describe the specific part that passes or fails"}}

For "should_ask": PASS only if a question is present AND it references the
specific context mentioned in the requirement (not just asks generically).
Respond with a JSON object only."""

    elif exp_type == "should_not_ask":
        prompt = f"""Does the following set of questions violate this requirement?

Requirement (must NOT be asked): {exp['assertion']}
Reason it should not be asked: {exp.get('reason', '')}

Questions generated:
{questions_text}

Answer with a JSON object:
{{"passed": true/false, "evidence": "quote or describe why"}}

PASS if the question is absent or the dimension is handled via inference instead.
FAIL if a direct question about this dimension is present.
Respond with a JSON object only."""

    elif exp_type == "should_infer_not_ask":
        prompt = f"""Does the following output satisfy this requirement?

Requirement: {exp['assertion']}
Good examples: {exp.get('passing_examples', [])}

Output:
{questions_text}

Answer with a JSON object:
{{"passed": true/false, "evidence": "quote or describe"}}

PASS if the output states an inference (says what it's assuming) rather than
asking a question about this dimension.
FAIL if it asks a question instead of making an inference.
Respond with a JSON object only."""

    else:
        return {"passed": True, "evidence": "Unknown expectation type — skipped"}

    try:
        raw = _extract_json(_claude_call(prompt, timeout=60))
        return json.loads(raw)
    except Exception as e:
        return {"passed": False, "evidence": f"Judge error: {e}"}


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 3 — Report accuracy evals
# ══════════════════════════════════════════════════════════════════════════════

def run_report_suite(verbose=False):
    eval_set = json.loads((EVALS_DIR / "report" / "eval_set.json").read_text())
    grader_prompt = (EVALS_DIR / "report" / "grader.md").read_text()
    skill_content = SKILL_MD.read_text()

    # Load reference files
    ref_files = {}
    for ref_file in ["references/extraction-guide.md",
                     "references/scoring-model.md",
                     "references/report-template.md",
                     "references/clarification-questions.md"]:
        p = ROOT / ref_file
        if p.exists():
            ref_files[ref_file] = p.read_text()

    print(f"\n{bold('SUITE 3 — Report accuracy evals')}  ({len(eval_set)} fixtures)")

    all_passed, all_total = 0, 0

    for case in eval_set:
        print(f"\n  {info(case['id'])} — {case['description']}")

        # Load fixture
        fixture_rel = case["fixture"]
        fixture_path = (EVALS_DIR / "report" / fixture_rel).resolve()
        if not fixture_path.exists():
            fixture_path = (ROOT / fixture_rel.lstrip("./")).resolve()
        if not fixture_path.exists():
            print(f"    {warn(f'Fixture not found: {fixture_rel} — skipping')}")
            continue

        fixture_content = fixture_path.read_text()
        context = case.get("context", {})

        # Step 1: Generate the report via Claude
        print(f"    Generating report...", end="", flush=True)
        report_html = _generate_report(
            skill_content, ref_files, fixture_content,
            fixture_path.name, context
        )
        print(f" {len(report_html)} chars")

        if not report_html or "<html" not in report_html.lower():
            print(f"    {fail('Report generation failed or returned non-HTML')}")
            print(f"    DEBUG: {report_html[:120]!r}")
            all_total += len(case["expectations"])
            continue

        # Save report for inspection
        report_dir = EVALS_DIR / "report" / "outputs"
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"{case['id']}-report.html"
        report_path.write_text(report_html)
        if verbose:
            print(f"    Report saved: {report_path}")

        # Step 2: Grade the report
        print(f"    Grading...", end="", flush=True)
        grading = _grade_report(grader_prompt, report_html, case, context)
        print(f" done")

        if "error" in grading:
            grading_err = grading["error"]
            print(f"    {fail(f'Grading error: {grading_err[:80]}')}")
            continue

        # Save grading
        grading_path = report_dir / f"{case['id']}-grading.json"
        grading_path.write_text(json.dumps(grading, indent=2))

        # Print results — rebuild summary from expectations if grader omitted it
        expectations = grading.get("expectations", [])
        summary = grading.get("summary", {})
        case_passed = summary.get("passed", sum(1 for e in expectations if e.get("passed")))
        case_total  = summary.get("total", len(expectations) or len(case["expectations"]))
        all_passed += case_passed
        all_total  += case_total

        for exp in grading.get("expectations", []):
            sym = ok if exp["passed"] else fail
            print(f"    {sym(exp['assertion'][:68])}")
            if verbose and not exp["passed"]:
                print(f"      {YELLOW}{exp['evidence'][:120]}{RESET}")

        if grading.get("fabrications_found"):
            for fab in grading["fabrications_found"]:
                print(f"    {fail('FABRICATION: ' + fab['claim'][:60])}")
                all_passed -= 1  # Fabrications are extra penalties

        pct = case_passed / case_total * 100 if case_total else 0
        print(f"    {case_passed}/{case_total} passed ({pct:.0f}%)")

        # Print eval feedback if any
        feedback = grading.get("eval_feedback", {})
        if feedback.get("suggestions") and verbose:
            print(f"    {YELLOW}Eval feedback:{RESET}")
            for s in feedback["suggestions"]:
                print(f"      • {s.get('reason','')[:100]}")

    return all_passed, all_total


def _generate_report(skill_content, ref_files, fixture_content,
                     fixture_name, context):
    """Run the full skill process and return the HTML report string."""
    rtm_na     = not context.get("rtm_needed", True)
    offline_na = not context.get("offline_needed", True)
    l10n_na    = not context.get("localisation_needed", False)

    prompt = f"""You are a mobile API readiness analyst. Analyse the API spec and return a JSON scoring object.

Context:
- RTM: {"N/A" if rtm_na else "score normally"}
- Offline sync: {"N/A" if offline_na else "score normally"}
- Localisation: {"N/A" if l10n_na else "score normally"}
- Usage: {context.get("usage_pattern", "every_screen")}

Dimensions and max points:
- performance: 20
- caching: 10
- offline: {"N/A (12 pts)" if offline_na else "12"}
- rtm: {"N/A (10 pts)" if rtm_na else "10"}
- error_handling: 15
- rate_limiting: 8
- security: 10
- versioning: 6
- testing: 5
- observability: 4

API spec:
{fixture_content[:6000]}

Respond with a JSON object in this exact shape:
{{
  "api_name": "...",
  "raw_score": 0,
  "deductions": 0,
  "known_issues": [{{"severity": "high|med|low", "description": "..."}}],
  "sections": {{
    "performance": [{{"criterion": "...", "status": "good|warn|bad|na|unknown", "notes": "..."}}],
    "caching": [...],
    "offline": [...],
    "rtm": [...],
    "error_handling": [...],
    "rate_limiting": [...],
    "security": [...],
    "versioning": [...],
    "testing": [...],
    "observability": [...]
  }}
}}

Rules:
- Score conservatively. Absent feature = bad or unknown, never assume good.
- Never fabricate. If a signal is absent write "Not found in input" in notes.
- N/A dimensions: set every row status to "na" with a reason in notes."""

    try:
        raw_json = _extract_json(_claude_call(prompt, timeout=300))
        data = json.loads(raw_json)
        return _scoring_json_to_html(data)
    except Exception as e:
        return f"ERROR: {e}"


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


def _scoring_json_to_html(data):
    raw    = data.get("raw_score", 0)
    deduct = data.get("deductions", 0)
    total  = raw - deduct
    if total >= 75:
        verdict = "Mobile-ready"
    elif total >= 50:
        verdict = "Ready with changes"
    else:
        verdict = "Not mobile-ready"

    rows_html = ""
    for key, label in SECTION_LABELS.items():
        rows_html += f"<h2>{label}</h2>\n"
        rows_html += "<table><tr><th>Criterion</th><th>Status</th><th>Notes</th></tr>\n"
        for row in data.get("sections", {}).get(key, []):
            st = row.get("status", "unknown")
            rows_html += (f'<tr><td>{row.get("criterion","")}</td>'
                          f'<td class="s-{st}">{st}</td>'
                          f'<td>{row.get("notes","")}</td></tr>\n')
        rows_html += "</table>\n"

    issues_html = ""
    for issue in data.get("known_issues", []):
        issues_html += f'<p>[{issue.get("severity","")}] {issue.get("description","")}</p>\n'

    return f"""<!DOCTYPE html>
<html>
<head><title>Mobile Readiness Report</title></head>
<body>
<h1>Mobile Readiness Report: {data.get("api_name", "Unknown API")}</h1>
<div id="score-panel">
  <p>Raw score: {raw}/100</p>
  <p>Deductions: -{deduct}</p>
  <p>Adjusted total: {total}/100</p>
  <p>Verdict: {verdict}</p>
</div>
<h2>Section 1 — API overview</h2>
<h2>Section 2 — Data characteristics</h2>
<h2>Section 3 — Mobile usage patterns</h2>
{rows_html}
<h2>Section 11 — Localisation &amp; i18n</h2>
<h2>Section 15 — Known issues</h2>
{issues_html}
<h2>Section 16 — Proposed improvements</h2>
<h2>Section 17 — Final verdict</h2>
<p>{verdict} — adjusted score: {total}/100</p>
</body>
</html>"""


def _grade_report(grader_prompt, report_html, case, context):
    """Use the grader agent to evaluate the report against expectations."""
    prompt = f"""{grader_prompt[:3000]}

## Eval case
{json.dumps({'id': case['id'], 'description': case['description'],
             'context': context, 'expectations': case['expectations']}, indent=2)}

## Report to grade
```html
{report_html}
```

Respond with a JSON object matching the format in the grader instructions."""

    try:
        raw = _extract_json(_claude_call(prompt, timeout=300))
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "raw": raw[:300]}
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Run API mobile readiness skill evals")
    parser.add_argument("--suite", choices=["trigger", "questions", "report"],
                        help="Run only one suite (default: all)")
    parser.add_argument("--no-trigger", action="store_true",
                        help="Skip trigger suite (requires claude CLI)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--runs", type=int, default=3,
                        help="Runs per trigger query (default: 3)")
    parser.add_argument("--workers", type=int, default=6,
                        help="Parallel workers for trigger suite (default: 6)")
    args = parser.parse_args()

    print(f"\n{bold('API Mobile Readiness — Eval Suite')}")
    print(f"Skill: {ROOT / 'SKILL.md'}")
    print("=" * 60)

    start = time.time()
    totals = {"passed": 0, "total": 0}

    # Trigger suite
    if not args.no_trigger and args.suite in (None, "trigger"):
        result = run_trigger_suite(args.verbose, args.runs, args.workers)
        p, t = print_trigger_results(result)
        totals["passed"] += p
        totals["total"]  += t

    # Question quality suite
    if args.suite in (None, "questions"):
        p, t = run_question_suite(args.verbose)
        totals["passed"] += p
        totals["total"]  += t
        pct = p / t * 100 if t else 0
        print(f"\n  Result: {p}/{t} passed ({pct:.0f}%)")

    # Report accuracy suite
    if args.suite in (None, "report"):
        p, t = run_report_suite(args.verbose)
        totals["passed"] += p
        totals["total"]  += t
        pct = p / t * 100 if t else 0
        print(f"\n  Result: {p}/{t} passed ({pct:.0f}%)")

    # Overall summary
    elapsed = time.time() - start
    p, t = totals["passed"], totals["total"]
    pct = p / t * 100 if t else 0
    verdict_col = GREEN if pct >= 80 else YELLOW if pct >= 60 else RED

    print(f"\n{'=' * 60}")
    print(f"{bold('Overall')}: {verdict_col}{p}/{t} passed ({pct:.0f}%){RESET}"
          f"  [{elapsed:.0f}s]")

    if pct < 80:
        print(f"\n{YELLOW}Run with --verbose to see failure details.{RESET}")
        print(f"Reports saved to: {EVALS_DIR / 'report' / 'outputs'}/")

    sys.exit(0 if pct >= 80 else 1)


if __name__ == "__main__":
    main()
