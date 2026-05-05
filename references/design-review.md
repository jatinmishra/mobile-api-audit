# Skill Design Review — Mobile API Audit

A point-by-point debate between a senior backend engineer (BE) and a senior mobile engineer (ME) on the design decisions in this skill.

---

## 1. N/A logic is stated contradictorily

**BE:** `SKILL.md` line 203 says "N/A dimensions score their full points." The scoring model says "exclude it from the denominator entirely — do not award its points." The math in the example is correct, but those two sentences say opposite things. Whichever sentence the model latches onto first, it will apply wrong.

**ME:** You're right. That's a genuine bug in the prose, not a design disagreement. The intent is clear — N/A dims are excluded from both numerator and denominator, so they neither help nor hurt you. "Score full points" is a misleading shorthand for "you're not penalised." Fix the wording, don't redesign the mechanic.

**Verdict: BE is right. Prose needs to be fixed.**

---

## 2. Double-penalization — losing points twice for the same gap

**BE:** An API with no cursor pagination scores 4/8 in Dimension 1 *and* takes a Minor −1 deduction in Section 15. Same for missing idempotency — 0/3 in D2 *and* a Major −3 deduction. You're penalising the same gap twice. There's no guard against this.

**ME:** These are measuring different things. The base score reflects *presence* — does the feature exist at all? The deduction reflects *consequence* — how bad is this gap for a mobile client? An offset-only API might score 4/8, but the deduction says: on a slow connection, this causes sessions to drop under load. Reporting both is correct. If you collapsed them into one number you'd lose the ability to distinguish "gap exists" from "gap is dangerous."

**BE:** That's a reasonable argument, but the rules don't state it anywhere. Without explicit documentation that this is intentional, the model will apply it inconsistently. At minimum, the scoring model needs a line explaining why both apply.

**Verdict: ME wins the design argument. BE wins the documentation argument. Add a clarifying note.**

---

## 3. Scoring weights are arbitrary

**BE:** Performance = 20 pts, Observability = 4 pts — why? There's no empirical basis cited. When a verdict flips from 74 to 75 (which changes the entire pass/fail framing), there's no principled answer for why those numbers are right.

**ME:** The weights aren't arbitrary, they reflect mobile failure modes. Performance tanks first on mobile — flaky network, CPU throttling, battery constraints. A slow API on mobile is a crash in the user's perception. Observability matters less to a mobile client directly; it matters to the team debugging issues post-launch. The ordering is defensible from experience if not from a controlled study.

**BE:** "Defensible from experience" isn't the same as documented. If someone challenges a borderline verdict, "trust the weights" is a weak answer.

**ME:** Fair. A brief rationale paragraph in the scoring model explaining the weighting philosophy would close this.

**Verdict: Split. Weights are defensible but need a rationale paragraph.**

---

## 4. Testing & mocks and Observability don't belong in a mobile readiness score

**BE:** Whether the API team runs contract tests or has a latency dashboard is entirely about producer practices. A mobile client can't observe either. You're grading team maturity, not API fitness.

**ME:** This is the take I disagree with most. Mobile releases take 1–2 weeks through App Store review. If there's no sandbox, my team ships against a moving target with no way to validate behavior before code is locked. That's not a backend team problem — it's *my* problem. One backend deploy can break my release and I can't hotfix it in 10 minutes like they can.

Same with request IDs. When a user files a crash report from the field and I need to correlate it with server logs, `X-Request-Id` is the only thread I have. Without it I'm flying blind in production.

**BE:** The sandbox argument is compelling. The contract tests argument is still about producer workflow, not wire behavior.

**ME:** Contract tests protect me from undocumented breaking changes. The mobile team has zero control over backend deploy cadence. If I can see that contract tests exist in CI, I know there's a safety net between me and a silent breaking change. That has direct mobile impact.

**Verdict: ME wins. Both dimensions are mobile-relevant. The framing in the skill could be clearer — these sections should be labelled "mobile team impact" not "API quality."**

---

## 5. Sequential AskUserQuestion calls are indefensible UX

**BE:** Five questions asked one at a time before any analysis runs. Five round-trips. All questions are independent of each other. There is zero reason they can't be batched.

