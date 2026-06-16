"""Append-only event bus. The ordered event log *is* the data artifact.

Consumers (renderers, the claim scorer, the analysis layer) read the log; nothing
mutates an emitted event. This is what makes a run reproducible and analyzable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    """One immutable game event."""

    kind: str
    payload: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))


class EventBus:
    """An append-only log of events."""

    def __init__(self) -> None:
        self._events: list[Event] = []

    def emit(self, kind: str, /, **payload: Any) -> Event:
        """Append an event and return it."""
        event = Event(kind, MappingProxyType(dict(payload)))
        self._events.append(event)
        return event

    @property
    def events(self) -> Sequence[Event]:
        """A read-only snapshot of the log in emission order."""
        return tuple(self._events)

    def __len__(self) -> int:
        return len(self._events)
