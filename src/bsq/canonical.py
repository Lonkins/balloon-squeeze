"""Canonical serialization for byte-comparison of agent decision streams.

The replay-identity contract compares the **agent claim stream** — the decisions an
agent actually made — not the verifier-injected events (which legitimately differ
across arms). A claim's canonical unit is therefore just the decision:
``(round_idx, speaker_id, proposition_id, asserted_value)``. Scoring fields
(``is_false``) and extractor metadata (``extractor_conf``) are excluded: they are not
agent decisions. Serialization is stable (sorted keys, compact separators, no
wall-clock), so two runs are comparable byte-for-byte and the unit generalizes cleanly
to real-model tokens later.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from bsq.models import Claim


def canonical_claim(claim: Claim) -> bytes:
    """The arm-invariant decision content of a claim, as stable bytes."""
    obj = {
        "round_idx": claim.round_idx,
        "speaker_id": claim.speaker_id,
        "proposition_id": claim.proposition_id,
        "asserted_value": claim.asserted_value,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_claim_stream(claims: Sequence[Claim]) -> tuple[bytes, ...]:
    """The ordered canonical claim stream for a run."""
    return tuple(canonical_claim(c) for c in claims)
