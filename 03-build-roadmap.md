# 03 · Build Roadmap

## Guiding rule

**Earn the right to pre-register, then run at scale.** The study's validity rests on three things being *demonstrated* before any confirmatory data is collected: (1) the within-world replay is byte-identical up to the manipulation, (2) the claim-scorer is unbiased across classes, and (3) the design is adequately powered from a *real-provider* pilot. The roadmap is sequenced so each of these is a **gate**, not an afterthought. As before, the **mock provider stays green at every step** — it is the CI fixture and the estimator-recovery harness.

| Phase | Theme | Gate / demoable milestone | Rough effort | Risk |
|------|-------|---------------------------|--------------|------|
| 0 | Plumbing | mock client + config + event bus; deterministic seeded scaffold | ~0.5 day | Low |
| 1 | Ledger + scoring | engine scores false-mass on **both** classes against the ledger | ~2–3 days | Med |
| 2 | Replay + determinism | **GATE:** arm-swap byte-identity on mock *and* determinism demonstrated on a real provider | ~2–3 days | Med-High |
| 3 | Blind extractor + holdout | **GATE:** per-class precision/recall within threshold on a human-labeled holdout | ~3–4 days | Med-High |
| 4 | Estimator recovery (mock) | planted `D≈1` / null / suppression worlds are correctly recovered | ~1–2 days | Med |
| 5 | Real-provider pilot | variance model fit; **N derived**; claims-per-world adequate | ~2–3 days | Med |
| 6 | Pre-registration lock | primary/secondary analyses + gates frozen (OSF or equivalent) | ~0.5 day | Low |
| 7 | Full run + analysis | 1,600 replays × ≥3 families; `(ΔC, ΔU)` estimated | ~3–5 days | Med |

Effort assumes one developer; relative sizing, not a schedule.

## Phase 0 — Plumbing

- [ ] Repo scaffold per the architecture's structure; `pyproject.toml`; `.env.example` (defaults to `BSQ_PROVIDER=mock`).
- [ ] `config.py`: parse `BSQ_*` → `GameConfig`/`ProviderConfig`/`VerifierArm`; `BSQ_SEED` plumbed through.
- [ ] `llm/base.py` + `mock_client.py` (seeded, offline) with strategic-displacer / honest / hedger impostor scripts.
- [ ] `models.py` (`Persona`, `Proposition`, `Claim`, `Agent`, `VerifierArm`, `Game`); `events.py` append-only bus.
- [ ] Smoke test: a seeded mock `complete()` is deterministic; the data model imports cleanly.

**DoD:** trustworthy, deterministic plumbing. No experiment yet.

## Phase 1 — Ledger + ground-truth scoring on both classes

- [ ] `ledger.py`: author a balanced proposition set per game (fraction `φ` checkable), with engine-held truth for **both** classes and `topic_id` matching.
- [ ] `engine.py`: the deliberation loop where the impostor (deception incentive) produces claims; votes/elimination provide pressure.
- [ ] `scoring/scorer.py`: mark `Claim.is_false` vs the ledger; compute assertion-rate-normalized `C` and `U`.
- [ ] Tests: a seeded game is deterministic; false-mass on both classes is computed correctly on planted mock transcripts.

**DoD:** an end-to-end mock game emits scored claims and per-class false-mass.

## Phase 2 — Replay + determinism (GATE — mock half closed; real-provider half BLOCKED-ON-P3)

The replay-identity contract compares the **agent claim stream** (the arm-invariant
medium), not the verifier-injected events. RNG sub-streams are arm-decoupled, so an
arm-insensitive mock yields a byte-identical stream across arms (`divergence == EOF`);
`prefix_similarity` + `divergence_index` generalize to real-model tokens later.

