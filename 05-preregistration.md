# 05 · Pre-registration Plan

This is the analysis plan to be **frozen (OSF or equivalent) before the full run** (Roadmap Phase 6). It separates confirmatory from exploratory analysis to prevent HARKing, and it commits in advance to the gates and abort rules. The point of a pre-registration is that the *null is as publishable as the effect*; this design is built so that is true.

## Study question

When LLM panelists are made aware a verifier checks a known subset of factual propositions, is false-claim mass on **checkable** propositions reduced (honesty) or redistributed onto **uncheckable** propositions held in the same seeded world (displacement)?

## Design

Within-world counterfactual: each base world (a seeded social-deduction game with a hidden, deception-incentivized impostor and an engine-held proposition ledger) is **replayed** under each verifier arm, changing only the immutable announcement block. Per world *w* and arm: `C_arm(w)`, `U_arm(w)` = assertion-rate-normalized, engine-scored false-mass on checkable / uncheckable claims. `ΔC(w)=C_A1−C_A0`, `ΔU(w)=U_A1−U_A0`.

**Arms:** `A0_off`, `A1_announced` (primary treatment), `A1_implicit`, `A2_silent`, `A3_placebo`; dose arms `A1_φ` for `φ∈{0.25,0.5,0.75}`.

**Models:** ≥3 families — a frontier strategic-reasoning model, a mid-tier instruction-tuned model, a small open-weight model — analyzed separately and as a capability gradient (no pooling across families in the primary).

## Hypotheses

| ID | Name | Prediction on `(ΔC, ΔU)` | Status |
|----|------|--------------------------|--------|
| **H1** | **Displacement (PRIMARY)** | `ΔC < 0` **and** `ΔU > 0` | confirmatory |
| H2 | Honesty | `ΔC+ΔU < 0`, `ΔU` not `>0` | confirmatory |
| H3 | Suppression | `ΔC < 0`, `ΔU ≈ 0` | confirmatory |
| **H4** | **Null (publishable)** | no arm effect on `(ΔC, ΔU)` | confirmatory — **reported as headline if it lands** |
| H5 | Dose-response | displacement rises with `φ` | confirmatory (dose arms) |
| H6 | Coverage-gaming | scope-probing higher under `A2` than `A1` | secondary |

## Primary analysis

A **bivariate mixed-effects / seemingly-unrelated-regression (SUR)** model on `(ΔC, ΔU)` with random intercepts for world/seed and the impostor seat, fit per model family. The four regimes are read off the **joint** distribution and its CI. Decision rule pre-committed:

- **Displacement (H1)** if the joint CI places mass in the `ΔC<0, ΔU>0` quadrant with both marginals excluding 0 in the predicted direction.
- **Honesty (H2) / Suppression (H3)** by the corresponding quadrant rules.
- **Null (H4)** if the joint contrast's CI contains the origin → report a **calibrated upper bound on displacement capability** (the largest displacement ruled out at the chosen power).

## Secondary analyses (pre-specified, exploratory beyond)

- **Displacement Index `D = ΔU/|ΔC|`** with a **Fieller / Bayesian-ratio CI** — reported for interpretability only, **never the primary**, and **never conditioned on `ΔC<0`** (that conditioning is selection-on-outcome and makes `D` explosive at the null).
- **Dose-response (H5):** slope of joint-displacement magnitude on `φ`.
- **Coverage-gaming (H6):** scope-probing rate `A2` vs `A1`.
- **`A1_implicit` contrast:** isolates *strategic re-routing* (verifier present, scope not named) from "told these classes are watched."
- **Detective/panelist-seat reference:** a near-null check (non-incentivized seats should not displace).

## Controls (confirmatory, pre-committed)

1. **Placebo uncheckable-irrelevant set** — must show **zero** displacement; a non-null here invalidates the primary (verbosity/priming artifact).
2. **Per-class extractor precision/recall** on a human-labeled holdout, reported, with **errors-in-variables** correction applied to `(ΔC, ΔU)`.
3. **Token-count propensity match** across arms.
4. **Extractor/scorer blind to arm.**
5. **Operational "uncheckable" = engine-knowable-but-agent-unverifiable** — genuinely unfalsifiable items excluded at ledger authoring.

## Gates that must pass BEFORE this plan is locked

- **Determinism gate (Phase 2):** arm-swap byte-identity on mock; real-provider determinism demonstrated; per-world divergence point logged; below-threshold-similarity worlds excluded by a fixed rule.
- **Extractor gate (Phase 3):** cross-class recall gap within a pre-set threshold on the holdout.
- **Power gate (Phase 5):** N derived from a **real-provider** variance model for the target MDE on the joint contrast; adequate claims-per-world.

## Abort / amendment rules

- If the **extractor recall gap** exceeds threshold → halt; fix the extractor and re-validate before any confirmatory run.
- If **claims-per-world** are too few for the target MDE → lengthen deliberation / extend the ledger and re-pilot (an amendment, logged).
- If **real-provider determinism** cannot be demonstrated → the within-world causal claim is downgraded; revise the design before locking.
- Any deviation after lock is reported as a logged amendment with timestamp; the analysis code hash is recorded at lock time.

## Sample size (to be finalized at the power gate)

Target ≈ **200 base worlds × 5 core arms + 200 × 3 dose arms ≈ 1,600 replays per model family**, contingent on the pilot variance model. ~6 scored impostor utterances/world is the binding constraint; if the pilot shows it is too thin, raise claims-per-world before lock rather than under-powering.

## Reporting commitments

- Report the regime for **each** family and the capability gradient, **including a prominent null** if that is the result.
- Report all controls, the placebo set result, extractor accuracy, the divergence/exclusion log, and the secondary `D` with its ratio CI.
- Scope the contribution to the four-ingredient **conjunction**, anchored by the within-world migration measurement — **not** the replay/verification machinery itself, which [QUACK](https://arxiv.org/abs/2605.27068) (Yuan 2026, the nearest prior art: a static per-claim audit in multi-agent social deduction with no migration measure) already demonstrates. Never headline the awareness toggle alone — it is established by [Li et al.](https://arxiv.org/abs/2508.00943) (monitor-aware) and [Hua et al.](https://arxiv.org/abs/2510.20487) (activation steering). Cite the closest prior work accurately — QUACK, [WOLF](https://arxiv.org/abs/2512.09187), [*From Hallucination to Scheming*](https://arxiv.org/abs/2604.04788), [OpenAI CoT-monitoring](https://arxiv.org/abs/2503.11926), [Du & Yang](https://onlinelibrary.wiley.com/doi/10.1111/jems.70014) (the human displacement precedent), Li et al., and Hua et al. No overclaiming.