**ME:** I actually agree with you here. The sequential flow was probably designed so the model doesn't overwhelm the user with a wall of questions, but in practice it just drags out the pre-audit ritual. The right fix is to batch all questions in one call and wait for answers collectively. The 5-question cap is right; the sequential execution is wrong.

**Verdict: BE is right. Questions should be batched.**

---

## 6. The offline N/A inference rule is too conservative

**BE:** The rule says only skip the offline question if the spec is "explicitly auth-only." The default is "Needed." Most APIs aren't auth-only, and most APIs aren't designed for offline. The skill will overclaim offline as a gap for the vast majority of inputs.

**ME:** That conservative default is intentional and I'd fight to keep it. Backend engineers routinely say "we don't need offline" and then 6 months after launch the first field worker is on a plane, underground, or in a building with no signal — and suddenly offline is a P0 regression. I have seen this exact pattern multiple times. The skill's job is to surface the question, not assume the answer. Requiring the team to explicitly say "offline isn't needed" is a forcing function that catches lazy assumptions before they become production incidents.

**BE:** That's a valid product argument but it creates false positives. An API for a payment checkout flow will be rated harshly for not supporting offline, which is genuinely irrelevant.

**ME:** Which is why the question exists — the user answers "No, always online" and the dimension becomes N/A. The forcing function costs one answer. The penalty for not asking is a field deployment failure.

**Verdict: ME wins the philosophy argument. BE's concern is real but is handled by the N/A flow itself.**

---

## 7. The spec-only exception contradicts the extraction guide

**BE:** The scoring model says Cache-Control and ETag should be `unknown` when only a spec is provided. But the extraction guide explicitly instructs the model to look for those headers in OpenAPI response definitions. If an API spec documents `Cache-Control` in its response headers, why score it `unknown`?

**ME:** The intent behind the spec-only exception is correct — a spec documents *intent*, not runtime behaviour. An OpenAPI response can define `Cache-Control` and the server can still send `no-store` on every response. You can't confirm caching behaviour without observing it.

**BE:** That's true for runtime, but the skill is auditing what the API *contract* specifies. If `Cache-Control: max-age=3600` is in the spec, that's a commitment. Score it based on the commitment.

**ME:** Agreed. The exception should be narrowed: score `unknown` only when the header is *absent from both spec and HAR*, not when it's present in the spec but HAR isn't provided.

**Verdict: BE identifies a real inconsistency. The fix is to narrow the spec-only exception, not remove it.**

---

## 8. "Idempotent by design" is unverifiable from a spec

**BE:** The scoring model awards 2 pts for "idempotent by design." How do you determine this from a spec? PUT is idempotent per RFC 7231, so every PUT endpoint gets 2 pts automatically? The rule doesn't say that.

**ME:** It should say that. PUT idempotency is a well-defined HTTP contract. If the endpoint uses PUT, award 2 pts. If it uses POST with no Idempotency-Key, award 0. The scoring rule is just under-specified, not wrong.

**Verdict: BE identifies an under-specified rule. The fix is one line clarifying that PUT = idempotent by design, POST without Idempotency-Key = not.**

---

## 9. HAR provenance check has blind spots

**BE:** The guide checks for `localhost`, `staging`, `dev` — but doesn't handle internal corporate hostnames (`api.corp.internal`), non-standard ports, or VPN-captured traffic to a hostname that looks production-like but isn't. This produces confidently wrong latency scores.

**ME:** You're right on internal hostnames and non-standard ports. The non-standard port check is partially there but the corporate hostname pattern is a real gap. In enterprise mobile development, the HAR is almost always captured from a dev environment routing through a VPN to an internal endpoint. The fix is to flag any non-standard port and any TLD that isn't a recognised public TLD.

**Verdict: BE is right. The provenance check needs to cover non-standard ports and internal TLDs.**

---

## 10. 17 sections is too many — the report is theater

**BE:** Sections 2, 3, 11, 13, 14 default to `unknown` or "Requires manual input." They exist to look thorough, not to drive action. Nobody acts on "Schema stability: unknown." Cut 60% of the report and lose almost no decision-making value.

