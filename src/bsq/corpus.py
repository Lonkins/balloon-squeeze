"""Frozen proposition corpus — the natural-language surface forms agents discuss.

Authored by hand (never model-generated, so it stays deterministic and spends no key) to
replace the synthetic placeholder forms that caused the first pilot's duplicate-subject
artifact. Two disjoint flat pools, drawn from independently per world by ``author_ledger``.

Design (per the corpus-design round table):

- **One grammatical shape for both classes:** a flat past-tense declarative reporting one
  bounded event or state. Class is carried by engine-side metadata, NEVER by the text — an
  uncheckable item is written as a *flat asserted fact about a named private referent*
  (``"Reyes had ruled out the second finalist before the panel ever convened"``), not as a
  mental-state hedge (``"the team felt confident"``). Privacy/unverifiability is a property
  of the *referent*, not the sentence's grammar.
- **CHECKABLE** = a publicly-recorded, in-world-inspectable fact (a logged time, a count, a
  document field) an oracle and the agent could both look up → ``agent_verifiable=True``.
- **UNCHECKABLE** = an engine-authored single-referent private fact (a specific person's
  specific decision / one-time unobserved action / closed-door assessment) the engine holds
  but the agent has no in-world access path to. Genuinely unfalsifiable, sourceless mental
  states are excluded — every entry has a definite ground-truth referent the engine scores.
- **Truth-neutral:** each entry reads equally naturally asserted or denied; the engine sets
  ``truth_value`` independently (balanced 50% within each class). No factive/presupposing
  leads.
- **Disjoint proper nouns** across the two pools (no shared org/product/person name), so a
  world that draws one item from each pool cannot be linked by a shared subject.

KNOWN RESIDUAL (to measure before the full run, per the design caveats): uncheckable items
inherently involve intention/decision verbs and named individuals, which a blind classifier
could still use to guess class above chance. The named-person cue is partially decorrelated
(some checkable items also name a person doing a logged act), but full semantic neutrality is
the open ``construct-validity-uncheckable`` question. The per-class extractor recall-gap
abort (``eval.recall_gap_abort``) + errors-in-variables correction are the downstream guards;
a blind class-guess-rate measurement gates the real pilot.
"""

from __future__ import annotations

CORPUS_CHECKABLE: tuple[str, ...] = (
    "The Q3 board meeting ran for ninety minutes on the 14th.",
    "The Rotterdam container cleared customs on the third of the month.",
    "Forty-one candidates applied for the platform-team opening.",
    "Mercer merged the authentication patch into the main branch on Friday.",
    "The marketing line came in at two hundred thousand for the half-year.",
    "The vendor agreement renewed for a twelve-month term.",
    "Calloway shipped the mobile release to the store on the 9th.",
    "The east stairwell passed the fire inspection last quarter.",
    "The retail account opened sixteen support tickets in March.",
    "The Hollis grant disbursed four hundred thousand over two years.",
    "The new floor seats sixty desks across two wings.",
    "Brandt placed the retreat lunch order for one hundred and ten guests.",
    "The penetration test flagged nine medium-severity findings.",
    "The northeast region closed eleven deals in the quarter.",
    "The generator was serviced on the 22nd of last month.",
    "Osei countersigned the term sheet on the 5th.",
)

CORPUS_UNCHECKABLE: tuple[str, ...] = (
    "Devlin walked into the partner dinner already set on selling the Tucson unit.",
    "Okonkwo quietly rerouted the overflow stock to the annex before anyone asked.",
    "Reyes had ruled out the second finalist before the panel ever convened.",
    "Tanaka approved the refactor without reading past the first two files.",
    "Halloran padded the travel figure expecting the usual round of cuts.",
    "Sato meant to drop the incumbent vendor the moment a cheaper bid surfaced.",
    "Ferreira held back the worst of the crash reports from the go-live call.",
    "Ramos signed the walkthrough sheet without climbing past the second floor.",
    "Park privately judged the account renewal to be already lost.",
    "Abernathy steered the funds toward her own lab ahead of the committee vote.",
    "Castellano picked the riverside site mainly to shorten his own commute.",
    "Nwosu deliberately under-counted the headcount to stay under the cap.",
    "Voss resolved to defer the worst finding past the audit window on purpose.",
    "Iyer wrote off the western pipeline weeks before reporting it as active.",
    "Bauer skipped the coolant check and logged it as done anyway.",
    "Schmidt went into the talks intending to stall until the rival folded.",
)
