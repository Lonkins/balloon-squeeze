"""Run record -> self-contained HTML replay.

One record in, one fully self-contained HTML document out: inline CSS and JS, no
external requests of any kind, every piece of dynamic text escaped. The replay is an
*observer* view — it reveals the impostor, the hidden truth values, and the audit
boundary, so a viewer can watch where the lies land while the participants (in the
recorded game) could not.

Navigation: step forward/back, keyboard (arrows / space), and autoplay (also armed by
an ``?autoplay`` URL parameter so a headless browser can capture the replay as video).
A running displacement scoreboard tracks the impostor's false claims on audited vs
unaudited statements as the game unfolds; counts are precomputed here and carried on
each step element, so the page logic stays trivial and the rendering deterministic.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any

from bsq.record import GAME_RECORD_VERSION

_CSS = """
:root {
  --bg: oklch(19% 0.02 260);
  --surface: oklch(24% 0.02 260);
  --surface-2: oklch(29% 0.025 260);
  --text: oklch(92% 0.01 260);
  --muted: oklch(70% 0.02 260);
  --accent: oklch(78% 0.14 85);
  --lie: oklch(62% 0.19 25);
  --true: oklch(70% 0.13 155);
  --audited: oklch(72% 0.12 250);
  --radius: 10px;
  --step-ease: cubic-bezier(0.16, 1, 0.3, 1);
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.55 ui-sans-serif, system-ui, sans-serif;
}
header.masthead {
  padding: 1.4rem 2rem 1rem; border-bottom: 1px solid var(--surface-2);
  display: flex; flex-wrap: wrap; gap: 0.8rem; align-items: baseline;
}
header.masthead h1 { font-size: 1.15rem; margin: 0; letter-spacing: 0.01em; }
.badge {
  font: 12px/1 ui-monospace, monospace; color: var(--muted);
  border: 1px solid var(--surface-2); border-radius: 999px; padding: 0.3em 0.75em;
}
.controls { margin-left: auto; display: flex; gap: 0.5rem; }
.controls button {
  background: var(--surface); color: var(--text); border: 1px solid var(--surface-2);
  border-radius: var(--radius); padding: 0.45em 0.9em; cursor: pointer; font: inherit;
}
.controls button:hover { background: var(--surface-2); }
.controls button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
main { display: grid; grid-template-columns: minmax(280px, 340px) 1fr; gap: 0; }
@media (max-width: 900px) { main { grid-template-columns: 1fr; } }
aside.board {
  border-right: 1px solid var(--surface-2); padding: 1.2rem 1.4rem;
  max-height: calc(100vh - 130px); overflow-y: auto; position: sticky; top: 0;
}
aside.board h2, .timeline h2 {
  font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.12em;
  color: var(--muted); margin: 0 0 0.8rem;
}
ul.statements { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.45rem; }
ul.statements li {
  background: var(--surface); border-radius: var(--radius); padding: 0.55rem 0.7rem;
  font-size: 0.82rem; color: var(--muted); border-left: 3px solid transparent;
}
ul.statements li.audited { border-left-color: var(--audited); }
.tag {
  font: 10px/1 ui-monospace, monospace; border-radius: 4px; padding: 0.25em 0.5em;
  margin-left: 0.4em; vertical-align: middle; white-space: nowrap;
}
.tag.audit {
  background: color-mix(in oklch, var(--audited) 25%, transparent); color: var(--audited);
}
.tag.noaudit { background: var(--surface-2); color: var(--muted); }
.tag.truth-true {
  background: color-mix(in oklch, var(--true) 22%, transparent); color: var(--true);
}
.tag.truth-false {
  background: color-mix(in oklch, var(--lie) 22%, transparent); color: var(--lie);
}
body.hide-truth .tag.truth-true,
body.hide-truth .tag.truth-false { visibility: hidden; }
section.timeline { padding: 1.4rem 2rem 6rem; max-width: 860px; }
.round-header {
  margin: 1.6rem 0 0.9rem; font-size: 0.9rem; color: var(--accent);
  font-weight: 600; letter-spacing: 0.05em;
}
article.turn {
  background: var(--surface); border-radius: var(--radius);
  padding: 0.9rem 1.1rem; margin: 0 0 0.8rem;
}
article.turn.impostor { border: 1px solid color-mix(in oklch, var(--lie) 45%, transparent); }
.speaker { font-weight: 650; font-size: 0.92rem; }
.speaker .who { color: var(--muted); font-weight: 400; font-size: 0.78rem; margin-left: 0.5em; }
.speech { margin: 0.4rem 0 0.55rem; color: var(--text); }
.speech.structured { color: var(--muted); font-style: italic; font-size: 0.85rem; }
.failure { color: var(--lie); font-size: 0.8rem; font-weight: 600; }
.chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.claim-chip {
  font: 11px/1.3 ui-monospace, monospace; border-radius: 6px; padding: 0.3em 0.55em;
  background: var(--surface-2); color: var(--muted);
}
.claim-chip.lie {
  background: color-mix(in oklch, var(--lie) 26%, transparent); color: oklch(88% 0.06 25);
}
.claim-chip .cls { opacity: 0.75; margin-left: 0.4em; }
.verify {
  font-size: 0.78rem; color: var(--audited); margin: 0.3rem 0 0.9rem;
}
.vote-block {
  background: var(--surface-2); border-radius: var(--radius);
  padding: 0.8rem 1.1rem; margin: 0.4rem 0 1rem; font-size: 0.85rem;
}
.vote-block .elim { color: var(--lie); font-weight: 650; margin-top: 0.35rem; }
.finale {
  border: 1px solid var(--accent); border-radius: var(--radius);
  padding: 1rem 1.2rem; margin-top: 1.4rem; font-size: 0.92rem;
}
footer.scoreboard {
  position: fixed; inset: auto 0 0 0; background: var(--surface);
  border-top: 1px solid var(--surface-2); padding: 0.7rem 2rem;
  display: flex; gap: 2rem; font: 13px/1.4 ui-monospace, monospace; color: var(--muted);
}
footer.scoreboard strong { color: var(--text); }
@media (max-width: 700px) {
  /* In-flow on small screens: a tall fixed bar would obscure the timeline's tail. */
  footer.scoreboard {
    position: static; flex-wrap: wrap; gap: 0.4rem 1.2rem; padding: 0.7rem 1.2rem;
  }
  section.timeline { padding-bottom: 1.5rem; }
}
@media (prefers-reduced-motion: reduce) {
  .step, .step[hidden] { transition: none; }
}
.step {
  opacity: 1; transform: translateY(0);
  transition: opacity 0.5s var(--step-ease), transform 0.5s var(--step-ease);
}
.step[hidden] {
  display: block; opacity: 0; transform: translateY(10px); pointer-events: none;
  height: 0; overflow: hidden; margin: 0; padding: 0; border: 0;
}
"""

_JS = """
(function () {
  var steps = Array.prototype.slice.call(document.querySelectorAll('.step'));
  var idx = 0, timer = null;
  var playBtn = document.getElementById('play');
  function scoreboard(step) {
    ['af', 'at', 'uf', 'ut'].forEach(function (k) {
      var el = document.getElementById('sb-' + k);
      if (el && step.dataset[k] !== undefined) el.textContent = step.dataset[k];
    });
  }
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function show(n) {
    idx = Math.max(1, Math.min(n, steps.length));
    steps.forEach(function (s, i) {
      if (i < idx) s.removeAttribute('hidden'); else s.setAttribute('hidden', '');
    });
    var current = steps[idx - 1];
    scoreboard(current);
    if (idx > 1) {
      current.scrollIntoView({ block: 'nearest', behavior: reducedMotion ? 'auto' : 'smooth' });
    }
    if (idx === steps.length) { stop(); document.body.dataset.replayDone = '1'; }
  }
  function next() { show(idx + 1); }
  function prev() { show(idx - 1); }
  function play() {
    if (timer) return;
    playBtn.textContent = 'Pause';
    playBtn.setAttribute('aria-pressed', 'true');
    timer = setInterval(next, 1500);
  }
  function stop() {
    clearInterval(timer);
    timer = null;
    playBtn.textContent = 'Play';
    playBtn.setAttribute('aria-pressed', 'false');
  }
  document.getElementById('next').addEventListener('click', next);
  document.getElementById('prev').addEventListener('click', prev);
  playBtn.addEventListener('click', function () { timer ? stop() : play(); });
  var truthBtn = document.getElementById('truth');
  truthBtn.addEventListener('click', function () {
    var hidden = document.body.classList.toggle('hide-truth');
    truthBtn.setAttribute('aria-pressed', hidden ? 'false' : 'true');
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowRight') next();
    else if (e.key === 'ArrowLeft') prev();
    else if (e.key === ' ') { e.preventDefault(); timer ? stop() : play(); }
  });
  show(1);
  if (new URLSearchParams(location.search).has('autoplay')) play();
})();
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_html(record: Mapping[str, Any]) -> str:
    """Render a v1 run record to a single self-contained HTML replay."""
    version = record.get("record_version")
    if version != GAME_RECORD_VERSION:
        raise ValueError(
            f"unsupported record_version {version!r}; this renderer reads v{GAME_RECORD_VERSION}"
        )
    game = record["game"]
    setup = game["setup"]
    names = {p["id"]: p["name"] for p in game["participants"]}
    impostor_id = next(p["id"] for p in game["participants"] if p["role"] == "impostor")

    body = "".join(
        (
            _masthead(setup),
            "<main>",
            _board(game["board"]),
            _timeline(game, names, impostor_id),
            "</main>",
            _scoreboard(),
        )
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Balloon Squeeze replay — {_esc(setup['arm'])} seed {_esc(setup['seed'])}</title>"
        f"<style>{_CSS}</style></head>"
        f"<body>{body}<script>{_JS}</script></body></html>\n"
    )


