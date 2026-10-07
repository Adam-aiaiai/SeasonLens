from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .contracts import ActionProposal, EventEnvelope, StateSnapshot, UserIntent


class VersionConflictError(RuntimeError):
    pass


@dataclass
class InMemoryStateStore:
    snapshots: dict[tuple[str, str], StateSnapshot] = field(default_factory=dict)

    def get(self, extension_id: str, aggregate_id: str) -> StateSnapshot:
        return self.snapshots[(extension_id, aggregate_id)]

    def compare_and_set(self, expected_version: int, new_state: StateSnapshot) -> None:
        key = (new_state.extension_id, new_state.aggregate_id)
        current = self.snapshots.get(key)
        if current is not None and current.version != expected_version:
            raise VersionConflictError(
                f"Expected v{expected_version}; found v{current.version}."
            )
        if new_state.version != expected_version + 1:
            raise ValueError("A state transition must advance exactly one version.")
        self.snapshots[key] = new_state


@dataclass
class InMemoryEventStore:
    events: list[EventEnvelope] = field(default_factory=list)

    def append(self, event: EventEnvelope) -> None:
        self.events.append(event)


@dataclass(frozen=True)
class ReplayAgentGateway:
    """Returns frozen proposals for controlled studies and deterministic tests."""

    proposals_by_correlation: dict[str, Sequence[ActionProposal]]

    def propose(
        self, intent: UserIntent, state: StateSnapshot
    ) -> Sequence[ActionProposal]:
        return self.proposals_by_correlation.get(intent.correlation_id, ())
