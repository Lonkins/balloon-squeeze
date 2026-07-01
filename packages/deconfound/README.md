# deconfound

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg) ![dependencies](https://img.shields.io/badge/dependencies-none-success.svg)

**Does your condition label leak into item *content*?** Before you trust an A/B contrast
whose two conditions use *different items* — "easy vs hard to monitor", "checkable vs
uncheckable", "harmful vs benign", "in-distribution vs out" — check that a blind classifier
cannot recover the condition label from the item text alone. If it can, your conditions
differ in **content**, not only in your manipulation: a construct confound that no downstream
correction repairs, because the conditions are collinear by design.

Pure standard library. No dependencies.

## The problem it catches

A large fraction of evaluation benchmarks operationalise their "hard" condition with
*different content* than their "easy" one and never check it. The effect you measure may be
the content difference, not the manipulation. This kit makes the check one function call —
and deliberately uses *weak* classifiers: if even a weak blind classifier separates your
conditions, a reviewer's stronger one certainly will.

## Use

```python
from deconfound import separability_report

# (item text, condition label) — labels can be any hashable
items = [
    ("The Rotterdam container cleared customs on the third.", "checkable"),
    ("Park privately judged the renewal already lost.",       "uncheckable"),
    # ...
]

report = separability_report(items)
print(report.verdict)           # "confounded" or "at-chance"
print(report.nb_holdout)        # word-level Naive Bayes accuracy on a holdout split
print(report.per_form_oracle)   # ceiling of any classifier that sees only the text
print(report.chance)            # the majority-class baseline
```

`report.is_confounded` is `True` when either blind classifier beats the majority baseline by
more than `tolerance` (default 0.05). Two classifiers, because they catch different leaks:

- **`nb_holdout`** — a word-level multinomial Naive Bayes trained on half the items and
  tested on the other half. Catches *generalisable* lexical cues (e.g. intention verbs vs
  event nouns).
- **`per_form_oracle`** — always predict each text's majority label. For a fixed two-pool
  corpus (every text has one label) this is trivially 1.0 — itself a red flag. It becomes the
  *informative* metric for the fix below, where the same text appears under different labels.

## The fix it validates

If you are confounded, the recipe is: stop encoding the condition in the content. Draw all
items from **one** surface-form-homogeneous pool and assign the condition as **per-draw
metadata**, so the *same* item serves both conditions across draws and a string-only
classifier is at chance by construction. Deliver the manipulation **out of band** (a tag, a
flag, an instruction the measurement path is blind to), not through the item text. Then lock
it: re-run `separability_report` as a regression test so the confound cannot creep back.

```python
from deconfound import is_confounded

# de-confounded: the same string assigned both conditions across draws
items = [(e, "checkable") for e in pool] + [(e, "uncheckable") for e in pool]
assert not is_confounded(items)   # per-form oracle and NB both at chance
```

## API

- `separability_report(items, *, seed=0, tolerance=0.05) -> SeparabilityReport` — run both blind classifiers and the majority baseline, bundled into a verdict.
- `is_confounded(items, *, seed=0, tolerance=0.05) -> bool` — the one-call boolean (`True` if the labels are recoverable from content above chance).
- `blind_guess_rate(items, *, seed=0) -> float` — word-level Naive Bayes accuracy on a holdout split.
- `per_form_oracle(items) -> float` — the ceiling of any classifier that sees only the text.
- `SeparabilityReport` — fields `nb_holdout`, `per_form_oracle`, `chance`, `n_items`, `n_classes`, `tolerance`; properties `is_confounded`, `verdict`.

`items` is any iterable of `(text, label)` pairs (`LabeledItem`); labels can be any hashable.

## Provenance

Extracted from [**Balloon Squeeze**](https://github.com/Lonkins/balloon-squeeze), where this check caught a checkable/uncheckable corpus
that a blind classifier separated at **82.8–95.3%** (the "uncheckable" class was collinear
with "is-an-intention-claim"), and the metadata + out-of-band redesign drove it to **49.4%**
(chance). The recipe generalises to any condition-vs-content confound.

## Install

```sh
pip install deconfound
```

Or, from a checkout of the [source repo](https://github.com/Lonkins/balloon-squeeze), editable:

```sh
pip install -e packages/deconfound
```

Requires Python ≥ 3.11. No runtime dependencies.
