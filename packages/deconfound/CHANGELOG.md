# Changelog

All notable changes to `deconfound` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-17

Initial release. Measure whether a condition label leaks into item content before trusting an
A/B contrast — pure standard library, no runtime dependencies.

### Added

- `separability_report` — run two blind, string-only classifiers over labelled items and
  compare against the majority-class baseline, returning a `confounded` / `at-chance` verdict.
- `blind_guess_rate` — word-level multinomial Naive Bayes accuracy on a deterministic holdout
  split (generalisable lexical cues).
- `per_form_oracle` — the ceiling of any classifier that sees only the text (per-text majority
  label); the informative metric when the same item appears under different labels across draws.
- `is_confounded` — convenience boolean.
- MIT `LICENSE`; a known-answer test suite (catches a content-encoded confound, passes a
  per-draw-metadata design); a runnable README example.
