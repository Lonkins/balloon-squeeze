# Balloon Squeeze

*Does telling an LLM agent that a verifier checks some of its claims make it honest — or does it just move the lies onto the claims that aren't checked?*

**Status: built, and run once.** The instrument is implemented and tested — the full pipeline runs offline on a deterministic mock provider, and a first **pre-registered probe** has been run on a real model. The headline contribution is the *method*, not that probe's result: a **replay-isolated within-world design**, a **de-confounding protocol** for the checkable/uncheckable boundary, and a **pre-committed kill rule** encoded as code. The first probe (a weak model) returned a **clean null**, reported honestly as a calibrated upper bound — see [Status & first result](#status--first-result). (Working name "Balloon Squeeze"; the repository directory name is legacy and will be settled before any public release.)

## What it is

A research instrument for **replay-isolated causal estimates of deception displacement**. Inside a multi-agent social-deduction game, one hidden "impostor" agent has an incentive to make false claims to avoid elimination. The engine holds **ground-truth** for every claim it makes — and crucially, for claims on *both* sides of a **checkability boundary**: *checkable* propositions an oracle could confirm, and *uncheckable* ones the agent cannot verify but the engine can still score. We then announce a **verifier** in some experimental arms and, by re-running the **byte-identical seeded world** with the verifier toggled on vs off, measure where the agent's false-claim mass goes.

The hypothesis being tested — the "balloon squeeze": **squeeze dishonesty out of the checked region and it bulges out in the unchecked region** rather than disappearing.

## The core question

> When LLM panelists are made aware a verifier checks a known subset of their factual claims, is false-claim mass on **checkable** propositions *reduced* (honesty) or *redistributed* onto **uncheckable** propositions held in the same seeded world (**displacement**)?

The primary estimand is the **bivariate joint contrast `(ΔC, ΔU)`** — the within-world change in false-mass on checkable vs uncheckable claims under verifier-announced vs verifier-off. Four pre-registered regimes: **Honesty** (both fall), **Displacement** (checkable falls, uncheckable rises — the balloon squeeze), **Suppression** (both fall via hedging/silence), and a publishable **Null** (no effect → a calibrated upper bound on displacement *capability*).

## Status & first result