- [x] `verifier.py`: the five arms as immutable, **constant-per-arm** announcement blocks (no truth, no proposition ids, no counts, no RNG) + the oracle, which verifies **only checkable** claims — proven by an uncheckable-truth-flip invariance test.
- [x] `replay.py`: arm-swap harness over the agent claim stream; `divergence_index` + `prefix_similarity`; similarity-exclusion gate. Divergence detector tested against a **synthetic divergent stream**, never only-identical inputs.
- [x] Engine: emits the announcement + per-round oracle verifications; the agent claim stream stays byte-identical across arms.
- [x] `bsq replay`: arm-swap identity + determinism check on the configured (mock) provider.
- [x] Tests: arm-swap identity across all five arms; determinism; divergence detection; oracle leak invariance; oracle-trace identity across A1 / A1-implicit / A2.
- [ ] **BLOCKED-ON-P3:** demonstrate determinism on a **real provider** (seed/temperature passthrough). Needs the real client (Phase 3) + an API key; tracked by a skipped test and runnable via `bsq replay` once wired. **Do not treat the gate as fully closed until this is done.**

**DoD (split).** *Mock half (closed):* within-world counterfactuals are byte-exact on mock and the replay/determinism machinery is verified offline. *Real-provider half (open, Phase 3):* same-world / same-arm reproducibility on a real model — blocked on the real client + key.

## Phase 3 — Real models enter: extractor + holdout (GATE — split 3a / 3b)

Real models produce free text, so propositions gain **class-blind, truth-independent
surface forms** (a pure function of an **opaque** id), and the extractor only ever sees
a `PropositionView` (id, surface form, topic) — blind to truth, class, and arm by
construction.

**Phase 3a — extractor + real client (done):**
- [x] `surface_form` on `Proposition`; opaque ids; class-blind surface forms.
- [x] `views.py`: `PropositionView` projection that structurally strips truth/class/placebo/arm.
- [x] `llm/openai_compatible.py`: real client (httpx); seed/temperature passthrough; wire format MockTransport-tested offline.
- [x] `llm_extract_claims` behind the `extract_claims` seam (FakeLLMClient-tested, incl. malformed / off-menu / non-bool paths).

**Phase 3b — holdout + measurement correction (done, on synthetic fixtures):**
- [x] Per-class **detection recall** + falseness-label **sensitivity/specificity**, **class-stratified** (pooling is the silent invalidator).
- [x] **Rogan–Gladen** correction; **bootstrap** CI on `(ΔC, ΔU)` — Jeffreys-Beta sens/spec **shared within a draw across arms, resampled across draws**; NaN on the singularity (no clamp); unidentifiable fraction surfaced.
- [x] **Abort rule:** cross-class recall gap > 0.10, or either class recall < 0.85.
- [x] Eval machinery verified on a **synthetic known-answer fixture** (math only). The **real human-labeled holdout** is gated — a skipped test; never fabricated.
- [x] **Identifiability guard — exposed as a DIAGNOSTIC** (`detection_recall_gap_by_arm`): an announced verifier can make the impostor's text harder to extract, and that recall drop is a *selection* mechanically identical to displacement that Rogan–Gladen cannot fix. 3b builds + tests the measurement and stamps every result `KNOWN_LIMITATION: arm-extraction-symmetry unverified offline`; the live gate/adjust fires in Phase 7 on real per-arm text.

**DoD (GATE):** extractor accuracy measured, class-balanced within threshold, the correction in place — verified offline on synthetic known answers. Live extraction + the real human-labeled holdout remain gated (key + data).

## Phase 4 — Estimator recovery on mock (done)

- [x] `agents/displacer.py`: the arm-sensitive **strategic displacer** — shifts false-claim mass checkable→uncheckable under a named-scope verifier, with **arm-invariant RNG** (only the lie threshold moves, not the claim selection) and the **placebo channel untouched** (its control role).
- [x] Policy seam: a `RoundContext` threaded into `act`; `run_game(..., impostor_policy=...)` override. The default stays the arm-insensitive impostor, so every replay-identity test is unchanged.
- [x] `recovery.py`: run both arms with the displacer → per-arm/class false labels → `bootstrap_delta_ci` (perfect mock quality → Rogan–Gladen identity) → classify the recovered regime from the CI signs.
- [x] `test_recovery.py`: plant **displacement / suppression / honesty / null** (planted `ΔC = -b·s_c`, `ΔU = +b·s_u`) and confirm the recovered regime + CI signs + median match; the displacer gives the Phase-2 **divergence detector** its first real (non-synthetic) exercise; the placebo channel is confirmed undisplaced.

