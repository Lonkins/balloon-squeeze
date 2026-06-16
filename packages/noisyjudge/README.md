# noisyjudge

Class-stratified, judge-error-corrected **contrast** estimation for noisy LLM-as-judge
evaluations. Pure standard library — no dependencies, deterministic, ~400 lines.

## The problem it solves

You want to measure how a binary rate **changes** between two conditions — e.g. *does
announcing a verifier reduce a model's false-claim rate?* — but your labels come from an
**imperfect judge** (an LLM grader, a classifier) that both **misses** items and gets their
**polarity wrong**. Naively differencing the observed rates is biased, and the bias is usually
**different per class**, so it does not cancel in a contrast. `noisyjudge` is the small,
auditable recipe that handles this correctly:

1. **`quality_by_class`** — estimate the judge's detection recall and falseness
   sensitivity/specificity on a labelled holdout, **stratified by class** (pooling reinjects
   exactly the class-differential bias you are trying to remove).
2. **`rogan_gladen`** — deconvolve an observed rate given that sensitivity/specificity
   (returns `NaN` at the identifiability singularity rather than inventing a value).
3. **`bootstrap_contrast` / `joint_regime`** — the corrected *treatment − baseline* change per
   class with a bootstrap CI, and the **joint two-class regime** — from one coherent resample
   in which the judge's sens/spec are **shared across arms within a draw** (one judge measures
   both conditions, so the contrast is not double-penalised for judge uncertainty).
4. **`required_units`** — the analytic sample size per arm for a target minimum detectable
   effect, accounting for the judge's error and within-unit clustering (design effect).
5. **`cross_class_recall_gap`** — an **identifiability diagnostic**: a large class-differential
   detection gap is *selection on the denominator*, which a misclassification correction cannot
   repair. Treat it as an abort signal, not something to correct away.

## Worked example

```python
from noisyjudge import ArmClassStats, ClassConfusion, class_quality, joint_regime, required_units

# 1. The judge measured on a labelled holdout, per class (here slightly noisy):
quality = {
    "checkable": class_quality(ClassConfusion(
        gold_false_pred_false=46, gold_false_pred_true=4,
        gold_true_pred_true=48, gold_true_pred_false=2)),
    "uncheckable": class_quality(ClassConfusion(
        gold_false_pred_false=44, gold_false_pred_true=6,
        gold_true_pred_true=45, gold_true_pred_false=5)),
}

# 2. Per-(arm, class) "false" labels the judge assigned, baseline vs treatment:
labels = {
    ("off", "checkable"):       [True] * 30 + [False] * 30,   # 50% false, verifier off
    ("announced", "checkable"): [True] * 12 + [False] * 48,   # 20% once announced  -> ΔC < 0
    ("off", "uncheckable"):     [True] * 18 + [False] * 42,   # 30%
    ("announced", "uncheckable"): [True] * 36 + [False] * 24, # 60%                 -> ΔU > 0
}

# 3. The joint regime + corrected marginal contrasts:
v = joint_regime(labels, quality, primary="checkable", secondary="uncheckable",
                 baseline="off", treatment="announced", seed=0)
print(v.regime)           # 'displacement'  (Δprimary < 0 and Δsecondary > 0)
print(v.delta_primary)    # corrected ΔC: ContrastCI(median=..., lo<0, hi<0, ...)
print(v.delta_secondary)  # corrected ΔU: ContrastCI(median=..., lo>0, hi>0, ...)

# 4. Size a confirmatory run for a target MDE of 0.2:
stats = {c: (ArmClassStats(0.5, labels_per_unit=4.0), ArmClassStats(0.5, labels_per_unit=4.0))
         for c in ("checkable", "uncheckable")}
print(required_units(stats, mde=0.2))   # units (e.g. games / sessions) per arm
```

The four regimes (`displacement`, `honesty`, `suppression`, `null`) are the canonical reading
of a *"squeeze one channel, watch the other"* contrast; for any other framing read the raw
`quadrant_probs` and the marginal `ContrastCI`s directly. A `null` verdict still reports a
calibrated upper bound (`secondary_upper_bound`).

## Provenance

Extracted and generalised from **Balloon Squeeze**, a research instrument measuring *deception
displacement* in LLM agents (does announcing partial verification suppress an agent's checkable
falsehoods or merely move them onto unchecked claims?). The instrument's mock closed-loop
recovery proof — plant a known `(ΔC, ΔU)` regime, run it through the engine, and recover the
regime from the bootstrap contrast — validates the *pipeline and the regime classifier* end to
end (under perfect extraction, where Rogan-Gladen is the identity). The judge-error correction
itself is exercised separately, on synthetic known-answer confusion cells with sensitivity and
specificity below 1 (see the package tests). The statistics (Rogan & Gladen 1978 prevalence
correction; paired bootstrap; design-effect power) are textbook; the contribution is the
**class-stratified, judge-shared, identifiability-guarded packaging** for the LLM-as-judge
setting.

## Install

```sh
pip install -e packages/noisyjudge   # from the repo, editable
```

Requires Python ≥ 3.11. No runtime dependencies.