**ME:** You're optimising for your reading experience, not for how these reports actually get used. A mobile audit report isn't just consumed by the engineer who ran it. It gets shared with: the backend team as a formal handoff artifact, the product manager deciding whether to delay launch, the security review board, and sometimes a VP who wants a single document to refer to. A 3-section punch list serves the engineer. 17 sections with structured evidence serves the organisation.

The rows that default to `unknown` aren't filler — they signal "we don't know this yet." That's information. It tells the backend team what they haven't documented. It tells the product manager there are open questions. Leaving them out implies the questions were answered.

**BE:** That's fair for an org-facing artifact. But the skill doesn't differentiate between "quick check for a developer" and "formal handoff document." One mode fits all, and that's a design smell.

**ME:** Agreed. A `--mode quick` flag that outputs just S15, S16, and S17 would solve this without cutting the full report.

**Verdict: ME wins on the use case argument. BE's point about modes is valid — the skill would benefit from a compact output option.**

---

## 11. Section 3 inferences are unreliable

**BE:** "Called on app launch," "Expected concurrent callers" — inferred from endpoint names. `POST /sync` or `GET /config` don't tell you when they're called. These inferences will carry into latency scoring targets with false confidence.

**ME:** Partially agree. The inferences are weak but the alternative is leaving the rows blank, which is worse — it makes the report look incomplete and gives the reader nothing to react to. The fix is to label inferences explicitly as inferences (which the skill does elsewhere) and let the user correct them in the clarifying questions step. What you shouldn't do is treat the inference as confirmed and silently apply the tighter latency target without stating why.

**Verdict: Split. The inferences should stay but must be visibly flagged as inferences in the report output.**

---

## 12. The skill trigger is too broad

**BE:** "Always use this skill when the user provides API specs or traffic data and wants any kind of quality or readiness assessment." A server-to-server integration, a batch export API, an internal microservice — none of these are mobile consumers. They'll all get a 17-section mobile readiness audit they didn't ask for.

**ME:** Agree completely. The trigger needs a qualifier — at minimum, if the user provides no mobile context and no mobile endpoints are evident, the skill should ask "Is this API consumed by a mobile client?" before proceeding. A quick context check would prevent 90% of false triggers.

**Verdict: Both agree. The trigger needs a mobile consumer confirmation step.**

---

## 13. Missing mobile-critical signals

**BE:** Retry policy and backoff guidance, response jitter (p95/p50 spread), push notification token management, certificate pinning guidance — none of these are scored.

**ME:** Retry policy and jitter are real gaps. Mobile clients on flaky connections will hammer an API without backoff guidance. The p95/p50 spread matters more to perceived mobile performance than raw p50 — a consistent 300ms feels better than a 50ms median with a 2s p95. These should be in Dimension 1.

Push notification token management and certificate pinning are out of scope — those are mobile client concerns, not API design concerns. The skill is auditing the API, not the app.

**Verdict: BE is right on retry policy and jitter. Wrong on pinning and push token management — those live in the app, not the API contract.**

---

## Summary Scorecard

| Point | Winner | Action |
|-------|--------|--------|
| N/A prose contradiction | BE | Fix the wording in SKILL.md |
| Double-penalization | ME (design), BE (docs) | Add a clarifying note to scoring-model.md |
| Arbitrary weights | Split | Add a rationale paragraph |
| Testing & mocks not mobile concerns | ME | Reframe section labels |
| Sequential questions | BE | Batch all questions in one call |
| Offline default too conservative | ME | No change |
| Spec-only exception inconsistency | BE | Narrow the exception |
| Idempotent by design unverifiable | BE | Add one-line clarification for PUT |
| HAR provenance blind spots | BE | Add internal TLD and non-standard port checks |
| 17 sections is overkill | Split | Add a compact `--mode quick` output option |
| Section 3 inferences unreliable | Split | Flag inferences visibly in report output |
| Trigger too broad | Both | Add mobile consumer confirmation step |
| Missing retry/jitter signals | BE (partial) | Add retry policy and jitter to Dimension 1 |
