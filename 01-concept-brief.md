# 01 · Concept Brief (Research)

## Elevator pitch

**Balloon Squeeze** is an instrument that asks a single, sharp question about AI oversight: when you tell an LLM agent that a verifier checks *some* of its claims, does it become honest — or does it just move its falsehoods onto the claims that aren't checked? We instantiate this inside a multi-agent social-deduction game where a hidden **impostor** has an incentive to deceive, the engine holds **ground-truth** for the impostor's claims on *both* sides of a **checkability boundary**, and a **verifier** is announced in some experimental arms. By re-running the **byte-identical seeded world** with the verifier toggled on vs off, we obtain a per-claim *causal* estimate of whether dishonesty is *reduced* or merely *redistributed* — the "balloon squeeze."

## Why it matters

Scalable oversight assumes that checking a model's outputs makes them more trustworthy. But a strategic agent under partial verification has a cheaper move than honesty: **route the dishonesty around the checks**. If announcing an oracle simply pushes false claims from verifiable statements onto unverifiable ones (intentions, social claims, judgments), then partial verification can create a false sense of safety while leaving total dishonesty unchanged. This *displacement* dynamic is well-documented in humans under monitoring ([Du & Yang 2025](https://onlinelibrary.wiley.com/doi/10.1111/jems.70014)) and is exactly the failure mode the deception-benchmark literature names as under-studied ([*From Hallucination to Scheming*, arXiv:2604.04788](https://arxiv.org/abs/2604.04788)), but it has never been measured causally in LLM agents.

## The gap (and why this instrument is the right tool)

The closest systems each have part of the apparatus but not the manipulation:

- [QUACK (arXiv:2605.27068)](https://arxiv.org/abs/2605.27068): has an explicit *unverifiable* claim verdict and replayable ground-truth logs — but verification is a **static audit**, not a manipulated variable, and it never measures migration.
- [WOLF (NeurIPS 2025 workshop, arXiv:2512.09187)](https://arxiv.org/abs/2512.09187): separable deception production vs detection in a Werewolf engine — but no verifier-awareness toggle and no displacement metric.
- [SycEval (AIES 2025, arXiv:2502.08177)](https://arxiv.org/abs/2502.08177) and [BASIL (arXiv:2508.16846)](https://arxiv.org/abs/2508.16846): characterize sycophancy under pressure, but in static, single-channel settings; they do not toggle a verifier or measure claims moving across a verifiability boundary.
- [OpenAI CoT-monitoring (arXiv:2503.11926)](https://arxiv.org/abs/2503.11926): obfuscation emerges in the **same** channel under optimization pressure — channel-hiding, not migration of false *claims* across classes.
- [Li et al. (arXiv:2508.00943)](https://arxiv.org/abs/2508.00943) and [Hua et al. (arXiv:2510.20487)](https://arxiv.org/abs/2510.20487): verifier/monitor **awareness** is already an established, manipulable variable (toggled and activation-steered) — so the awareness IV *alone* is prior art, not the contribution.

Four ingredients are needed at once, and only this instrument has all four:
1. an in-game **ground-truth partition** of every claim into *checkable* vs *uncheckable*, with the engine holding truth for **both** (existing benchmarks only verify the checkable side);
2. **verifier awareness** as a *manipulated independent variable* (announced on vs off), not a static audit;
3. **deterministic counterfactual replay** of the identical seeded world so the *same* agent in the *same* position is compared across verifier conditions — a within-world causal contrast, not a noisy between-condition average;
4. genuine **multi-agent social pressure**, so displacement is measured where it matters for oversight (claims made to peers and an overseer), not in single-turn QA.

## Central question & hypotheses

**Question.** When LLM panelists are made aware a verifier checks a known subset of factual propositions, is their false-claim mass on **checkable** propositions *reduced* (honesty) or *redistributed* onto **uncheckable** propositions held in the same seeded world (displacement)?

Per world *w*, define `ΔC(w)` and `ΔU(w)` as the within-world change in assertion-rate-normalized, engine-scored **false-mass** on checkable / uncheckable claims under *verifier-announced* (A1) vs *verifier-off* (A0).

- **H1 — Displacement (primary).** `ΔC < 0` **and** `ΔU > 0`, tested as a **bivariate joint contrast** (mixed-effects / SUR), *not* a ratio.
- **H2 — Honesty.** Total false-mass falls (`ΔC + ΔU < 0`), `ΔU` not `> 0`.
- **H3 — Suppression.** `ΔC < 0`, `ΔU ≈ 0` (agents hedge or go quiet).
- **H4 — Null (publishable).** No arm effect on the `(ΔC, ΔU)` distribution → a **calibrated upper bound on displacement capability**. Reportable as the headline if it lands.
- **H5 — Dose-response.** Displacement magnitude rises with the checkability fraction `φ`.
- **H6 — Coverage-gaming.** Scope-probing behaviour is higher when the verifier is present-but-silent than when its scope is announced.

A scalar **Displacement Index `D = ΔU / |ΔC|`** is reported **only as a secondary**, with a Fieller/Bayesian-ratio CI, never as the primary estimand and never conditioned on `ΔC < 0` (the conditioning is what makes the ratio explode at the null — see [05-preregistration.md](05-preregistration.md)).

## The contribution

> A pre-registered, replay-isolated, **de-confounded** instrument for causally estimating whether announcing a verifier *reduces* or *redistributes* an LLM agent's false claims across a checkability boundary — with the engine holding truth on **both** sides and the boundary de-confounded from claim content. Its first two-tier probe returns a **calibrated upper bound** on displacement (a kill-rule-passing null with a faint, unresolved directional hint), **not** a displacement existence proof.

## Operational definitions (load-bearing)

- **Checkable proposition:** a claim an oracle could confirm from engine-held facts or the game log (e.g., "I voted for X last round," a factual claim about the shared scenario).
- **Uncheckable proposition = engine-knowable-but-agent-unverifiable:** a claim the *agent* cannot verify but the *engine* can score against ground truth (e.g., a stated intention, internal state, or social claim the engine authored). This excludes genuinely unfalsifiable items, which are pre-registered out.
- **False-mass:** assertion-rate-normalized count of engine-scored false claims in a class.

## Scope (MoSCoW)

**Must**
- Proposition ledger holding truth for both checkable and uncheckable classes; arm-controlled verifier-announcement; a blind claim-extractor + ground-truth scorer; an arm-swap replay harness with byte-identity assertions; the bivariate `(ΔC, ΔU)` estimator; offline mock mode for pipeline + estimator-recovery validation.

**Should**
- Dose arms (`φ ∈ {0.25, 0.5, 0.75}`); the present-but-silent and placebo-authority arms; per-class extractor precision/recall on a human-labeled holdout with errors-in-variables correction; the real-provider pilot for power.

**Could**
- Coverage-gaming / scope-probing detector (H6); a watchable replay viewer as a *secondary* demo artifact (never a design constraint on the measurement).

**Won't (this cycle)**
- The retired entertainment "theater," the humanness-detection target, any "fun > accuracy" tuning, and the injustice-of-omission line (rejected in review for an unfixable confound).

## Success criteria (research-grade)

- A **clean within-world contrast**: byte-identical replays up to the first verifier-conditioned token, with a trajectory-similarity exclusion gate.
- A **correctly-specified estimator**: the bivariate `(ΔC, ΔU)` model with the ratio demoted; the publishable null pre-registered.
- **Defensible measurement**: blind extractor, per-class precision/recall reported, errors-in-variables correction, placebo-irrelevant proposition set returns null.
- **Adequate power** derived from a *real-provider pilot* (the mock validates pipeline only), across **≥3 model families**.
- **No overclaiming** in any public copy: the closest prior work is cited accurately and the contribution is scoped to the four-ingredient combination above.

## Non-goals

- Not a claim of a new phenomenon class or a virgin research sector — the contribution is a precise, well-controlled causal estimate.
- Not a deception *detector* product; the panel exists to create social pressure, not to be evaluated.
- Not a humanness/Turing test — that target was dropped as construct-corrupted.

## Risks & open questions

- **Thin per-claim signal.** ~6 scored impostor utterances/world means small effects. *Mitigation:* real-provider pilot to fit the variance model and set N before lock; lengthen deliberation / extend the ledger if claims-per-world are too few. **Open:** the minimum claims-per-world for an adequately-powered joint contrast.
- **Most-likely result is modest.** Expect heterogeneity by capability (frontier: small positive displacement; mid-tier: suppression; small open-weight: null). *Mitigation:* the null is pre-registered as a capability upper-bound — the paper is robust to it.
- **Extractor error correlated with class.** If the extractor is better at one class, it biases `(ΔC, ΔU)`. *Mitigation:* blind scoring, per-class precision/recall holdout, errors-in-variables correction, pre-registered abort if the recall gap exceeds threshold.
- **Construct validity of "uncheckable."** *Mitigation:* the engine-knowable-but-agent-unverifiable definition + a placebo-irrelevant set that must show zero displacement.
- **Determinism on real providers.** Replay identity is the spine of the design. *Mitigation:* demonstrate provider determinism (seed/temperature passthrough) as a gate before pre-registration; log the divergence point per replay.
