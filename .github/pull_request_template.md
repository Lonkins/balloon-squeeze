## Summary

<!-- What does this PR change, and why? Link any relevant doc or issue. -->

## Checklist

- [ ] `ruff check`, `mypy --strict`, and `pytest` pass locally (plus each edited kit's own checks under `packages/`)
- [ ] Determinism preserved on the `mock` provider — no change breaks replay reproducibility
- [ ] No secrets committed, and no vendor or model-tier names added to tracked files
- [ ] Results reported honestly — a null stays a calibrated upper bound, never a positive existence claim
- [ ] Docs and tests updated as needed
