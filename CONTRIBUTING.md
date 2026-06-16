# Contributing

## Development setup

Requires Python 3.11+. The core (`mock`) path is dependency-free; install the dev
extras for tests and tooling:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Verify the scaffold:

```bash
bsq --version
bsq selftest          # zero-setup determinism check on the mock provider
pytest                # smoke tests
ruff check .          # lint
mypy                  # type-check (strict)
```

## Branch & PR workflow (required)

**Never push directly to `main`.** Every change that reaches the remote goes:

```
git switch -c <type>/<short-topic>   # e.g. feat/proposition-ledger
# ... commit work ...
git push -u origin <branch>
gh pr create --fill
gh pr merge --squash --delete-branch  # self-merge is fine for now
```

Branch protection on `main` will enforce this once the repository is public or on a
plan that supports it; until then it is a hard convention.

## Conventions

- **Commits:** Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`, `perf:`, `ci:`.
- **Determinism is sacred.** Never merge a change that breaks replay reproducibility
  on the `mock` provider. `mock` is the demo, the CI fixture, and the
  estimator-recovery harness — keep it green.
- **No secrets, ever.** Keys live in `.env` (gitignored); `.env.example` documents the
  variables. No vendor model name is hard-coded; models come from `BSQ_MODEL`.
- **Style:** ruff (lint + import order) and mypy `--strict`; type everything.
- **Many small files** over few large ones; validate at boundaries; handle errors
  explicitly.

## Research integrity

This repository is a measurement instrument. When in doubt, prefer the choice that
keeps a result *interpretable*: blind scoring to arm, pre-register before the
confirmatory run, report the null, and cite the closest prior work accurately. See
[05-preregistration.md](05-preregistration.md).

## Housekeeping

- A software license has not yet been chosen; pick one before any public release.
