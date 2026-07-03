"""Environment-driven configuration. Validate at the boundary; fail fast and clearly."""

from __future__ import annotations

import os

from bsq.llm.base import KNOWN_PROVIDERS, ProviderConfig
from bsq.models import CONTROL_ARMS, STANDARD_ARMS, GameConfig, VerifierArm


def _get(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _int(name: str) -> int | None:
    raw = _get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def provider_config_from_env() -> ProviderConfig:
    """Build a :class:`ProviderConfig` from ``BSQ_*`` variables (default: mock)."""
    provider = _get("BSQ_PROVIDER") or "mock"
    if provider not in KNOWN_PROVIDERS:
        raise ValueError(
            f"BSQ_PROVIDER={provider!r} is invalid; expected one of {sorted(KNOWN_PROVIDERS)}"
        )
    return ProviderConfig(
        provider=provider,
        model=_get("BSQ_MODEL"),
        api_key=_get("BSQ_API_KEY"),
        base_url=_get("BSQ_BASE_URL"),
        seed=_int("BSQ_SEED"),
        temperature=_float("BSQ_TEMPERATURE", 0.0),
    )


def resolve_arm(name: str) -> VerifierArm:
    """Look up a verifier arm by name (behavioral arms first, then control arms)."""
    if name in STANDARD_ARMS:
        return STANDARD_ARMS[name]
    if name in CONTROL_ARMS:
        return CONTROL_ARMS[name]
    raise ValueError(
        f"unknown verifier arm {name!r}; expected one of "
        f"{sorted(STANDARD_ARMS) + sorted(CONTROL_ARMS)}"
    )


def _bool(name: str, default: bool) -> bool:
    raw = _get(name)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean (1/0/true/false), got {raw!r}")


def game_config_from_env() -> GameConfig:
    """Build a :class:`GameConfig` from ``BSQ_*`` variables."""
    arm = _get("BSQ_VERIFIER_ARM") or "A0_off"
    resolve_arm(arm)  # validate eagerly
    phi = _float("BSQ_CHECKABILITY_FRACTION", 0.5)
    if not 0.0 <= phi <= 1.0:
        raise ValueError(f"BSQ_CHECKABILITY_FRACTION must be in [0, 1], got {phi}")
    interactive = _bool("BSQ_INTERACTIVE", default=False)
    return GameConfig(checkability_fraction=phi, verifier_arm=arm, interactive=interactive)
