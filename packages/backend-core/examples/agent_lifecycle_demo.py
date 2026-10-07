"""A complete, dependency-free lifecycle example for the shared platform.

Run after installing the backend core in editable mode:

    cd packages/backend-core
    python -m pip install -e .
    python examples/agent_lifecycle_demo.py

The example intentionally uses a rule-based AgentGateway. Replacing only that
class with a validated live-LLM adapter leaves the policy, tool, reducer,
state/version and event mechanisms unchanged.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Sequence
from uuid import uuid4

from shared_platform import (
    ActionProposal,
    Actor,
    ActorType,
    AllowlistPolicy,
    Decision,
    EventEnvelope,
    InMemoryEventStore,
    InMemoryStateStore,
    Orchestrator,
    Registry,
    StateSnapshot,
    ToolResult,
    ToolStatus,
    UserIntent,
)


EXTENSION_ID = "ceramics-demo"
AGGREGATE_ID = "inquiry-001"
SESSION_ID = "session-001"
DATASET_ID = "ceramics-demo-v1"


# The frozen dataset is deliberately tiny. A real extension would query a
# versioned database or object store, but the tool still owns the calculation.
RECORDS: tuple[dict[str, str], ...] = (
    {"id": "c1", "period": "Song", "motif": "lotus"},
    {"id": "c2", "period": "Song", "motif": "cloud"},
    {"id": "c3", "period": "Song", "motif": "lotus"},
    {"id": "c4", "period": "Yuan", "motif": "lotus"},
    {"id": "c5", "period": "Yuan", "motif": "dragon"},
)


def require(condition: bool, message: str) -> None:
    """Small dependency-free replacement for a schema validation error."""
    if not condition:
        raise ValueError(message)


class RuleBasedCountingAgent:
    """Step 3: turns one known user request into a typed proposal.

    This is an AgentGateway implementation, even though it is not an LLM.
    It demonstrates the contract before model uncertainty is introduced.
    """

    def propose(
        self, intent: UserIntent, state: StateSnapshot
    ) -> Sequence[ActionProposal]:
        require(
            intent.text == "统计宋代样本中莲纹器物的数量",
            "The demo agent only supports its documented example request.",
        )
        return (
            ActionProposal(
                extension_id=EXTENSION_ID,
                action_type="COUNT_MOTIF",
                actor=Actor(ActorType.AGENT, "counting-rule-v1"),
                payload={
                    "dataset_id": DATASET_ID,
                    "period": "Song",
                    "motif": "lotus",
                },
                expected_state_version=state.version,
                evidence_refs=(f"dataset:{DATASET_ID}",),
                rationale="Count the requested motif within the requested period.",
                # We deliberately request confirmation so the demonstration
                # includes the human-authority branch of the lifecycle.
                requires_confirmation=True,
            ),
        )


@dataclass(frozen=True)
class CountMotifTool:
    """Steps 6–7: a deterministic, versioned analysis tool."""

    records: tuple[dict[str, str], ...]
    name: str = "ceramics.count_motif"
    version: str = "1.0.0"

    def execute(self, payload: dict[str, object]) -> ToolResult:
        dataset_id = str(payload["dataset_id"])
        period = str(payload["period"])
        motif = str(payload["motif"])

        period_records = [record for record in self.records if record["period"] == period]
        matched_records = [
            record for record in period_records if record["motif"] == motif
        ]

        if not period_records:
            return ToolResult(
                tool_call_id=str(uuid4()),
                tool_name=self.name,
                tool_version=self.version,
                status=ToolStatus.FAILED,
                output={"reason": f"No records exist for period {period}."},
                warnings=("The requested period has no coverage.",),
                reproducibility={
                    "dataset_checksum": "demo-sha256-ceramics-v1",
                    "code_version": self.version,
                    "parameters": dict(payload),
                },
            )

        matching_ids = [record["id"] for record in matched_records]
        total = len(period_records)
        count = len(matched_records)
        return ToolResult(
            tool_call_id=str(uuid4()),
            tool_name=self.name,
            tool_version=self.version,
            status=ToolStatus.SUCCEEDED,
            output={
                "dataset_id": dataset_id,
                "period": period,
                "motif": motif,
                "count": count,
                "total_in_period": total,
                "proportion": count / total,
                "matching_record_ids": matching_ids,
            },
            evidence_refs=(
                f"dataset:{dataset_id}",
                *(f"object:{record_id}" for record_id in matching_ids),
            ),
            warnings=(),
            reproducibility={
                "dataset_checksum": "demo-sha256-ceramics-v1",
                "code_version": self.version,
                "parameters": dict(payload),
            },
        )


class CeramicsCountingExtension:
    """Steps 4 and 8–9: domain validation, reduction and domain events."""

    extension_id = EXTENSION_ID

    def validate(self, proposal: ActionProposal, state: StateSnapshot) -> None:
        require(proposal.extension_id == self.extension_id, "Wrong extension ID.")
        require(proposal.action_type == "COUNT_MOTIF", "Unknown action type.")
        require(
            proposal.expected_state_version == state.version,
            "The proposal was made against an old state version.",
        )

        # This hand-written check illustrates an action-specific schema.
        # Production code should validate the same fields with the extension's
        # JSON Schema before this method is called.
        payload = dict(proposal.payload)
        require(
            set(payload) == {"dataset_id", "period", "motif"},
            "COUNT_MOTIF payload must contain exactly dataset_id, period and motif.",
        )
        require(payload["dataset_id"] == state.data["dataset_id"], "Unknown dataset.")
        require(
            payload["period"] in state.data["allowed_periods"],
            "Period is not allowed by this inquiry.",
        )
        require(
            payload["motif"] in state.data["allowed_motifs"],
            "Motif is not allowed by this inquiry.",
        )
        require(
            f"dataset:{payload['dataset_id']}" in proposal.evidence_refs,
            "The proposal must cite its dataset.",
        )

    def reduce(
        self,
        state: StateSnapshot,
        proposal: ActionProposal,
        result: ToolResult | None,
    ) -> tuple[StateSnapshot, Sequence[EventEnvelope]]:
        require(result is not None, "COUNT_MOTIF requires a tool result.")
        require(result.status is ToolStatus.SUCCEEDED, "Tool failed; state is unchanged.")

        data = deepcopy(dict(state.data))
        analysis_id = f"analysis-{result.tool_call_id}"
        run = {
            "analysis_id": analysis_id,
            "proposal_id": proposal.proposal_id,
            "tool_call_id": result.tool_call_id,
            "result": dict(result.output),
            "evidence_refs": list(result.evidence_refs),
            "reproducibility": dict(result.reproducibility),
        }
        data["analysis_runs"].append(run)

        new_state = StateSnapshot(
            extension_id=state.extension_id,
            aggregate_id=state.aggregate_id,
            version=state.version + 1,
            data=data,
        )

        # The current core Extension.reduce interface does not receive the
        # UserIntent. For this standalone example the proposal ID is used as
        # the domain-event correlation key. A production implementation should
        # pass a full execution context so intent.correlation_id is retained.
        event_base = {
            "session_id": str(state.data["session_id"]),
            "extension_id": state.extension_id,
            "aggregate_id": state.aggregate_id,
            "aggregate_version": new_state.version,
            "correlation_id": proposal.proposal_id,
            "causation_id": proposal.proposal_id,
        }
        events = (
            EventEnvelope(
                **event_base,
                actor=Actor(ActorType.TOOL, result.tool_name),
                event_type="tool.succeeded",
                payload={
                    "proposal_id": proposal.proposal_id,
                    "tool_call_id": result.tool_call_id,
                    "tool_name": result.tool_name,
                    "tool_version": result.tool_version,
                },
            ),
            EventEnvelope(
                **event_base,
                actor=Actor(ActorType.SYSTEM, "ceramics-demo.reducer"),
                event_type="analysis.counted",
                payload={
                    "analysis_id": analysis_id,
                    "count": result.output["count"],
                    "total_in_period": result.output["total_in_period"],
                    "evidence_refs": list(result.evidence_refs),
                },
            ),
        )
        return new_state, events


def build_count_projection(state: StateSnapshot) -> dict[str, object]:
    """Step 10: turn domain state into a UI-oriented read model."""
    cards = []
    for run in state.data["analysis_runs"]:
        result = run["result"]
        cards.append(
            {
                "analysis_id": run["analysis_id"],
                "headline": (
                    f"{result['period']} period: {result['count']} of "
                    f"{result['total_in_period']} objects contain {result['motif']}."
                ),
                "proportion": result["proportion"],
                "evidence_refs": run["evidence_refs"],
                "warning": None,
            }
        )
    return {
        "extension_id": state.extension_id,
        "aggregate_id": state.aggregate_id,
        "state_version": state.version,
        "projection_type": "motif-count-summary",
        "cards": cards,
    }


def record_approval(
    events: InMemoryEventStore,
    intent: UserIntent,
    state: StateSnapshot,
    proposal: ActionProposal,
) -> None:
    """Record the human decision before the skeleton executes the proposal.

    The current backend-core deliberately leaves pending-proposal persistence
    and authorization to the future API/application layer. The explicit event
    below makes the approval visible in this complete tutorial trace.
    """
    events.append(
        EventEnvelope(
            session_id=intent.session_id,
            extension_id=state.extension_id,
            aggregate_id=state.aggregate_id,
            aggregate_version=state.version,
            actor=Actor(ActorType.HUMAN, "researcher-7"),
            event_type="approval.granted",
            payload={
                "proposal_id": proposal.proposal_id,
                "rationale": "The requested dataset and filters are appropriate.",
            },
            correlation_id=intent.correlation_id,
            causation_id=proposal.proposal_id,
        )
    )


def main() -> None:
    # Step 1: a person expresses a goal through a UI or text input.
    intent = UserIntent(
        session_id=SESSION_ID,
        extension_id=EXTENSION_ID,
        actor=Actor(ActorType.HUMAN, "researcher-7"),
        text="统计宋代样本中莲纹器物的数量",
    )

    # Step 2: initialize and then read the aggregate's structured state.
    states = InMemoryStateStore(
        snapshots={
            (EXTENSION_ID, AGGREGATE_ID): StateSnapshot(
                extension_id=EXTENSION_ID,
                aggregate_id=AGGREGATE_ID,
                version=0,
                data={
                    "session_id": SESSION_ID,
                    "dataset_id": DATASET_ID,
                    "allowed_periods": ["Song", "Yuan"],
                    "allowed_motifs": ["lotus", "cloud", "dragon"],
                    "analysis_runs": [],
                },
            )
        }
    )
    events = InMemoryEventStore()

    # Assemble the extension, its tool binding and its policy in one place.
    extension = CeramicsCountingExtension()
    registry = Registry()
    registry.register_extension(extension)
    registry.register_tool(EXTENSION_ID, "COUNT_MOTIF", CountMotifTool(RECORDS))
    policy = AllowlistPolicy(
        allowed_actions={EXTENSION_ID: frozenset({"COUNT_MOTIF"})},
        auto_actions={EXTENSION_ID: frozenset({"COUNT_MOTIF"})},
    )
    orchestrator = Orchestrator(
        agent=RuleBasedCountingAgent(),
        policy=policy,
        tools=registry,
        states=states,
        events=events,
        extensions=registry.extensions,
    )

    # Steps 3–5: proposal, validation and policy evaluation.
    outcome = orchestrator.propose(intent, AGGREGATE_ID)[0]
    assert outcome.policy.decision is Decision.REQUIRE_CONFIRMATION
    print(f"Policy: {outcome.policy.decision} — {outcome.policy.reason}")
    print(f"Proposed action: {outcome.proposal.action_type}")

    # The human sees the proposal in an approval tray and accepts it.
    state_before_approval = states.get(EXTENSION_ID, AGGREGATE_ID)
    record_approval(events, intent, state_before_approval, outcome.proposal)

    # Steps 6–9: execute tool, reduce to v1, append domain events.
    completed = orchestrator.execute_approved(
        intent=intent,
        aggregate_id=AGGREGATE_ID,
        proposal=outcome.proposal,
    )
    assert completed.tool_result is not None
    assert completed.state is not None
    print(f"Tool result: {completed.tool_result.output}")

    # Step 10: obtain a UI-oriented representation instead of exposing raw state.
    projection = build_count_projection(completed.state)
    print(f"Projection: {projection}")

    print("\nAudit events:")
    for event in events.events:
        print(
            f"- v{event.aggregate_version} {event.event_type} "
            f"actor={event.actor.actor_id} causation={event.causation_id}"
        )


if __name__ == "__main__":
    main()
