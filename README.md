# Balloon Squeeze

*Does telling an LLM agent that a verifier checks some of its claims make it honest — or does it just move the lies onto the claims that aren't checked?*

[![CI](https://github.com/Lonkins/balloon-squeeze/actions/workflows/ci.yml/badge.svg)](https://github.com/Lonkins/balloon-squeeze/actions/workflows/ci.yml) ![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg) ![Status: research preview](https://img.shields.io/badge/status-research%20preview-orange.svg)

> **Status:** early-stage research instrument. The offline `mock` path is stable and fully reproducible; the first two-tier probe is reported as a pre-registered, calibrated upper bound — not a displacement existence proof.

A deterministic, mock-first research instrument for **replay-isolated causal estimates of deception displacement**. It pairs a within-world replay design with a **de-confounding protocol** — one that caught an 82.8% construct confound and drove it to chance, locked by a regression test — and a **pre-committed kill rule** encoded in code. Built, tested, and run on a first pre-registered, two-tier measurement.

## What it is

Inside a multi-agent social-deduction game, one hidden "impostor" agent has an incentive to make false claims to avoid elimination. The engine holds **ground truth** for every claim it makes — and crucially, for claims on *both* sides of a **checkability boundary**: *checkable* propositions an oracle could confirm, and *uncheckable* ones the agent cannot verify but the engine can still score. We announce a **verifier** in some experimental arms and, by re-running the **byte-identical seeded world** with the verifier toggled on vs off, measure where the agent's false-claim mass goes.

The hypothesis — the "balloon squeeze": **squeeze dishonesty out of the checked region and it bulges into the unchecked region** rather than disappearing.

## The core question

> When an agent is made aware a verifier checks a known subset of its factual claims, is false-claim mass on **checkable** propositions *reduced* (honesty) or *redistributed* onto **uncheckable** propositions held in the same seeded world (**displacement**)?

The estimand is the within-world joint contrast `(ΔC, ΔU)` — the change in false-mass on checkable vs uncheckable claims, verifier-announced vs verifier-off. Four pre-registered regimes: **honesty** (both fall), **displacement** (checkable falls, uncheckable rises — the balloon squeeze), **suppression** (both fall via hedging), and **null** (no effect).

## The de-confounding result

Measuring this cleanly is harder than it looks. Our first corpus encoded checkability in the *content* — checkable claims were logged public events, uncheckable ones were private-intention predicates — so a blind classifier recovered the class from the text alone **82.8–95.3%** of the time. "Uncheckable" was collinear with "is-an-intention-claim", not with audit status: a construct confound that would have explained any result away.

The fix makes class **per-world metadata** over one surface-form-homogeneous pool — the same sentence is checkable in one world and uncheckable in another, so a string-only classifier is at **49.4%** (chance) *by construction*, enforced as a regression test. The audit boundary reaches the agent **out of band**, via an explicit `[AUDITED]/[NOT AUDITED]` tag the measurement path never sees.

→ The full detective story is in **[case-study-deconfounding.md](case-study-deconfounding.md)** — start here if you read one thing.

## Reusable kits

Two methods are extracted as standalone, dependency-free MIT packages:

- **[`noisyjudge`](packages/noisyjudge/)** — class-stratified, judge-error-corrected contrast estimation (Rogan-Gladen correction + paired bootstrap CI + power + an identifiability diagnostic) for noisy LLM-as-judge evaluations.
- **[`deconfound`](packages/deconfound/)** — a one-call blind-classifier check that your condition labels don't leak into item content. Run it on any benchmark before you trust an A/B contrast.

## Reproduce

The whole instrument runs offline on a deterministic **mock** provider — no API key, no spend:

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
bsq selftest                                        # zero-setup determinism check, no key
pytest                                              # full suite
pytest tests/test_corpus.py -k blind_class_guess    # the de-confounding gate, at chance
bsq analyze examples/transcripts                    # recompute statistics from record files
```

Every offline claim is reproducible this way — replay determinism, the de-confounding gate, the judge-error-corrected closed-loop recovery, and the power model. Real-model probe results are recorded in [results/real-model-runs.md](results/real-model-runs.md) and the [paper](paper/balloon-squeeze.md).

## Watch a game

Every run produces a complete **run record** (world, hidden truth, every utterance, every claim scored, votes, eliminations — see [examples/transcripts/](examples/transcripts/)), and any record renders to a self-contained offline replay:

```sh
bsq render examples/transcripts/A1_announced.json -o replay.html
open replay.html    # step through or press Play — watch where the lies land
```

The replay shows the statement board with its audited/unaudited boundary, each participant speaking in turn, per-claim lie/truth verdicts, the verifier's checks, the votes — and a running scoreboard of whether the impostor's false claims migrate to the unaudited side. Run your own game with `bsq run --interactive` (records land in `runs/`, capture is always on; the record format is documented in [docs/record-format.md](docs/record-format.md)). To make a shareable video: screen-record the autoplay replay, or `python tools/export_video.py <record.json>` if you have Playwright installed.

Two deliberation modes exist: **monologue** (the default — the configuration all recorded results were measured on) and **interactive** (`--interactive` — speakers see the evolving discussion and every round ends in a vote with elimination stakes). The recorded two-tier null is attributed to the monologue configuration; measuring displacement under interaction is future, funded work.

## First result

A first pre-registered probe ran two capability tiers through the identical de-confounded channel and returned a kill-rule-passing **null** on both, with a faint, unresolved hint in the displacement direction on the stronger tier. Full numbers, confidence intervals, and the power analysis are in the **[paper](paper/balloon-squeeze.md)**.

## How it compares

The pieces exist; the de-confounded combination does not. The closest prior work and the gap:

- [QUACK (arXiv:2605.27068)](https://arxiv.org/abs/2605.27068) already has an explicit *unverifiable* claim verdict and replayable per-utterance ground-truth logs — but its verification is a **static audit**, never a manipulated variable, and it never measures false claims **migrating** across the boundary.
- [WOLF (NeurIPS 2025 workshop, arXiv:2512.09187)](https://arxiv.org/abs/2512.09187) shows deception *production* and *detection* are separable in a Werewolf engine — but no verifier-awareness manipulation and no displacement metric.
- [*From Hallucination to Scheming* (arXiv:2604.04788)](https://arxiv.org/abs/2604.04788) surveys 50 deception benchmarks and flags **pragmatic distortion** (technically-true-but-misleading claims) as *critically under-covered*.
- [OpenAI CoT-monitoring (arXiv:2503.11926)](https://arxiv.org/abs/2503.11926) shows obfuscation emerges **within the same channel** under optimization pressure — channel-hiding, not migration of false *claims* across a verifiability boundary.
- Verifier/monitor **awareness** is already an established, manipulable variable — toggled by [Li et al. (arXiv:2508.00943)](https://arxiv.org/abs/2508.00943) and activation-steered by [Hua et al. (arXiv:2510.20487)](https://arxiv.org/abs/2510.20487) — so the awareness IV alone is not the contribution here.
- In humans, monitoring one dimension displaces lying onto unobserved dimensions ([Du & Yang, *J. Econ. & Mgmt. Strategy* 2025](https://onlinelibrary.wiley.com/doi/10.1111/jems.70014)) — theoretical grounding, but not LLM/agentic and not replay-isolated.

What's new is the conjunction: a manipulated verifier-awareness variable, truth held on *both* sides of the boundary, within-world replay, and a boundary **de-confounded from claim content**.

## Repository layout

```text
src/bsq/              the instrument — mock-first engine, ledger, verifier arms, replay,
                      run records (record.py), HTML replay renderer (render.py)
packages/noisyjudge/  reusable MIT kit — judge-error-corrected contrast estimation
packages/deconfound/  reusable MIT kit — blind-classifier label-leakage check
examples/transcripts/ committed run records, one per core arm (drift-locked to the engine)
paper/                workshop-paper draft + figures
results/              recorded real-model probe runs
tests/                determinism, the de-confounding gate, estimator recovery, power
tools/                optional helpers (video export of a replay)
01–05-*.md            concept brief, architecture, roadmap, pre-registration
```

Runtime records are written to `runs/` (gitignored); the committed examples above are deterministic, offline-generated, and locked to the engine by a regression test.

The two `packages/` kits are the parts intended for reuse; the instrument package is marked `Private :: Do Not Upload`.

## The docs

- **[case-study-deconfounding.md](case-study-deconfounding.md)** — the methodological core: catching, *measuring*, and killing the 82.8% confound, with the tests that keep it dead.
- **[paper/balloon-squeeze.md](paper/balloon-squeeze.md)** — the workshop-paper draft: instrument, de-confounding protocol, measurement, the first probe's calibrated bound, and the threat-model ladder.
- **[05-preregistration.md](05-preregistration.md)** — the pre-registration: primary vs secondary analyses, confirmatory gates, abort rules.
- **[01-concept-brief.md](01-concept-brief.md)**, **[02-technical-architecture.md](02-technical-architecture.md)**, **[03-build-roadmap.md](03-build-roadmap.md)** — the research brief, the architecture, and the phased build plan (including the canonical [remaining-gates list](03-build-roadmap.md#remaining-gates): what still needs funding or a maintainer decision).

## Contributing

Contributions are welcome — bug reports, kit improvements, and prior-art corrections especially. The `mock` provider makes the whole instrument reproducible offline, so most changes can be validated with `pytest` and no API spend. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for setup, the branch/PR workflow, and the research-integrity conventions (blind scoring, pre-registration, report-the-null).

Determinism on `mock` is a hard invariant: never merge a change that breaks replay reproducibility.

## License

MIT — see [LICENSE](LICENSE). The standalone kits are MIT-licensed too ([`noisyjudge`](packages/noisyjudge/LICENSE), [`deconfound`](packages/deconfound/LICENSE)). The instrument package itself is marked not-for-distribution (`Private :: Do Not Upload`); the kits are the parts intended for reuse.
