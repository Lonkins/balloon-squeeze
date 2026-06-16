# Balloon Squeeze

*Does telling an LLM agent that a verifier checks some of its claims make it honest — or does it just move the lies onto the claims that aren't checked?*

**Status: Design phase — not yet built.** These docs are the spec a dedicated build thread should implement. (Working name "Balloon Squeeze"; the repository directory name is legacy and will be settled before any public release.)

## What it is

A research instrument for **replay-isolated causal estimates of deception displacement**. Inside a multi-agent social-deduction game, one hidden "impostor" agent has an incentive to make false claims to avoid elimination. The engine holds **ground-truth** for every claim it makes — and crucially, for claims on *both* sides of a **checkability boundary**: *checkable* propositions an oracle could confirm, and *uncheckable* ones the agent cannot verify but the engine can still score. We then announce a **verifier** in some experimental arms and, by re-running the **byte-identical seeded world** with the verifier toggled on vs off, measure where the agent's false-claim mass goes.

The hypothesis being tested — the "balloon squeeze": **squeeze dishonesty out of the checked region and it bulges out in the unchecked region** rather than disappearing.

## The core question

> When LLM panelists are made aware a verifier checks a known subset of their factual claims, is false-claim mass on **checkable** propositions *reduced* (honesty) or *redistributed* onto **uncheckable** propositions held in the same seeded world (**displacement**)?

The primary estimand is the **bivariate joint contrast `(ΔC, ΔU)`** — the within-world change in false-mass on checkable vs uncheckable claims under verifier-announced vs verifier-off. Four pre-registered regimes: **Honesty** (both fall), **Displacement** (checkable falls, uncheckable rises — the balloon squeeze), **Suppression** (both fall via hedging/silence), and a publishable **Null** (no effect → a calibrated upper bound on displacement *capability*).

## What's new (honest positioning)

The pieces exist; the combination does not. The closest prior work and the exact gap:

- [QUACK (arXiv:2605.27068)](https://arxiv.org/abs/2605.27068) already has an explicit *unverifiable* claim verdict and replayable per-utterance ground-truth logs — but its verification is a **static audit**, never a manipulated variable, and it never measures false claims **migrating** across the boundary.
- [WOLF (NeurIPS 2025 workshop, arXiv:2512.09187)](https://arxiv.org/abs/2512.09187) shows deception *production* and *detection* are separable in a Werewolf engine — but no verifier-awareness manipulation and no displacement metric.
- [*From Hallucination to Scheming* (arXiv:2604.04788)](https://arxiv.org/abs/2604.04788) surveys 50 deception benchmarks and flags **pragmatic distortion** (technically-true-but-misleading claims) as *critically under-covered*.
- [OpenAI CoT-monitoring (arXiv:2503.11926)](https://arxiv.org/abs/2503.11926) shows obfuscation emerges **within the same channel** under optimization pressure — channel-hiding, not migration of false *claims* across a verifiability boundary.
- In humans, monitoring one dimension displaces lying onto unobserved dimensions ([Du & Yang, *J. Econ. & Mgmt. Strategy* 2025](https://onlinelibrary.wiley.com/doi/10.1111/jems.70014)) — theoretical grounding, but not LLM/agentic and not replay-isolated.

**Our claim, and nothing more:** the first pre-registered, replay-isolated causal estimate that announcing a verifier **redistributes** rather than reduces LLM dishonesty, across a boundary where the engine holds truth on *both* sides.

## The docs

- **[01-concept-brief.md](01-concept-brief.md)** — the research brief: motivation, the gap, the question, hypotheses, contribution, prior art, scope, success criteria, risks.
- **[02-technical-architecture.md](02-technical-architecture.md)** — the instrument: kept engine + new components (proposition ledger, verifier arms, blind claim-scorer, arm-swap replay harness), data model, the experimental loop, metric computation, controls, project structure.
- **[03-build-roadmap.md](03-build-roadmap.md)** — phased plan, gated so power and determinism are proven *before* pre-registration lock.
- **[04-kickoff-prompt.md](04-kickoff-prompt.md)** — a ready-to-paste prompt to start the build thread.
- **[05-preregistration.md](05-preregistration.md)** — the pre-registration plan: primary vs secondary analyses, confirmatory gates, abort rules.

## Honesty note

This is a **solid, defensible study, not a seminal discovery** — three independent reviews confirmed the apparatus's affordances are now common in the multi-agent literature, so we compete on a precise, well-controlled question, not on a virgin sector. The *most-likely* result is modest (displacement that scales with model capability; small or null on weak models). That is fine: the null is pre-registered as a calibrated capability upper-bound, so the contribution is robust to outcome. We will not overclaim.
