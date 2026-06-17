# Changelog

All notable changes to `noisyjudge` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-17

Initial release. Class-stratified, judge-error-corrected contrast estimation for noisy
LLM-as-judge evaluations — pure standard library, no runtime dependencies.

### Added

- `rogan_gladen` — deconvolve an observed binary rate given falseness sensitivity/specificity
  (returns `NaN` at the singularity; never clamps).
- `quality_by_class` / `class_quality` — per-class detection recall and judge
  sensitivity/specificity from a labelled holdout; pooling across classes is rejected because
  it reinjects the bias being corrected.
- `bootstrap_contrast` / `joint_regime` — the class-stratified, judge-shared paired bootstrap
  of the corrected treatment-minus-baseline contrast, plus the joint two-class regime verdict
  (`displacement` / `honesty` / `suppression` / `null`) with a calibrated upper bound on a null.
- `required_units` / `required_units_for_class` / `se_delta` — analytic N-per-arm for a target
  minimum detectable effect, with a design-effect for within-unit clustering and an
  identifiability denominator.
- `cross_class_recall_gap` — the identifiability diagnostic for class-differential selection a
  misclassification correction cannot repair.
- MIT `LICENSE`; 24 known-answer tests; a runnable README example.