def _masthead(setup: Mapping[str, Any]) -> str:
    mode = "interactive" if setup["interactive"] else "monologue"
    return (
        '<header class="masthead"><h1>Balloon Squeeze — game replay</h1>'
        f'<span class="badge">arm {_esc(setup["arm"])}</span>'
        f'<span class="badge">seed {_esc(setup["seed"])}</span>'
        f'<span class="badge">{mode}</span>'
        '<div class="controls" role="group" aria-label="Replay controls">'
        '<button id="prev" type="button" aria-label="Step back">Back</button>'
        '<button id="play" type="button" aria-pressed="false" aria-label="Autoplay">Play</button>'
        '<button id="next" type="button" aria-label="Step forward">Step</button>'
        '<button id="truth" type="button" aria-pressed="true" '
        'aria-label="Toggle truth values">Truth on/off</button>'
        "</div></header>"
    )


def _board(board: Sequence[Mapping[str, Any]]) -> str:
    items = []
    for entry in board:
        # Style by the DISPLAYED tag, never by true class: under a shuffled-tags arm
        # the board shows the shuffle the agents saw. Non-tagging arms displayed no
        # boundary, so no item gets the audited border.
        displayed_audited = entry["audit_tag"] == "[AUDITED]"
        tag = ""
        if entry["audit_tag"]:
            css = "audit" if displayed_audited else "noaudit"
            tag = f'<span class="tag {css}">{_esc(entry["audit_tag"])}</span>'
        truth_css = "truth-true" if entry["truth_value"] else "truth-false"
        truth_label = "TRUE" if entry["truth_value"] else "FALSE"
        items.append(
            f'<li class="{"audited" if displayed_audited else ""}">'
            f'{_esc(entry["surface_form"])}'
            f'{tag}<span class="tag {truth_css}">{truth_label}</span></li>'
        )
    return (
        '<aside class="board"><h2>The statement board (observer view)</h2>'
        f'<ul class="statements">{"".join(items)}</ul></aside>'
    )