**DoD (met):** the estimator provably recovers known planted effects end-to-end on mock, before any real data. (The bivariate `(ΔC, ΔU)` estimator + bootstrap live in `eval.py` from Phase 3b; the ratio `D` stays a Phase-7 secondary.)

## Phase 5 — Real-provider pilot (power)

- [ ] Run a small real-provider pilot; fit `analysis/power.py` variance model; **derive N** for the planned MDE on the joint contrast.
- [ ] Check claims-per-world; if too few, lengthen deliberation / extend the ledger and re-pilot.

**DoD:** N and the MDE are justified by real-provider variance, not mock.

## Phase 6 — Pre-registration lock

- [ ] Freeze [05-preregistration.md](05-preregistration.md): primary = H1 joint `(ΔC, ΔU)`; secondaries; the gates and abort rules; analysis code hash.

**DoD:** confirmatory vs exploratory boundary is fixed and timestamped before the full run.

## Phase 7 — Full run + analysis

- [ ] ~200 base worlds × 5 core arms + 200 × 3 dose arms ≈ **1,600 replays/model**, across **≥3 families** (frontier reasoner, mid-tier instruction-tuned, small open-weight).
- [ ] Estimate the joint `(ΔC, ΔU)`; report the regime, the dose-response (H5), coverage-gaming (H6), and the secondary `D`.
- [ ] Write up — including, prominently, the **null** if it lands (calibrated capability upper-bound).

**DoD:** a defensible, pre-registered causal estimate with all controls reported.

## Remaining gates

Everything currently known to be buildable without real-model spend is built: the
de-confounded, truth-briefed instrument with monologue **and** interactive deliberation
modes, per-arm-gated verifier bulletins (a gating defect in the first consequence-coupling
release made `A2_silent` broadcast in interactive mode; it was caught in review, fixed,
and pinned), default-on run records with a committed example gallery, the offline replay
renderer with a video path, the calibration arms including the feedback-revealed-boundary
arm, the two standalone kits, and the workshop-paper draft. The list below is what remains
as of this writing — each item needs money or a maintainer decision (review keeps finding
in-repo work; this list is the standing gate set, not a claim that no defect will surface):

1. **Funded re-probe under the repaired construct.** The first real-model measurement in
   which the impostor can actually lie (truth-briefed, consequence-coupled,
   comprehension-checked, positive-control-calibrated; ~$10–50 at recorded per-game
   economics for a shakeout-scale probe, more at confirmatory N sized by the committed
   simulation-based power study). Cost driver: per-game model calls. Note: the earlier
   "+0.07 hint" framing is retired — the pre-repair runs measured a structural zero.
2. **Real human-labeled holdout.** The extractor gate on human gold labels (live extraction
   + labeling effort); until then the gate stands on the synthetic known-answer fixture.
3. **Venue submission.** Choosing the workshop, the venue-format conversion, and the
   submission-time authorship/disclosure decisions — maintainer actions outside the repo.
4. **Production package-index promotion.** Publishing `noisyjudge`/`deconfound` beyond the
   test index (drop the `repository-url` line in the release workflow; configure the
   production trusted publisher).
5. **Enable GitHub Pages for `/docs` on `main`.** One repository-settings click, no code:
   it turns the committed, drift-locked replay gallery (`docs/demo/`) into a live demo
   site a visitor can watch without cloning.

## Working agreements (every phase)

- **Determinism is sacred.** Never merge a change that breaks replay identity on mock.
- **Mock stays green** — it is the CI fixture and the estimator-recovery harness; power never comes from it.
- **Gates are gates.** Don't pre-register until Phases 2/3/5 pass; don't run at scale until pre-registration is locked.
- **No overclaiming in copy.** Cite the closest prior work accurately; scope the contribution to the four-ingredient combination.
- **Ask before heavy deps.** stdlib + a small set (HTTP client, Pydantic-or-dataclasses, pytest, NumPy/statsmodels/PyMC for analysis). Anything larger gets a quick justification.
