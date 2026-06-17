# Balloon Squeeze: a replay-isolated, de-confounded instrument for measuring deception displacement across an audit boundary

*Working draft — methods / instruments / negative-results workshop submission.*

## Abstract

When an agent is told that some of its claims are audited, does it become honest, or does
it move its falsehoods onto the claims it believes are unaudited? Measuring this
*deception displacement* cleanly is harder than it looks: the obvious operationalization —
contrasting "checkable" against "uncheckable" claims — confounds audit status with claim
*content*. We present **Balloon Squeeze**, a deterministic instrument that isolates the
contrast three ways. First, a **within-world replay** design: each seeded multi-agent game
is re-run byte-identically with only the verifier announcement toggled, so the audit
manipulation is the sole difference between arms. Second, a **de-confounding protocol**:
checkability is assigned as *per-world metadata* over a single surface-form-homogeneous
proposition pool, so the same sentence is checkable in one world and uncheckable in
another, and the audit boundary reaches the agent *out of band* via an explicit tag rather
than through content. We show this matters empirically: a blind classifier separated our
first (content-encoded) corpus at **82.8–95.3%**, and the redesign drives it to **49.4%**
(chance), enforced as a regression test. Third, a **pre-committed kill rule** encoded as
code, so a null is a measurement rather than a disappointment. A first pre-registered probe
on a weak model returns a **clean null** — no measurable displacement, with a healthy lie
floor and clean controls — which we report as a calibrated upper bound, not as a claim that
"LLMs do not displace deception." The contribution is the apparatus and the de-confounding
method; the weak-tier null is a worked demonstration that the instrument returns a
trustworthy zero.

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
its scope is not), `A2_silent` (a verifier runs but is not announced), and `A3_placebo` (a
moderator with no verification). The estimand is the within-world joint contrast
`(ΔC, ΔU)` — the change in false-mass on checkable and uncheckable claims between arms.

**Within-world replay.** Because the engine is deterministic and every consumer draws from
an arm-independent namespaced RNG substream, the *same seeded world* can be re-run under
each arm with byte-identical agent behaviour up to the point the announcement changes. The
contrast is therefore taken within a world, not between independent samples — a markedly
cleaner causal lever than the between-condition comparisons standard in this literature.

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

## 5. A first probe

We ran the probe on a weak model (a small, fast tier), owner-gated for cost, with the audit
boundary *declared*: 14 `A1_announced` games plus `A0_off` and `A2_silent` controls,
temperature 0.

The within-`A1_announced` tag gap was **+0.048, 95% CI [−0.223, +0.288]** — no measurable
displacement. The floor was healthy: the impostor lied on **21–43%** of its claims across
conditions, both channels populated (≈ 2.8–4.3 claims per game per class), with zero response
truncations. The `A2_silent` control gap was **+0.111, CI [−0.112, +0.312]** (includes zero;
no spontaneous class split). The cross-arm checkable contrast `ΔC` was small, noisy, and in
the anti-suppression direction; we do not interpret it. The probe **passed the kill rule** as
a clean `inert` verdict.

**Calibrated upper bound.** Rather than claim "no displacement," we report the bound the data
support: with 95% confidence the tag gap is **at most +0.29**. The implied resolution
(SE ≈ 0.13, so a minimum detectable gap of ≈ 0.36 at 80% power) means this rules out a
*gross* effect on this tier, for a *declared* boundary — and nothing finer. The binding
constraint is the thin uncheckable channel (≈ 2.8 claims/game); tightening the bound is a
matter of channel **depth**, not breadth.

## 6. Limitations and the threat-model ladder

The result is honestly scoped on three axes, and the threat-model ladder is the key framing:

- **Boundary type (the ladder).** *Declared* (the agent is told the audited set — what we
  measured) → *announced-but-unscoped* (`A1_implicit`: a verifier exists, scope unknown) →
  *inferred* (the agent must work out the boundary from context — the deployment-relevant,
  monitor-evasion-shaped version). We measured the **easiest rung**. A null on a declared
  boundary is weak evidence about inferred-boundary behaviour; the de-confounding that buys
  the clean contrast is exactly what forecloses the inferred version in the same corpus.
- **Capability tier.** This is a weak-model null. It confirms the field's prior that small
  models do not strategically route deception; it does not speak to capable models, which is
  where the safety-relevant question lives.
- **Resolution.** A wide CI on a thin channel rules out only a gross effect. A subtle effect
  below ≈ 0.3 is not excluded.

Two further caveats: real-provider runs are best-effort reproducible (the API has no seed),
softening the within-world claim on the live path relative to mock; and the explicit
`[NOT AUDITED]` tag could in principle act as a permission cue, which the placebo-inside-menu
control exists to rule out.

## 7. Related work

The pieces exist; the de-confounded combination does not. QUACK [arXiv:2605.27068] has
unverifiable-claim verdicts and replayable ground-truth logs but a *static* audit and no
migration measure. WOLF [arXiv:2512.09187] separates deception production from detection but
has no verifier-awareness manipulation. Monitor-awareness [Li et al. 2025] and CoT-monitoring
[arXiv:2503.11926] show models respond to being watched and that obfuscation emerges
*within* a channel under pressure — channel-hiding, not migration of false claims *across* a
verifiability boundary. Du & Yang [2025] establish displacement in humans but not for LLM
agents and not replay-isolated. Our novelty is the conjunction: a manipulated verifier-
awareness variable, truth held on *both* sides of the boundary, within-world replay, and —
the methodological core — a boundary **de-confounded from claim content**.

## 8. Conclusion

A clean answer requires a clean question. The value here is not the weak-tier null but the
apparatus that makes the null *trustworthy*: a within-world replay design, a de-confounding
protocol that drives an 82.8% content confound to chance and locks it with a test, and a
pre-committed kill rule a clean null actually passed. The reusable lesson generalizes to any
"hard-to-monitor vs easy-to-monitor" benchmark: measure the confound with a blind classifier
before trusting any contrast, move the distinction into metadata, deliver the manipulation
out of band, and lock it with a regression test.

## References

- Du & Yang, *Journal of Economics & Management Strategy*, 2025 — monitoring displaces human cheating onto unmonitored dimensions.
- QUACK, arXiv:2605.27068 — unverifiable-claim verdicts + replayable logs; static audit, no migration measure.
- WOLF, arXiv:2512.09187 — separable deception production/detection in a Werewolf engine.
- Li et al., 2025, arXiv:2508.00943 — monitor-awareness.
- OpenAI, 2025, arXiv:2503.11926 — CoT-monitoring and within-channel obfuscation.
- *From Hallucination to Scheming*, arXiv:2604.04788 — survey flagging pragmatic distortion as under-covered.
