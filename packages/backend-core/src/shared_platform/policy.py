from __future__ import annotations

from dataclasses import dataclass

from .contracts import ActionProposal, Decision, PolicyDecision, StateSnapshot


@dataclass(frozen=True)
class AllowlistPolicy:
    """Baseline policy; extension-specific validators may impose stricter rules."""

    allowed_actions: dict[str, frozenset[str]]
    auto_actions: dict[str, frozenset[str]]

    def evaluate(
        self, proposal: ActionProposal, state: StateSnapshot
    ) -> PolicyDecision:
        allowed = self.allowed_actions.get(proposal.extension_id, frozenset())
        if proposal.action_type not in allowed:
            return PolicyDecision(Decision.DENY, "Action is not in the extension allowlist")

        automatic = self.auto_actions.get(proposal.extension_id, frozenset())
        if proposal.action_type in automatic and not proposal.requires_confirmation:
            return PolicyDecision(Decision.ALLOW, "Read-only or preview computation")

        return PolicyDecision(
            Decision.REQUIRE_CONFIRMATION,
            "Action changes accepted state or requires human interpretation",
        )