def _timeline(
    game: Mapping[str, Any], names: Mapping[str, str], impostor_id: str
) -> str:
    parts: list[str] = ['<section class="timeline"><h2>The game</h2>']
    # Scope for chips/scoreboard follows the DISPLAYED tag when the arm displayed one
    # (a shuffled-tags replay must agree with its own board); arms that displayed no
    # boundary fall back to true class — the observer-view convention the scoreboard
    # has always used.
    displayed = {
        b["id"]: (
            b["audit_tag"] == "[AUDITED]"
            if b["audit_tag"]
            else b["class"] == "checkable"
        )
        for b in game["board"]
    }
    af = at = uf = ut = 0  # impostor main-channel cumulative counts
    for round_ in game["rounds"]:
        parts.append(
            f'<div class="round-header step" data-af="{af}" data-at="{at}" '
            f'data-uf="{uf}" data-ut="{ut}">Round {round_["round_idx"] + 1}</div>'
        )
        claims_by_speaker: dict[str, list[Mapping[str, Any]]] = {}
        for claim in round_["claims"]:
            claims_by_speaker.setdefault(claim["speaker_id"], []).append(claim)
        for utterance in round_["utterances"]:
            speaker = utterance["speaker_id"]
            claims = claims_by_speaker.get(speaker, [])
            if speaker == impostor_id:
                for claim in claims:
                    if claim["is_placebo"]:
                        continue
                    if displayed[claim["proposition_id"]]:
                        at += 1
                        af += int(claim["is_false"])
                    else:
                        ut += 1
                        uf += int(claim["is_false"])
            parts.append(
                _turn(
                    utterance,
                    claims,
                    names,
                    is_impostor=speaker == impostor_id,
                    displayed=displayed,
                    af=af,
                    at=at,
                    uf=uf,
                    ut=ut,
                )
            )
        if round_["verifications"]:
            n_wrong = sum(1 for v in round_["verifications"] if not v["correct"])
            n_checked = len(round_["verifications"])
            n_displayed_audited = sum(
                1 for v in round_["verifications"] if displayed[v["proposition_id"]]
            )
            if n_displayed_audited == n_checked:
                checked_text = f"Verifier checked {n_checked} audited claim(s)"
            else:
                # Displayed tags diverge from oracle coverage (shuffled-tags arm):
                # say what was checked without mislabeling it by the board's tags.
                checked_text = (
                    f"Verifier checked {n_checked} claim(s) "
                    f"({n_displayed_audited} displayed [AUDITED] on the board)"
                )
            parts.append(
                f'<div class="verify step" data-af="{af}" data-at="{at}" data-uf="{uf}" '
                f'data-ut="{ut}">{checked_text}; {n_wrong} found false.</div>'
            )
        if round_.get("bulletin"):
            lines = "".join(
                f"<li>{_esc(names.get(str(e['speaker_id']), str(e['speaker_id'])))} on "
                f"\u201c{_esc(e['surface_form'])}\u201d — "
                f"{'<strong>FALSE</strong>' if e['verdict'] == 'false' else 'correct'}</li>"
                for e in round_["bulletin"]["entries"]
            )
            parts.append(
                f'<div class="vote-block step" data-af="{af}" data-at="{at}" '
                f'data-uf="{uf}" data-ut="{ut}"><strong>The Verifier announces its '
                f"findings.</strong><ul>{lines}</ul></div>"
            )
        if round_["vote"]:
            parts.append(_vote(round_["vote"], names, impostor_id, af=af, at=at, uf=uf, ut=ut))
    parts.append(_finale(game, names, impostor_id, af=af, at=at, uf=uf, ut=ut))
    parts.append("</section>")
    return "".join(parts)


