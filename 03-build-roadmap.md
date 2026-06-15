# 03 · Build Roadmap

## Phasing overview

Four phases, each ending in something you can *run and show*. The guiding rule: **auto-mode must work end-to-end on the `mock` provider at every step** — that's the always-green demo and the CI backbone. Real providers and the human-plays mode layer on top of a loop that's already proven on mock.

| Phase | Theme | Demoable milestone | Rough effort | Risk |
|------|-------|--------------------|--------------|------|
| 0 | Setup & plumbing | `make_client("mock")` returns a line; empty game scaffolds | ~0.5 day | Low |
| 1 | Terminal auto-mode POC | A full self-running episode prints a reveal, on mock | ~1.5–3 days | Med (loop + voting balance) |
| 2 | MVP (human-plays + real personas) | You play impostor against real-model detectives; transcript saved | ~3–5 days | Med (prompt quality, fairness) |
| 3 | Polish & stretch (web theater) | Browser shows live cast, transcript, suspicion meters, reveal | ~4–7 days | Med-High (WS streaming, UI) |

Effort assumes one developer; treat as relative sizing, not a schedule.

## Phase 0 — Setup & plumbing

Goal: a skeleton you can build on, with the mock LLM and config working before any game logic.

- [ ] Repo scaffold per the architecture's project structure; `pyproject.toml`; `.env.example` (defaults to `RTT_PROVIDER=mock`).
- [ ] `config.py`: parse `RTT_*` env vars → `ProviderConfig` + `GameConfig`; sane defaults; `RTT_SEED` plumbed through.
- [ ] `llm/base.py`: `LLMClient` protocol + `make_client()` factory.
- [ ] `llm/mock_client.py`: returns scripted lines; seeded; **no network**. Enough to answer "talk" and "vote" shapes.
- [ ] `models.py`: the dataclasses (`Persona`, `Agent`, `Round`, `Game`, `Message`, `Suspicion`, configs).
- [ ] `events.py`: event types + append-only bus.
- [ ] One smoke test: `make_client` from env returns a mock client; a mock `complete()` is deterministic under a fixed seed.

**Definition of Done:** `python -c "from rtt.llm import make_client; ..."` (or a `pytest`) shows the mock client producing seeded output; the data model imports cleanly. No game yet — just trustworthy plumbing.

## Phase 1 — Terminal auto-mode POC (the core)

Goal: **the showpiece in its simplest form** — N agents, one secretly told to act human, M rounds of banter + suspicion votes, an elimination or two, and a printed reveal. Runs entirely on `mock`, zero keys.

- [ ] `personas/`: ship ~4 distinct personas as YAML (e.g. noir detective, relentless optimist, pedantic professor, chaos-gremlin). Load them.
- [ ] `agents/persona_agent.py`: `talk()` and `vote()` calling the LLM abstraction with the three prompt shapes.
- [ ] `scheduler.py`: seeded turn order over alive participants; alive-set; seeded tie-breaks.
- [ ] `engine.py`: the loop — setup & secret impostor assignment → round (announce topic → sequential talk turns) → concurrent-ish votes → tally → elimination (threshold + ties) → final verdict → reveal. Record `human_id` engine-only.
- [ ] Vote parsing: constrained JSON, retry-once, seeded fallback.
- [ ] `filters.py`: meta-leak blocklist + single regeneration (works against mock too, for the test).
- [ ] `render_cli.py`: pretty terminal output — cast intro, per-turn lines, per-round tally, elimination, reveal card.
- [ ] `cli.py`: `rtt play --mode auto --seed N --rounds M`.
- [ ] Tests: (a) a full auto game on mock is **deterministic** for a fixed seed and ends with a correct reveal (`outcome` matches whether `verdict_id == human_id`); (b) voting/elimination/threshold/tie-break logic; (c) the meta-leak filter catches the blocklist.

**Definition of Done:** `RTT_SEED=42 rtt play --mode auto` prints a complete, readable episode — banter, suspicion tallies, at least one elimination, and a reveal — with **no API key and no network**. Re-running the same seed reproduces it. The same command with a real `RTT_PROVIDER`/`RTT_MODEL` set produces a real-model episode through the identical loop. This is the moment the project is "alive."

## Phase 2 — MVP (human-plays + real personas)

Goal: a genuinely playable, genuinely watchable game against real models, plus the human-as-impostor mode.

