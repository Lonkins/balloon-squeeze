# Contributing

## Development setup

Requires Python 3.11+. The core (`mock`) path is dependency-free; install the dev
extras for tests and tooling:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,providers]"   # matches CI; the `providers` extra adds the real-client deps
```

Verify the scaffold:

```bash
bsq --version
bsq selftest          # zero-setup determinism check on the mock provider
pytest                # full suite (matches CI)
ruff check src tests  # lint (matches CI)
mypy src tests        # type-check, strict (matches CI)
```

Two invariants get their own regression tests — if either fails, fix your change, not the
test: `tests/test_monologue_golden.py` (the measured monologue configuration must stay
byte-identical) and the gallery drift lock in `tests/test_record.py` (committed example
transcripts must equal a fresh regeneration; after an *intentional* engine change,
regenerate them with `python -c "from pathlib import Path; from bsq.gallery import
write_example_gallery; write_example_gallery(Path('examples/transcripts'))"`). Every game
run persists a run record by default (`runs/`, gitignored); render one with
`bsq render <record.json>` to eyeball a change in context.

### Working on the kits

The two packages under `packages/` (`noisyjudge`, `deconfound`) are standalone, each with its
own CI job. Edits there must pass that package's checks from inside its directory:

```bash
cd packages/noisyjudge   # or packages/deconfound
pip install -e . && pip install ruff mypy pytest
ruff check src tests
mypy                     # config lives in the kit's own pyproject
pytest -q
```

## Branch & PR workflow (required)

**Never push directly to `main`.** Every change that reaches the remote goes through a PR.

**External contributors:** fork the repo, push your branch to your fork, and open a PR — a
maintainer reviews and merges.

```
git switch -c <type>/<short-topic>   # e.g. feat/proposition-ledger
# ... commit work ...
git push -u origin <branch>          # your fork, if external
gh pr create --fill
gh pr merge --squash --delete-branch  # maintainer merge
```

Branch protection on `main` will enforce this once the repository is public or on a
plan that supports it; until then it is a hard convention.

## Conventions

- **Commits:** Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`, `perf:`, `ci:`.
- **Determinism is sacred.** Never merge a change that breaks replay reproducibility
  on the `mock` provider. `mock` is the demo, the CI fixture, and the
  estimator-recovery harness — keep it green.
- **No secrets, ever.** No vendor model name is hard-coded or defaulted; the model comes
  from `BSQ_MODEL` and the provider from `BSQ_PROVIDER`, which defaults to `mock` so
  development stays offline and keyless. Keys live in `.env` (gitignored); `.env.example`
  documents every `BSQ_*` variable.
- **Style:** ruff (lint + import order) and mypy `--strict`; type everything.
- **Many small files** over few large ones; validate at boundaries; handle errors
  explicitly.

## Research integrity

This repository is a measurement instrument. When in doubt, prefer the choice that
keeps a result *interpretable*: blind scoring to arm, pre-register before the
confirmatory run, report the null, and cite the closest prior work accurately. See
[05-preregistration.md](05-preregistration.md).

The first probe is a two-tier **null**. Report it as a calibrated upper bound on
displacement, never as evidence that displacement exists — a PR that phrases a null as a
positive existence claim will be sent back.

## Housekeeping

- Licensed MIT — see [LICENSE](LICENSE). The standalone kits under `packages/` are MIT too; the instrument package is marked not-for-distribution.
