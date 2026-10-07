from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping
from uuid import uuid4

JsonObject = Mapping[str, Any]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActorType(StrEnum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"
    TOOL = "tool"


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_CONFIRMATION = "require_confirmation"


class ToolStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class Actor:
    actor_type: ActorType
    actor_id: str


@dataclass(frozen=True)
class StateSnapshot:
    extension_id: str
    aggregate_id: str
    version: int
    data: JsonObject


@dataclass(frozen=True)
class UserIntent:
    session_id: str
    extension_id: str
    actor: Actor
    text: str | None = None
    ui_event: JsonObject | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class ActionProposal:
    extension_id: str
    action_type: str
    actor: Actor
    payload: JsonObject
    expected_state_version: int
    evidence_refs: tuple[str, ...] = ()
    rationale: str | None = None
    requires_confirmation: bool = True
    proposal_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str


@dataclass(frozen=True)
class Approval:
    proposal_id: str
    approved: bool
    actor: Actor
    rationale: str | None = None
    decided_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    tool_name: str
    tool_version: str
    status: ToolStatus
    output: JsonObject
    evidence_refs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    reproducibility: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class EventEnvelope:
    session_id: str
    extension_id: str
    aggregate_id: str
    aggregate_version: int
    actor: Actor
    event_type: str
    payload: JsonObject
    correlation_id: str
    causation_id: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    recorded_at: datetime = field(default_factory=utc_now)
