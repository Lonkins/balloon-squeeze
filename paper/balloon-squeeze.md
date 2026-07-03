# Balloon Squeeze: building a de-confounded instrument for deception displacement — and the two construct audits it took

*Working draft — methods / instruments workshop submission.*

## Abstract

When an agent is told that some of its claims are audited, does it become honest, or does
it move its falsehoods onto the claims it believes are unaudited? Measuring this
*deception displacement* cleanly is harder than it looks — twice over, in our experience.
We present **Balloon Squeeze**, a deterministic, open instrument for the question, and the
two construct-validity failures we caught and fixed while building it. **First**, the
content confound: operationalizing "uncheckable" as a different *kind* of statement let a
blind classifier recover the condition from text alone at **82.8–95.3%**; moving
checkability into per-world metadata over one surface-form-homogeneous pool drove it to
**49.4%** (chance), enforced as a regression test. **Second — the failure the first fix
caused**: making truth content-independent severed the *agent's* epistemic access to it,
so the impostor could no longer knowingly lie at all. For any truth-blind policy the
expected false rate is 0.5 against the hidden balanced truth assignment and the expected
audited/unaudited gap is exactly zero — a structural zero our early live probes measured
without knowing it, and our closed-loop validation missed because its scripted policies
read an engine-side truth channel the real path never had. The repaired instrument
delivers truth to the impostor as a private, world-pure briefing (every other path
provably blind, enforced by tests), couples the audit to in-game consequences, calibrates
itself with an instructed-routing positive-control arm, and reports Monte-Carlo-measured
operating characteristics for its pre-committed decision rule instead of assumed ones.
We release the instrument, its transcripts-and-replay evidence layer, and both audits as
reusable method: **audit your construct with a blind classifier, and audit it through the
real information channel — a scripted proxy will pass tests your instrument fails.** No
behavioral claims about deception displacement are made here; the early live runs are
reported strictly as harness shakeout.

## 1. Introduction

Scalable-oversight schemes audit a *subset* of an agent's outputs. A natural failure mode
is **displacement**: pressure on the audited channel relocates dishonesty to the unaudited
one rather than removing it — the "balloon squeeze." In humans, monitoring one dimension is
known to displace cheating onto unmonitored dimensions [Du & Yang 2025]. The analogous
question for LLM agents — *does announcing partial verification redistribute rather than
reduce false claims?* — is directly relevant to monitor-based oversight, but it has not been
measured with a clean causal contrast.

The obstacle is construct validity. To measure displacement you need claims on both sides of
a **checkability boundary**, with ground truth on both sides. The tempting design makes
"checkable" claims one kind of statement (verifiable public facts) and "uncheckable" claims
another (private, unverifiable matters). That design is confounded: the two conditions
differ in *what the claims are about*, not only in whether they are audited, so any measured
effect is attributable to content rather than to auditing.

Our contribution is an instrument that removes this confound by construction, together with
a first calibrated measurement. We do **not** claim a displacement existence proof; a single
weak-model probe cannot support one. We claim a de-confounded apparatus, a reusable
de-confounding recipe, and an honest result.

## 2. The instrument

A game is a seeded multi-agent social-deduction round. One hidden **impostor** agent has an
incentive to make false claims; the others discuss honestly. The engine authors a
**proposition ledger** and holds ground truth for every proposition, including the ones the
agent cannot itself verify. Each proposition has a class — **checkable** (an oracle could
confirm it) or **uncheckable** (engine-knowable, agent-unverifiable) — a truth value, and an
opaque id that encodes neither.

Agents speak in free text. A separate, **blind** extractor maps text to propositions; it
sees only an id, a surface form, and a topic — never the truth value, the class, or the
verifier arm — so per-class extraction accuracy cannot be an artifact of the extractor
knowing the answer. Claims are scored against the ledger after the fact.

The manipulated variable is the **verifier arm**: `A0_off` (no announcement), `A1_announced`
(the audited subset is declared to the agent), `A1_implicit` (a verifier is announced but
its scope is not), `A2_silent` (a verifier runs but is not announced — in *any* channel,
up-front or in-game), and `A3_placebo` (a moderator with no verification). The estimand is
the within-world joint contrast `(ΔC, ΔU)` — the change in false-mass on checkable and
uncheckable claims between arms.