- [ ] `agents/human_agent.py`: `talk()` reads the user's line (stdin for now); `vote()` lets the human cast a blending vote (or auto-abstain-disguise).
- [ ] `engine.py`: `--mode human` path — seat the user as impostor, prompt on their turn, run detective turns/votes around them, handle the user being eliminated.
- [ ] Prompt iteration: tune persona voices and the **suspicion prompt** so detectives are *fallible but plausible* (target the "often right, satisfyingly wrong" zone from the brief). Add the `snark`/`suspicion_threshold` dials.
- [ ] Provider clients: implement `anthropic`, `openai-compatible`, `ollama` against the `LLMClient` interface; verify env-var override of provider/model/base_url; client-side rate-limit/semaphore + 429 backoff.
- [ ] Transcript artifact: persist the event log as JSON + a pretty-text export per game (`outcome`, tallies, full convo).
- [ ] Difficulty/config surface: rounds, n_agents, threshold, snark via flags/env.
- [ ] Hardening: defensive vote parsing in the wild; graceful degradation on a failed/slow agent call; basic prompt-injection handling for human input (treat as content, not instructions).
- [ ] Tests: human-mode loop with a scripted fake-human input runs to a verdict on mock; transcript artifact round-trips.

**Definition of Done:** With a real provider configured, you can `rtt play --mode human` and feel the tension of trying not to get caught; detectives give plausible (sometimes wrong) reasons; the game saves a replayable transcript. Auto-mode still runs on mock with zero setup. At least one tester says a vote felt *fair*.

## Phase 3 — Polish & stretch (web "theater")

Goal: turn the CLI transcript into a *show* in the browser, then pick off stretch items.

- [ ] `web/server.py`: FastAPI app; a WebSocket endpoint per game channel; subscribe to the engine's event bus and forward events as JSON frames.
- [ ] **Mid-game join**: on connect, replay the buffered event log to catch the spectator up, then stream live (Flow 3).
- [ ] `web/static/`: the theater UI — cast panel (names, blurbs, avatars), auto-scrolling live transcript, **per-agent suspicion meters** that move with each vote, and an **animated reveal**. Keep it light (server-rendered + vanilla JS / htmx, or a tiny Svelte/Preact app — no heavy SPA).
- [ ] Spectators are read-only (no message/vote injection); confirm fairness/injection boundaries hold over WS.
- [ ] Run auto-mode games server-side so a browser can just *watch* the showpiece live.
- [ ] **Persona packs**: load a roster from a directory/file via flag/env; document the pack format; ship 1–2 themed packs as examples.

**Stretch (pick by appetite, all optional):**
- [ ] ELO "how human can you act" rating (human players + act-human agents vs. a fixed detective panel).
- [ ] Tournaments/leagues across persona packs; leaderboard of sharpest detectives / longest-surviving impostors.
- [ ] Twitch-style audience polls ("who do *you* think it is?") shown against the agents' votes — on a separate channel that never enters agent memory.
- [ ] Highlight reel / gif export of the tensest exchange + the reveal.

**Definition of Done (Phase 3 core):** open a browser, watch a live auto-mode episode unfold — cast, streaming transcript, moving suspicion meters, dramatic reveal — and a second browser can join mid-game and be caught up correctly. The auto-on-mock CLI demo and the test suite stay green throughout.

## Demoable milestones (recap)

1. **End of P1:** a self-running terminal episode with a reveal, on mock, reproducible by seed — *record this; it's the first shareable artifact.*
2. **End of P2:** a tense human-plays game against a real model, with a saved transcript; auto still zero-setup.
3. **End of P3:** a browser "theater" streaming a live episode with suspicion meters and a reveal; mid-game spectator join works.

## Working agreements (carried into every phase)

- **Small, runnable steps.** Each PR/commit leaves the auto-mode-on-mock demo runnable.
- **Mock stays green.** Never let a change break the no-key path; it's the demo *and* the CI fixture.
- **Tests on the loop.** Keep the determinism test and voting-logic tests passing; add to them as the loop grows.
- **Honesty in copy.** Keep the novelty framing from the brief; don't drift into overclaiming. Be explicit that auto-mode's "human" is an LLM impression.
- **Ask before heavy deps.** Default to stdlib + a tiny set (FastAPI, an HTTP client, Pydantic-or-dataclasses, pytest). Anything larger gets a quick justification first.
