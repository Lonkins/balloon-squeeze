"""The real-provider determinism gate — deliberately NOT run offline.

This is the open half of the Phase 2 gate. It cannot be closed without a real LLM
client (Phase 3) and an API key, and a mock must never stand in for it. The test is
skipped so the suite shows it as not-passed (never green) until it is closed for real.
"""

from __future__ import annotations

import pytest

_MANUAL_COMMAND = (
    "BSQ_PROVIDER=openai-compatible BSQ_API_KEY=... BSQ_MODEL=... BSQ_TEMPERATURE=0 "
    "bsq replay --seed 0"
)


@pytest.mark.skip(
    reason=(
        "GATE blocked on Phase 3: real-provider determinism needs a real LLM client + "
        f"API key. Close it manually once the real client lands: `{_MANUAL_COMMAND}`."
    )
)
def test_real_provider_determinism_gate() -> None:
    raise AssertionError("real-provider determinism is not demonstrable offline")