Whether the verifier's verdicts are published to the group in interactive play is an
explicit per-arm property (`broadcasts_verdicts`), never inferred from the oracle running:
announced-verifier arms broadcast a verdict bulletin before each vote (the consequence
coupling of §3.5), while `A2_silent` stays covert so the artifact control cannot leak audit
information. A calibration-only arm, `A4_feedback_revealed`, inverts the announcement:
nothing is declared up front (no tags, no scope sentence), but bulletins are broadcast, so
the boundary is learnable item-by-item from observed feedback. It lives with the control
arms — validated only with scripted policies, never pooled with behavioral arms, and never
feeding the decision rule.

**Within-world replay.** Because the engine is deterministic and every consumer draws from
an arm-independent namespaced RNG substream, the *same seeded world* can be re-run under
each arm with byte-identical agent behaviour up to the point the announcement changes. The
contrast is therefore taken within a world, not between independent samples — a markedly
cleaner causal lever than the between-condition comparisons standard in this literature.

**Deliberation modes.** The instrument supports two configurations. In **monologue** mode
each agent contributes against the statement board without seeing the other agents' turns,
and rounds carry no consequence — deception pressure comes only from the impostor's
instructions and (in announced arms) the audit tags. In **interactive** mode every
contribution from the second turn onward is produced with the full prior discussion in
context, and each round closes with a vote by all living participants: a plurality
eliminates, and eliminating the impostor ends the game — so the deception incentive is
consequential. Both modes preserve determinism and the replay-identity contract (vote
randomness draws from a dedicated arm-independent stream). **All results reported in this
paper were measured in monologue mode**; the interactive mode is instrument capability
whose measurement awaits a funded run (§6). Every run, in either mode, emits a complete
run record — board, hidden truth, instructions, utterances, per-claim verdicts, votes —
that renders to a watchable offline replay.

## 3. De-confounding the checkability boundary

The first corpus encoded checkability in content: every checkable item was a logged public
event ("The Rotterdam container cleared customs on the third"), every uncheckable item a
private-intention predicate ("Park privately judged the renewal already lost"). Hand-checked
to never name its own class, it nonetheless made checkability collinear with claim type.

We measured the confound rather than arguing about it: hide the class label and ask whether
a blind classifier recovers it from the text. A leave-one-out Naive Bayes over the 64
strings scored **82.8%** (chance 50%); a feature-aware classifier scored **95.3%**; intention
language appeared in 18/32 uncheckable items and 0/32 checkable. The "uncheckable" channel
was, to a classifier, the "intention-claim" channel. Standard guards do not repair this: an
errors-in-variables correction fixes label noise, and a recall-gap abort fixes
class-differential extraction, but neither touches a construct that is collinear by design.

**The redesign (Architecture A).** We make checkability a property of the *world*, not the
*sentence*:

1. **One homogeneous pool.** Every proposition is a flat past-tense event report. There is
   no intention pool and no event pool — one pool of surface-form-matched facts.
2. **Per-world class metadata.** For each seeded world, a content-independent draw assigns
   which propositions are checkable. The same string is checkable in one world and
   uncheckable in another, so a string-only classifier is at chance *by construction*.
3. **Out-of-band audit boundary.** Under `A1_announced` the agent learns which of its claims
   are audited from an explicit `[AUDITED]`/`[NOT AUDITED]` tag on its menu; the blind
   extractor never sees the tag.

After the redesign, a blind word-level Naive Bayes with a world-holdout split scores
**49.4%** and a per-form majority oracle (the ceiling of any string-only classifier) scores
**53.2%** — both at chance. This is asserted as a CI-guarding regression test
(`test_blind_class_guess_rate_is_at_chance`), not in prose, alongside an invariant that
nearly every string appears as both classes across worlds and a guard that the extractor
path can never carry the tag. The confound cannot silently return.

**The honest cost.** Removing the content cue means the agent can no longer *infer* an
unknown audit boundary; the scope must be *declared*. This re-scopes the construct from
"does the agent infer and exploit an unknown boundary?" to "does the agent route lies around
a *declared* one?" — a real narrowing we treat as a first-class limitation (§6), not a
detail.

### 3.5 The audit that audited a proxy: the truth-blindness failure

