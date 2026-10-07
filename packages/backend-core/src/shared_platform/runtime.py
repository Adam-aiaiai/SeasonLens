from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .contracts import (
    ActionProposal,
    Actor,
    ActorType,
    Decision,
    EventEnvelope,
    PolicyDecision,
    StateSnapshot,
    ToolResult,
    UserIntent,
)
from .ports import AgentGateway, EventStore, Extension, PolicyEngine, StateStore, ToolRegistry


class StaleStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProposalOutcome:
    proposal: ActionProposal
    policy: PolicyDecision
    tool_result: ToolResult | None = None
    state: StateSnapshot | None = None


class Orchestrator:
    """Shared proposal-policy-tool-reducer loop.

    This class deliberately contains no project-specific action semantics and no
    model-provider code. Extensions own domain validation and state reduction.
    """

    def __init__(
        self,
        *,
        agent: AgentGateway,
        policy: PolicyEngine,
        tools: ToolRegistry,
        states: StateStore,
        events: EventStore,
        extensions: dict[str, Extension],
    ) -> None:
        self._agent = agent
        self._policy = policy
        self._tools = tools
        self._states = states
        self._events = events
        self._extensions = extensions

    def propose(self, intent: UserIntent, aggregate_id: str) -> Sequence[ProposalOutcome]:
        extension = self._extensions[intent.extension_id]
        state = self._states.get(extension.extension_id, aggregate_id)
        proposals = self._agent.propose(intent, state)
        outcomes: list[ProposalOutcome] = []

        for proposal in proposals:
            self._check_version(proposal, state)
            extension.validate(proposal, state)
            policy = self._policy.evaluate(proposal, state)
            self._events.append(
                self._event(
                    intent,
                    state,
                    "proposal.created",
                    {"proposal_id": proposal.proposal_id, "action_type": proposal.action_type},
                )
            )
            if policy.decision is Decision.ALLOW:
                outcomes.append(self._execute(intent, state, extension, proposal, policy))
            else:
                outcomes.append(ProposalOutcome(proposal=proposal, policy=policy))
        return outcomes

    def execute_approved(
        self,
        *,
        intent: UserIntent,
        aggregate_id: str,
        proposal: ActionProposal,
    ) -> ProposalOutcome:
        extension = self._extensions[proposal.extension_id]
        state = self._states.get(extension.extension_id, aggregate_id)
        self._check_version(proposal, state)
        extension.validate(proposal, state)
        policy = PolicyDecision(Decision.ALLOW, "Approved by an authorized human")
        return self._execute(intent, state, extension, proposal, policy)

    def _execute(
        self,
        intent: UserIntent,
        state: StateSnapshot,
        extension: Extension,
        proposal: ActionProposal,
        policy: PolicyDecision,
    ) -> ProposalOutcome:
        tool = self._tools.resolve(extension.extension_id, proposal.action_type)
        result = tool.execute(dict(proposal.payload)) if tool else None
        new_state, domain_events = extension.reduce(state, proposal, result)
        self._states.compare_and_set(state.version, new_state)
        for event in domain_events:
            self._events.append(event)
        return ProposalOutcome(proposal, policy, result, new_state)

    @staticmethod
    def _check_version(proposal: ActionProposal, state: StateSnapshot) -> None:
        if proposal.expected_state_version != state.version:
            raise StaleStateError(
                f"Proposal expected state v{proposal.expected_state_version}, "
                f"but current state is v{state.version}."
            )

    @staticmethod
    def _event(
        intent: UserIntent,
        state: StateSnapshot,
        event_type: str,
        payload: dict[str, object],
    ) -> EventEnvelope:
        return EventEnvelope(
            session_id=intent.session_id,
            extension_id=state.extension_id,
            aggregate_id=state.aggregate_id,
            aggregate_version=state.version,
            actor=Actor(ActorType.SYSTEM, "orchestrator"),
            event_type=event_type,
            payload=payload,
            correlation_id=intent.correlation_id,
        )
