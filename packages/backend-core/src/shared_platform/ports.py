from __future__ import annotations

from typing import Protocol, Sequence

from .contracts import (
    ActionProposal,
    EventEnvelope,
    PolicyDecision,
    StateSnapshot,
    ToolResult,
    UserIntent,
)


class AgentGateway(Protocol):
    """Produces proposals only; it cannot mutate platform state."""

    def propose(
        self, intent: UserIntent, state: StateSnapshot
    ) -> Sequence[ActionProposal]: ...


class PolicyEngine(Protocol):
    def evaluate(
        self, proposal: ActionProposal, state: StateSnapshot
    ) -> PolicyDecision: ...


class Tool(Protocol):
    name: str
    version: str

    def execute(self, payload: dict[str, object]) -> ToolResult: ...


class ToolRegistry(Protocol):
    def resolve(self, extension_id: str, action_type: str) -> Tool | None: ...


class StateStore(Protocol):
    def get(self, extension_id: str, aggregate_id: str) -> StateSnapshot: ...

    def compare_and_set(
        self, expected_version: int, new_state: StateSnapshot
    ) -> None: ...


class EventStore(Protocol):
    def append(self, event: EventEnvelope) -> None: ...


class Extension(Protocol):
    extension_id: str

    def validate(self, proposal: ActionProposal, state: StateSnapshot) -> None: ...

    def reduce(
        self,
        state: StateSnapshot,
        proposal: ActionProposal,
        result: ToolResult | None,
    ) -> tuple[StateSnapshot, Sequence[EventEnvelope]]: ...
