from shared_platform import (
    ActionProposal,
    Actor,
    ActorType,
    AllowlistPolicy,
    Decision,
    InMemoryStateStore,
    StateSnapshot,
)


def test_policy_allows_only_declared_automatic_action() -> None:
    policy = AllowlistPolicy(
        allowed_actions={"mosaic": frozenset({"RUN_CELL", "ADMIT_DEFINITION"})},
        auto_actions={"mosaic": frozenset({"RUN_CELL"})},
    )
    state = StateSnapshot("mosaic", "case-1", 2, {})
    proposal = ActionProposal(
        extension_id="mosaic",
        action_type="RUN_CELL",
        actor=Actor(ActorType.AGENT, "agent"),
        payload={},
        expected_state_version=2,
        requires_confirmation=False,
    )

    assert policy.evaluate(proposal, state).decision is Decision.ALLOW


def test_state_store_rejects_version_jump() -> None:
    store = InMemoryStateStore()
    store.snapshots[("mosaic", "case-1")] = StateSnapshot("mosaic", "case-1", 1, {})

    try:
        store.compare_and_set(1, StateSnapshot("mosaic", "case-1", 3, {}))
    except ValueError as error:
        assert "exactly one version" in str(error)
    else:
        raise AssertionError("Expected a version-jump failure")
