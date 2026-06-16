"""The real human-labeled holdout gate — deliberately NOT run offline.

Extraction-quality validation needs gold labels authored by humans. The synthetic
fixture (tests/fixtures/synthetic_quality.py) verifies the correction math only; it is
never a stand-in for gold. This test is skipped so the suite shows it as not-passed
until a real holdout lands.
"""

from __future__ import annotations

import pytest

_MANUAL_COMMAND = "BSQ_HOLDOUT=path/to/gold.jsonl pytest tests/test_real_holdout_gate.py"


@pytest.mark.skip(
    reason=(
        "GATE blocked: extraction-quality validation requires the human-labeled holdout. "
        "Gold labels must be authored by humans, never synthesized. Close manually once "
        f"labels land: {_MANUAL_COMMAND}"
    )
)
def test_extraction_quality_on_real_holdout() -> None:
    raise AssertionError("extraction quality is not demonstrable without human gold labels")
