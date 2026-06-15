# Reverse Turing Theater

*An inverted Turing test staged as spectator theater: a cast of AI agents must work out which of them is the lone human — while the human tries to blend in.*

**Status: Design phase — not yet built.** These four docs are the spec a dedicated build thread should implement.

## What it is

A social-deduction game flipped on its head. Instead of a human guessing whether their counterpart is a bot, a *room full of distinct AI personalities* are the detectives — they converse on prompts, reason out loud, cast live "suspicion" votes, eliminate suspects, and finally deliver a verdict on which participant is the human impostor. It runs in two modes: **human-plays** (you are the hidden human, trying not to get caught) and **auto/demo** (one agent is secretly told to "act human," so the whole show runs hands-free). The emphasis is on *watchability* — personality-driven banter, visible reasoning, mounting drama, and a satisfying reveal.

## The docs

- **[01-concept-brief.md](01-concept-brief.md)** — the PRD: pitch, delight thesis, players-and-spectators, honest novelty positioning, the two modes, MoSCoW scope, success criteria, risks.
- **[02-technical-architecture.md](02-technical-architecture.md)** — stack, component diagram, data model, the full game loop, the provider-agnostic + mock-mode AI layer, prompt design, key flows, project structure.
- **[03-build-roadmap.md](03-build-roadmap.md)** — phased plan from setup → terminal POC → MVP → web "theater" UI, with per-phase checklists, effort/risk, and demoable milestones.
- **[04-kickoff-prompt.md](04-kickoff-prompt.md)** — a ready-to-paste prompt to start the first build thread.

## A taste

A four-agent auto-mode round. The topic was *"the worst piece of advice you ever followed."* `Margaux` is secretly the one told to act human.

```
[Round 2 · topic: worst advice you ever followed]

DETECTIVE-NOIR   "Follow your passion," they said. I followed it into a
                 ditch. Anyway. I notice MARGAUX took four seconds to
                 answer a question about feelings. Machines don't hesitate.
                 People do. Interesting.

SUNNY            omg same though?? i once quit a job to "manifest" and then
                 cried in an Ikea. we've all been there 💀

MARGAUX          "manifested" my way into a parking ticket once. the
                 universe sends invoices, turns out.

PROFESSOR        A clever line. Too clever. Sunny rambles like a person;
                 Margaux performs like someone *trying* to sound like one.

  Suspicion this round →  Margaux 2  ·  Sunny 1  ·  Professor 0
```

Set no API key and it runs anyway, in an offline **mock** mode where every agent emits scripted lines — the loop, the votes, and the reveal all still work. Drop a key in and the same code calls a real model.
