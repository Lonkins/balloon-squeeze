# Real-model run record

The committed source-of-record for every real-model (paid) result reported in
[`paper/balloon-squeeze.md`](../paper/balloon-squeeze.md). The deterministic, zero-spend
results (the de-confounding gate, the closed-loop recovery) are reproduced by the test
suite, not recorded here.

> **Recomputability (2026-07-03, forward-looking).** Runs from this point on persist a
> complete per-game run record ([format](../docs/record-format.md)) and re-derive every
> reported statistic from those files via `bsq analyze` — so future tables in this document
> will be recomputable by anyone from committed evidence. The historical summaries below
> predate record capture and remain exactly as recorded: their per-game data were not
> persisted and they are **not** recomputable.

**Why pooled, not per-game.** The within-`A1` tag gap and its CI are cluster-bootstrapped
over games; the per-game cluster counts are computed in-process by the run driver and
were not persisted, and the provider's API has no seed, so the paid runs are not
bit-reproducible. The pooled per-class counts below pin the reported point estimates and
floors; the CIs are the values the driver's `probe.gap_ci` returned at run time.

Fixed config for all runs unless noted: `n_topics=12`, `rounds=3`, `n_agents=5`,
`temperature=0`, A1-first early-stop, `max_tokens` 384 (policy) / 512 (extractor). Total real
spend across the whole project ≈ **$6.4**.

## 1. First probe — weak tier, thin channel (2026-06-17)

Tier: **weak** (a small, fast model). Original (pre-repair) coverage nudge (`max_tokens` 256 policy) → ≈ 2.8 uncheckable
claims/game. Full three-arm run.

| arm | games | checkable false/total (rate) | uncheckable false/total (rate) | tag gap (U−C) [95% CI] | verdict |
|-----|------:|------------------------------|--------------------------------|------------------------|---------|
| `A1_announced` | 14 | 22/60 (0.367) | 17/41 (0.415) | **+0.048** [−0.223, +0.288] | inert |
| `A0_off` | 10 | (0.211), 3.80/game | (0.429), 2.80/game | — | — |
| `A2_silent` | 10 | 13/41 (0.317) | 12/28 (0.429) | +0.111 [−0.112, +0.312] | clean |

ΔC (A0.C − A1.C) = −0.156 (noisy, cross-run; not interpreted). Healthy floor; clean controls.

## 2. Capability gradient — repaired channel (2026-06-17)

Class-neutral coverage repair (`four or five statements`, `max_tokens` 256→384) → ≈ 4.4–4.5
uncheckable claims/game. A pre-flight stronger-tier smoke (2 games) confirmed
`U/game = 4.00` before any full run. Both tiers run A1-first through the **identical**
pipeline; both early-stopped `inert`.

| tier | games | checkable false/total (rate) | uncheckable false/total (rate) | tag gap (U−C) [95% CI] |
|------|------:|------------------------------|--------------------------------|------------------------|
| weak (repaired) | 14 | 41/102 (0.402) | 25/63 (0.397) | **−0.005** [−0.267, +0.274] |
| stronger | 14 | 44/100 (0.440) | 31/61 (**0.508**) | **+0.068** [−0.119, +0.282] |

No confirmatory displacement on either tier (both CIs contain 0). The stronger tier lied more
on its unaudited claims (0.508 vs 0.440): a faint +0.07 hint in the predicted direction,
≈ 0.7 SE from zero, unresolved at this budget. Per the committed power model the hint needs
≈ 180–300 worlds/arm (Figure 1); 14 worlds resolve only a gross effect (MDE ≈ 0.20). Zero
truncations on the weak tier, one on each stronger-tier run (tolerated, partial text used).