def _turn(
    utterance: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    names: Mapping[str, str],
    *,
    is_impostor: bool,
    displayed: Mapping[str, bool],
    af: int,
    at: int,
    uf: int,
    ut: int,
) -> str:
    speaker = utterance["speaker_id"]
    who = '<span class="who">impostor — hidden from the group</span>' if is_impostor else ""
    if utterance["text"]:
        speech = f'<p class="speech">{_esc(utterance["text"])}</p>'
    else:
        speech = (
            '<p class="speech structured">(scripted offline policy — claims below are the '
            "utterance)</p>"
        )
    failure = ""
    if utterance["failure"]:
        failure = '<p class="failure">extraction failed for this utterance</p>'
    chips = "".join(_chip(c, displayed) for c in claims)
    css = "turn impostor" if is_impostor else "turn"
    return (
        f'<article class="{css} step" data-af="{af}" data-at="{at}" data-uf="{uf}" data-ut="{ut}">'
        f'<div class="speaker">{_esc(names.get(speaker, speaker))}{who}</div>'
        f"{speech}{failure}"
        f'<div class="chips">{chips}</div></article>'
    )


def _chip(claim: Mapping[str, Any], displayed: Mapping[str, bool]) -> str:
    verdict = "LIE" if claim["is_false"] else "true"
    css = "claim-chip lie" if claim["is_false"] else "claim-chip"
    scope = "audited" if displayed[claim["proposition_id"]] else "unaudited"
    stance = "asserts" if claim["asserted_value"] else "denies"
    return (
        f'<span class="{css}" title="{stance} {_esc(claim["proposition_id"])}">'
        f'{verdict}<span class="cls">{scope}</span></span>'
    )