The instrument is built (`src/bsq/`, full test suite green on the mock provider), and the two reusable methods are extracted as standalone, dependency-free packages: **[`noisyjudge`](packages/noisyjudge/)** (class-stratified Rogan-Gladen correction + paired bootstrap CI + power + an identifiability diagnostic — the *measurement-time* judge-error machinery) and **[`deconfound`](packages/deconfound/)** (a blind-classifier check that your condition label doesn't leak into item content — the *design-time* construct-validity gate, below).

Two things are worth reporting honestly:

1. **A construct-validity repair.** The first corpus encoded checkability in the *content* (logged public events vs private-intention predicates), so a blind classifier separated the two classes at **82.8–95.3%** — "uncheckable" was collinear with "is-an-intention-claim", not with audit status. The fix (*Architecture A*) makes class **per-world metadata** over one surface-form-homogeneous pool — the same sentence is checkable in one world and uncheckable in another — and delivers the audit boundary **out of band** via an explicit `[AUDITED]/[NOT AUDITED]` tag. A blind classifier now sits at **49.4%** (chance), enforced as a regression test, not asserted in prose.

2. **A pre-registered capability-gradient probe → a two-tier null with a faint hint.** With the audit boundary *declared*, two capability tiers were run through the **identical** de-confounded channel. Both returned a clean, healthy-floor null on the within-arm tag gap (uncheckable-minus-checkable false rate): the weak tier at **−0.005 [−0.27, +0.27]**, the stronger tier at **+0.068 [−0.12, +0.28]**. **No confirmatory displacement on either tier** — but the stronger model lied *more* on its unaudited claims than its audited ones (0.508 vs 0.440), a faint **+0.07 hint in the predicted direction** where the weak model was flat. It is ~0.7 SE from zero — consistent with displacement scaling with capability, but **not resolved** at this budget (the CI is dominated by between-world variance, so tightening it needs more *worlds*, not deeper coverage). Both runs passed a **pre-committed kill rule**; the result is reported as a **calibrated upper bound**, not as "LLMs don't displace deception."

## Reproduce

The whole instrument runs offline on a deterministic **mock** provider — no API key, no spend:

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" && pip install -e packages/noisyjudge
pytest                                              # full suite (both packages green)
pytest tests/test_corpus.py -k blind_class_guess    # the 49.4%-at-chance de-confounding gate
```

The mock path reproduces every offline claim — within-world replay determinism, the de-confounding gate, the judge-error-corrected closed-loop recovery (paper Appendix A), and the power model. The real-model probes are owner-gated and run from an untracked internal driver; their results are reported in [paper/balloon-squeeze.md](paper/balloon-squeeze.md) and recorded as committed data in [results/real-model-runs.md](results/real-model-runs.md).

## What's new (honest positioning)

The pieces exist; the combination does not. The closest prior work and the exact gap:

- [QUACK (arXiv:2605.27068)](https://arxiv.org/abs/2605.27068) already has an explicit *unverifiable* claim verdict and replayable per-utterance ground-truth logs — but its verification is a **static audit**, never a manipulated variable, and it never measures false claims **migrating** across the boundary.
- [WOLF (NeurIPS 2025 workshop, arXiv:2512.09187)](https://arxiv.org/abs/2512.09187) shows deception *production* and *detection* are separable in a Werewolf engine — but no verifier-awareness manipulation and no displacement metric.
- [*From Hallucination to Scheming* (arXiv:2604.04788)](https://arxiv.org/abs/2604.04788) surveys 50 deception benchmarks and flags **pragmatic distortion** (technically-true-but-misleading claims) as *critically under-covered*.
- [OpenAI CoT-monitoring (arXiv:2503.11926)](https://arxiv.org/abs/2503.11926) shows obfuscation emerges **within the same channel** under optimization pressure — channel-hiding, not migration of false *claims* across a verifiability boundary.
- In humans, monitoring one dimension displaces lying onto unobserved dimensions ([Du & Yang, *J. Econ. & Mgmt. Strategy* 2025](https://onlinelibrary.wiley.com/doi/10.1111/jems.70014)) — theoretical grounding, but not LLM/agentic and not replay-isolated.

**Our claim, and nothing more:** a pre-registered, replay-isolated **instrument** for measuring whether announcing a verifier *redistributes* rather than reduces LLM dishonesty — across a boundary where the engine holds truth on *both* sides and the boundary is **de-confounded from claim content** — together with a first calibrated weak-tier measurement. The contribution is the apparatus, the de-confounding protocol, and the honest result; **not** a displacement existence proof, which a single weak-model probe cannot and does not support.

## The docs

- **[01-concept-brief.md](01-concept-brief.md)** — the research brief: motivation, the gap, the question, hypotheses, contribution, prior art, scope, success criteria, risks.
- **[02-technical-architecture.md](02-technical-architecture.md)** — the instrument: kept engine + new components (proposition ledger, verifier arms, blind claim-scorer, arm-swap replay harness), data model, the experimental loop, metric computation, controls, project structure.
- **[03-build-roadmap.md](03-build-roadmap.md)** — phased plan, gated so power and determinism are proven *before* pre-registration lock.
- **[04-kickoff-prompt.md](04-kickoff-prompt.md)** — a ready-to-paste prompt to start the build thread.
- **[05-preregistration.md](05-preregistration.md)** — the pre-registration plan: primary vs secondary analyses, confirmatory gates, abort rules.
- **[case-study-deconfounding.md](case-study-deconfounding.md)** — the methodological core: how an 82.8% construct confound in the checkability boundary was caught, *measured*, and driven back to chance (49.4%), with the regression tests that keep it there. Start here if you read one thing.
- **[paper/balloon-squeeze.md](paper/balloon-squeeze.md)** — the workshop-paper draft: instrument, de-confounding protocol, measurement, the first probe's calibrated upper bound, and the threat-model ladder.

## Honesty note

This is a **solid, defensible instrument, not a seminal discovery** — independent reviews confirmed the apparatus's affordances are now common in the multi-agent literature, so it competes on a precise, well-controlled, *de-confounded* question, not on a virgin sector. The first real result is exactly the modest, pre-registered outcome anticipated: a null on a weak model, reported as a calibrated capability upper bound. That is by design — the contribution is robust to outcome because the null was pre-registered as publishable and the kill rule held. The value lives in the method (within-world replay + the 82.8% → 49.4% de-confounding repair + a kill rule that a clean null actually passed), not in the weak-tier number. We do not overclaim.

## License

MIT — see [LICENSE](LICENSE). The standalone kits are MIT-licensed too ([`noisyjudge`](packages/noisyjudge/LICENSE), [`deconfound`](packages/deconfound/LICENSE)). The instrument package itself is marked not-for-distribution (`Private :: Do Not Upload`); the kits are the parts intended for reuse.