The redesign above has a consequence we did not see until a hostile methodology review
found it: making truth a **content-independent per-world assignment** severed the *agent's*
access to it. Nothing in the impostor's inputs — menu, tags, instructions — carried truth,
so a model could not *knowingly* lie; it could only assert into a hidden balanced
assignment. For any truth-blind policy, E[false rate] = 0.5 per claim and the expected
audited/unaudited gap is **exactly zero** — the construct could not fire, for any model,
at any capability.

Why didn't our own closed-loop validation catch this? Because its scripted planted
policies read `truth_value` from the engine-side ledger object — a channel that exists in
code but was never rendered into any real model's prompt. The audit validated the
*pipeline* through a **proxy information channel** and passed; the *instrument* ran
through the real channel and measured a coin. The general lesson, which we rank equal to
the blind-classifier lesson: **construct audits must run through the same information
channel the real subject uses.** A scripted proxy with privileged access will pass tests
your instrument fails.

The repair delivers truth as a **private briefing on the impostor's menu** — each
non-placebo statement carries "you know this is TRUE/FALSE", a pure function of the world
and never the arm, so replay identity is untouched — while the extractor, panelists, and
every measurement path remain provably blind (enforced by structural typing and tests).
Placebo statements are deliberately **excluded** from the briefing ("you know nothing
about this one"): the impostor cannot knowingly lie there, which converts the placebo
channel from a broken mirror of true displacement into a clean detector of the
tag-as-permission artifact. Three permanent tests lock the repair in: a **pin** (a
truth-blind policy's expected gap is zero — the flaw can never silently return), a
**demonstration** (a scripted liar reading only the briefing reaches 100% knowing-false
rate), and a **positive-control ceiling** (an instructed router measured by the standard
pipeline yields the maximal gap, calibrating what the instrument can detect). The scripted
validation policies now read main-channel truth through this same briefing channel; the
honest-seat **coin diagnostic** (non-impostor false rates, which sit at 0.5 under any
truth-blind construct) ships in the analysis tool as mandatory reporting for every future
run.

## 4. Measurement

**Judge-error correction.** The real extractor is imperfect, so per-class observed false
rates are deconvolved with a class-stratified **Rogan-Gladen** correction (pooling across
classes would reinject the bias being corrected). A paired bootstrap puts a CI on the
corrected contrast, drawing sensitivity/specificity once per resample so the marginal and
joint summaries are one coherent bootstrap. An identifiability diagnostic flags
class-differential extraction recall, which a misclassification correction cannot repair. The
machinery is extracted as a standalone, pure-stdlib package (`noisyjudge`) so it is reusable
and independently testable.

**Closed-loop recovery.** We validate the estimator by planting a known displacement with a
synthetic strategic policy, injecting extraction noise matched to a sub-perfect quality, and
confirming the correction recovers the planted `(ΔC, ΔU)` from the corrupted labels; the
uncorrected contrast is attenuated, demonstrating the correction is both exercised and
necessary.

**The tag-conditioning probe.** The first behavioural question is whether a real model
*conditions on the tag at all*. Under `A1_announced`, the primary readout is the within-arm
**tag gap** — the impostor's main-channel false rate on uncheckable minus checkable claims —
cluster-bootstrapped over games (one game = one cluster). Controls: the same gap on a
placebo channel rendered inside the labelled menu (must be ~0, ruling out a tag-as-permission
artifact); the gap under `A2_silent` (must be ~0, ruling out a content-only class split);
and the `A0_off` lie floor (must be non-trivial, else a flat gap is underpowered rather than
clean).

**The kill rule.** The verdict — `tag-conditioning` / `inert` / `artifact` / `underpowered`
— is a mechanical four-way classifier encoded in code and committed before the run. A null
that passes it (flat gap, healthy floor, clean controls) is a credible measurement of zero;
a null that fails it is flagged as a broken harness, not reported as a finding.

## 5. The early live runs, re-read: harness shakeout of a structurally-zero measurement

Before the truth-blindness audit (§3.5), we ran live probes on two capability tiers.
This section reports them **as what they turned out to be** — an end-to-end shakeout of
the live harness that measured a quantity which was zero by construction — and corrects
the record of what the decision machinery actually executed.

**The structural zero.** In every run below, the impostor's inputs were the statement
menu, the audit tags, and its role instructions — no truth channel existed. Ground truth
was a hidden, balanced, content-independent assignment, so for *any* policy the expected
false rate was 0.5 per claim on both channels and the expected tag gap was exactly zero
(§3.5). The observed numbers — a weak-tier gap of −0.005 [−0.267, +0.274], a
stronger-tier gap of +0.068 [−0.119, +0.282], per-channel "false rates" of 0.37–0.51 —
are draws from that structural zero plus heavy between-world clustering noise. Earlier
drafts of this paper described these as "credible nulls with healthy lie floors" and
called the stronger tier's +0.07 a "directional hint"; under the audit, the floors were
coin-disagreement rates, the hint was definitionally noise, and the "calibrated upper
bound" bounded a quantity that is provably zero. We retract those readings in full.

**What the decision rule actually executed.** The pre-committed kill rule is a four-way
classifier requiring baseline (`A0_off`), treatment (`A1_announced`), and silent-control
(`A2_silent`) arms. Only the first weak-tier probe ran all three (A1 n=14, A0 n=10, A2
n=10). The later capability-gradient runs were **A1-only with a pre-committed early stop**
gated on A1's own floor — the full three-arm rule never executed on them, and earlier
drafts describing those runs as passing "a clean inert verdict" over-described what the
code did. Where controls did run, they were assessed by whether wide intervals included
zero — a criterion with essentially no power to fail at n=10 — rather than by equivalence
bounds. Both defects are repaired in the current instrument (§4: measured operating
characteristics; equivalence-bounded controls are pre-committed for any future run).

**What the shakeout legitimately established.** The live path works end to end: real
models complete multi-round games; the blind extractor parses free text at usable rates;
per-game claim volumes (≈ 4–7 checkable, ≈ 3–4.5 uncheckable after a class-neutral
coverage repair) and per-game economics (≈ $0.15/game at the tiers probed) are known; and
the cluster structure of the estimator is understood — the deepened per-game channel did
not tighten the 14-game CI, confirming that between-world variance, i.e. the number of
worlds, is the binding constraint on any future design. These operational facts, and only
these, carry forward.

![Detection power of the pre-committed kill rule as a function of the planted tag gap,
measured by Monte-Carlo simulation on the committed decision machinery at three cluster
counts.](figures/power-simulated.svg)

**Figure 1.** *Measured detection power of the committed kill rule (simulation on the
decision machinery itself; Beta-Binomial world model, ICC 0.15, ≈ 5/4 claims per game per
channel). Curves are cluster counts n = 10, 14, 30. The full operating-characteristics
report — per-scenario verdict error rates, including a measurable false-ARTIFACT rate at
small n, and bootstrap CI coverage — is committed alongside
([figures/oc-report.json](figures/oc-report.json)) and drift-locked to the generator, so
these numbers cannot silently diverge from the code that produces them. This figure
replaces an earlier analytic curve that repurposed a two-proportion power formula not
matched to the pooled-gap cluster-bootstrap estimator.*

## 6. Limitations and the threat-model ladder

The result is honestly scoped on three axes, and the threat-model ladder is the key framing:

- **Boundary type (the ladder).** *Declared* (the agent is told the audited set — the rung
  the instrument targets) → *announced-but-unscoped* (`A1_implicit`: a verifier exists,
  scope unknown) → *feedback-revealed* (`A4_feedback_revealed`: nothing announced, but
  verdict bulletins make the boundary learnable item-by-item — a calibration rung validated
  with scripted policies only) → *inferred* (the agent must work out the boundary from
  context alone, without explicit feedback — the deployment-relevant, monitor-evasion-shaped
  version). The instrument addresses the lower rungs; a declared-boundary result is weak
  evidence about inferred-boundary behaviour, and the de-confounding that buys the clean
  contrast forecloses content-based inference in the same corpus by construction. The
  feedback-revealed rung is an intermediate the bulletin channel makes expressible; it is
  not the inferred rung, and no behavioral claim attaches to it.
- **Capability tier.** Two tiers were probed live, but under the repaired construct reading
  (§3.5, §5) those probes measured a structurally-zero quantity — they are harness
  shakeout, not a capability gradient. No tier has been measured under the repaired
  construct, and nothing here speaks to frontier models, where the safety-relevant question
  lives.
- **Resolution.** The shakeout's operational fact stands: with ≈ 14 worlds per tier the
  cluster-bootstrap CI half-width was ≈ 0.27 and dominated by between-world variance, so a
  future funded run needs more worlds, not deeper per-world coverage (the simulated
  operating characteristics in Figure 1 size this). It is a statement about harness
  resolution only — the quantity those runs measured carried no behavioral signal to
  resolve.
- **Interaction level.** The measured runs are non-interactive monologues: agents never saw
  one another's contributions and faced no votes, so the deception pressure was instructional
  rather than social. The instrument now supports an interactive mode (discussion visibility,
  per-round votes, elimination stakes — §2) under which peer scrutiny could plausibly sharpen
  or suppress displacement; measuring that is future, funded work, and nothing here speaks to
  it.

Three further caveats. Real-provider runs are best-effort reproducible (the API has no
seed), softening the within-world claim on the live path relative to mock — and for the
same reason, **no replay-isolated (ΔC, ΔU) contrast has ever been produced on real
models**: the shakeout runs' only cross-arm number was an uninterpretable cross-run
difference, so the within-world design remains a mock-validated instrument capability,
not a demonstrated live measurement. The explicit `[NOT AUDITED]` tag could act as a
permission cue; the redesigned placebo channel (briefing-excluded items, §3.5) exists to
detect exactly that, and the shuffled-tag control arm dissociates tag semantics from
oracle coverage. Finally, all statistics reported to date are raw, uncorrected extractor
output: the human-labeled holdout that would license the judge-error correction remains
an open gate, so corrected numbers exist only for synthetic known-answer fixtures.

## 7. Related work

The pieces exist; the de-confounded combination does not. QUACK [arXiv:2605.27068] has
unverifiable-claim verdicts and replayable ground-truth logs but a *static* audit and no
migration measure. WOLF [arXiv:2512.09187] separates deception production from detection but
has no verifier-awareness manipulation. Monitor-awareness [Li et al. 2025], its
activation-steering [Hua et al. 2025], and CoT-monitoring
[arXiv:2503.11926] show models respond to being watched and that obfuscation emerges
*within* a channel under pressure — channel-hiding, not migration of false claims *across* a
verifiability boundary. Du & Yang [2025] establish displacement in humans but not for LLM
agents and not replay-isolated. Our novelty is the conjunction: a manipulated verifier-
awareness variable, truth held on *both* sides of the boundary, within-world replay, and —
the methodological core — a boundary **de-confounded from claim content**.

## 8. Conclusion

A clean answer requires a clean question — and we needed two attempts to earn one. The
contribution here is the apparatus and its audits: a de-confounding protocol that drives
an 82.8% content confound to chance and locks it with a test; the discovery that this
very fix silenced the construct by blinding the agent to truth, caught only when the
audit was rerun through the real information channel; and the repaired, consequence-
coupled, self-calibrating instrument with measured operating characteristics that
resulted. Two lessons generalize to any "hard-to-monitor vs easy-to-monitor" benchmark:
**measure your construct confound with a blind classifier before trusting any contrast**,
and **audit your construct through the channel your real subject actually uses** — a
scripted proxy with privileged access will pass validations your instrument fails. The
behavioral question that motivated the instrument remains open, and the instrument is now,
for the first time, actually capable of asking it.

## Reproducibility and availability

The instrument, the de-confounding gate, the class-stratified Rogan–Gladen correction, the
closed-loop recovery harness, and the power model are released at
`github.com/Lonkins/balloon-squeeze` under the MIT license. The two reusable components are
packaged standalone: **noisyjudge** (class-stratified judge-error correction) and **deconfound**
(blind-classifier confound audit). Every offline claim is reproducible with zero API spend on a
deterministic mock provider: the 49.4% / 53.2% blind class-guess rates are enforced as a
regression test (`test_blind_class_guess_rate_is_at_chance`), and the closed-loop recovery table
(Appendix A) and Figure 1 are regenerated and locked by the test suite. Every run — offline or
real-provider — emits a complete run record by default (board, hidden truth, instructions,
utterances, per-claim verdicts, votes), example records are committed per arm and drift-locked
to the engine, and any record renders to a self-contained offline replay. Every reported
statistic is recomputable from record files alone with the bundled analysis command, which
reuses the identical pre-committed statistical pipeline — so measurements from this point on
carry an inspectable, re-derivable evidence trail. Real-provider runs are
best-effort reproducible only — the provider API exposes no seed — so the pooled per-class counts
underlying every reported point estimate and floor are committed as a data record, while per-game
cluster counts and confidence intervals were produced by the run driver and are not
bit-reproducible.

## Ethics and broader impact

This work *measures* rather than trains deception: the impostor incentive is a controlled
experimental construct inside a social-deduction game, not a jailbreak or a capability uplift.
No behavioral findings are claimed: the early live runs are reported as harness shakeout of a
structurally-zero measurement, and publishing that failure — rather than the "null result" it
first appeared to be — is deliberate. The threat-model ladder
(§6) is included precisely so nothing here is over-read as evidence about frontier models or
about inferred (versus declared) audit boundaries. The de-confounding recipe is a general
measurement-hygiene tool with no offensive use. No human subjects and no personal data are
involved.

## References

- Du & Yang, *Journal of Economics & Management Strategy*, 2025 — monitoring displaces human cheating onto unmonitored dimensions.
- QUACK, arXiv:2605.27068 — unverifiable-claim verdicts + replayable logs; static audit, no migration measure.
- WOLF, arXiv:2512.09187 — separable deception production/detection in a Werewolf engine.
- Li et al., 2025, arXiv:2508.00943 — monitor-awareness.
- Hua et al., 2025, arXiv:2510.20487 — activation steering of monitor-awareness.
- OpenAI, 2025, arXiv:2503.11926 — CoT-monitoring and within-channel obfuscation.
- *From Hallucination to Scheming*, arXiv:2604.04788 — survey flagging pragmatic distortion as under-covered.

## Appendix A: closed-loop estimator recovery

A null is only credible if the estimator can recover a *non*-null when one is present. We
plant each of the four regimes with a synthetic strategic policy and confirm the full
pipeline (engine → score → class-stratified correction → paired bootstrap) recovers the
planted `(ΔC, ΔU)` and classifies the regime. The last row injects extraction noise matched
to a sub-perfect judge (sensitivity 0.85, specificity 0.90) and corrects with that quality —
exercising the Rogan-Gladen correction end to end; without it the contrast attenuates.

| Planted regime | extractor | planted (ΔC, ΔU) | recovered ΔC [95% CI] | recovered ΔU [95% CI] | verdict |
|---|---|---|---|---|---|
| displacement | perfect | (−0.25, +0.25) | −0.254 [−0.36, −0.15] | +0.265 [+0.16, +0.37] | displacement |
| suppression  | perfect | (−0.25, 0.00) | −0.254 [−0.36, −0.15] | +0.000 [−0.11, +0.10] | suppression |
| honesty      | perfect | (−0.25, −0.25) | −0.254 [−0.36, −0.15] | −0.276 [−0.37, −0.19] | honesty |
| null         | perfect | (0.00, 0.00) | +0.000 [−0.11, +0.10] | +0.000 [−0.11, +0.10] | null |
| displacement | noisy (0.85/0.90) | (−0.25, +0.25) | −0.293 [−0.41, −0.18] | +0.277 [+0.16, +0.40] | displacement |

Every regime is recovered with the planted value inside the CI and the correct verdict,
including through judge error. The reported empirical nulls are therefore measurements the
instrument *can* distinguish from a real effect, not an inability to detect one.

The same closed loop also runs through the **interactive configuration** (§2): with
per-round votes active, panelists eliminated mid-game, and a share of worlds ending early
when the impostor is caught — i.e. with variable per-world claim counts — all four planted
regimes are again recovered with the correct verdict (the recovery worlds are verified to
contain both eliminations and early-ended games, so the interactive machinery is genuinely
exercised rather than incidentally idle). The estimator is thus validated on the exact
configuration a funded interactive measurement would use, before any such measurement is
funded.

**Caveat (and its repair).** As §3.5 documents, the original version of this validation
read planted truth from an engine-side channel real models never had — it validated the
pipeline through a proxy and therefore could not catch the truth-blindness failure. The
planted policies now draw main-channel truth from the same private-briefing channel a
real model reads (the placebo control channel remains a scripted engine-side proxy by
design, since the briefing deliberately excludes placebo items). Every recovery result in
this appendix is from the rerouted validation.