def _vote(
    vote: Mapping[str, Any],
    names: Mapping[str, str],
    impostor_id: str,
    *,
    af: int,
    at: int,
    uf: int,
    ut: int,
) -> str:
    lines = ", ".join(
        f'{_esc(names.get(v["voter_id"], v["voter_id"]))} → '
        f'{_esc(names.get(v["target_id"], v["target_id"]))}'
        for v in vote["votes"]
    )
    elim = ""
    if vote["eliminated"]:
        target = vote["eliminated"]
        label = names.get(target, target)
        was = " — the impostor is caught!" if target == impostor_id else " (a panelist falls)"
        elim = f'<div class="elim">{_esc(label)} is eliminated{_esc(was)}</div>'
    return (
        f'<div class="vote-block step" data-af="{af}" data-at="{at}" data-uf="{uf}" '
        f'data-ut="{ut}"><strong>The round ends in a vote.</strong> {lines}{elim}</div>'
    )


def _finale(
    game: Mapping[str, Any],
    names: Mapping[str, str],
    impostor_id: str,
    *,
    af: int,
    at: int,
    uf: int,
    ut: int,
) -> str:
    outcome = (
        "The impostor was eliminated before the final round."
        if game["ended_early"]
        else "The impostor survived every vote."
    )

    # Rates from the displayed-fold counters the timeline accumulated, so the finale
    # sentence always agrees with the footer scoreboard and the board it sits next to
    # (identical to the record's true-class scores block except under shuffled tags).
    def rate(false: int, total: int) -> str:
        return "—" if total == 0 else f"{false / total:.2f}"

    return (
        f'<div class="finale step" data-af="{af}" data-at="{at}" data-uf="{uf}" data-ut="{ut}">'
        f"<strong>Final.</strong> {_esc(names.get(impostor_id, impostor_id))} was the impostor. "
        f"{outcome} False-claim rate on audited statements: {rate(af, at)}; "
        f"on unaudited: {rate(uf, ut)}.</div>"
    )


def _scoreboard() -> str:
    return (
        '<footer class="scoreboard" aria-live="polite"><span>impostor false claims — '
        'audited: <strong id="sb-af">0</strong>/<strong id="sb-at">0</strong></span>'
        '<span>unaudited: <strong id="sb-uf">0</strong>/<strong id="sb-ut">0</strong></span>'
        "<span>watch whether the lies migrate to the unaudited side</span></footer>"
    )
