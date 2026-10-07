from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence
from uuid import uuid4

from shared_platform import (
    ActionProposal,
    Actor,
    ActorType,
    EventEnvelope,
    StateSnapshot,
    ToolResult,
    ToolStatus,
    UserIntent,
)

from .catalog import DemoItemCatalog
from .regions import (
    classify_semantic_region,
    normalized_rectangle,
    region_iou,
    target_definition,
    validate_region_selection,
)


EXTENSION_ID = "seasonlens"
CONDITION = "observation-first-contingent"
ANSWER_FIRST = "answer-first"
YOKED_NON_CONTINGENT = "observation-first-yoked"


class DifficultyCode(StrEnum):
    REGION_MISS = "REGION_MISS"
    CUE_MISIDENTIFIED = "CUE_MISIDENTIFIED"
    INTERPRETATION_ERROR = "INTERPRETATION_ERROR"
    CORRECT = "CORRECT"


class SeasonLensStage(StrEnum):
    OBSERVE = "OBSERVE"
    INITIAL_COMMITTED = "INITIAL_COMMITTED"
    POSITIVE_FEEDBACK = "POSITIVE_FEEDBACK"
    HINT = "HINT"
    REOBSERVE = "REOBSERVE"
    REVISED_COMMITTED = "REVISED_COMMITTED"
    REVEAL = "REVEAL"
    REFLECTION = "REFLECTION"
    COMPLETE = "COMPLETE"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _contains_keyword(text: object, keywords: Sequence[str]) -> bool:
    normalized = " ".join(str(text).casefold().split())
    return any(keyword.casefold() in normalized for keyword in keywords)


def _stage_choice_accepted(item: Mapping[str, Any], response: Mapping[str, Any]) -> bool:
    """Use stable stage IDs when authored; retain keyword scoring for legacy items."""
    correct_stage_id = item.get("correct_stage_id")
    if correct_stage_id is not None:
        return response.get("selected_stage_id") == correct_stage_id
    return _contains_keyword(
        response.get("interpretation_text", ""),
        item["accepted_interpretation_keywords"],
    )


def score_structured_response(
    item: Mapping[str, Any], response: Mapping[str, Any]
) -> dict[str, bool]:
    return {
        "region_accepted": validate_region_selection(
            response.get("selected_region", {}), target_definition(item)["rect"], item.get("region_iou_threshold", 0.25)
        ),
        "cue_accepted": _contains_keyword(
            response.get("observation_text", ""), item["accepted_cue_keywords"]
        ),
        "interpretation_accepted": _stage_choice_accepted(item, response),
    }


def classify_difficulty(
    item: Mapping[str, Any], response: Mapping[str, Any]
) -> DifficultyCode:
    scores = score_structured_response(item, response)
    if not scores["region_accepted"]:
        return DifficultyCode.REGION_MISS
    if not scores["cue_accepted"]:
        return DifficultyCode.CUE_MISIDENTIFIED
    if not scores["interpretation_accepted"]:
        return DifficultyCode.INTERPRETATION_ERROR
    return DifficultyCode.CORRECT


def diagnose_response(item: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    """Independent literal checks; ordered primary error is region, cue, interpretation.

    Semantic interpretation is a future extension, not part of this scorer.
    """
    checks = score_structured_response(item, response)
    spatial = classify_semantic_region(item, response.get("selected_region"))
    return {
        **spatial,
        "region_correct": checks["region_accepted"],
        "cue_correct": checks["cue_accepted"],
        "interpretation_correct": checks["interpretation_accepted"],
        "stage_correct": checks["interpretation_accepted"],
        "primary_error": classify_difficulty(item, response).value,
        "region_iou": spatial["target_iou"],
    }


def diagnostic_reason(diagnostic: Mapping[str, Any]) -> str:
    """Explain the ordered diagnosis without changing the existing taxonomy."""
    reasons = {
        DifficultyCode.REGION_MISS.value: "Selected region does not overlap the accepted expert region.",
        DifficultyCode.CUE_MISIDENTIFIED.value: "The region is relevant, but the observation missed the accepted visual cue.",
        DifficultyCode.INTERPRETATION_ERROR.value: "The region and cue are relevant, but the stage choice is not accepted.",
        DifficultyCode.CORRECT.value: "The relevant region, visual cue, and stage choice are correct.",
    }
    return reasons.get(str(diagnostic.get("primary_error")), "No diagnosis is available yet.")


def select_hint_decision(
    item: Mapping[str, Any], difficulty: DifficultyCode | str, level: int = 1, *,
    selected_semantic_region: str | None = None,
) -> dict[str, Any]:
    """Prefer an authored spatial hint on a region miss, then the existing category tier."""
    code = DifficultyCode(difficulty)
    source = None
    hint = None
    if code is DifficultyCode.REGION_MISS:
        spatial_hints = item.get("region_hints", {}).get(selected_semantic_region, [])
        hint = next((entry for entry in spatial_hints if entry["level"] == level), None)
        source = "semantic_region" if hint else "generic_region_miss"
    if hint is None:
        hint = next((entry for entry in item["hints"].get(code.value, []) if entry["level"] == level), None)
    if hint is None:
        raise ValueError(f"No authored hint for {code.value} at level {level}")
    return {
        "hint": deepcopy(hint), "region_hint_source": source,
        "region_hint_id": hint["id"] if code is DifficultyCode.REGION_MISS else None,
        "region_hint_region_id": selected_semantic_region if source == "semantic_region" else None,
    }


def select_hint_from_library(
    item: Mapping[str, Any], difficulty: DifficultyCode | str, level: int = 1, *,
    selected_semantic_region: str | None = None,
) -> dict[str, Any]:
    return select_hint_decision(item, difficulty, level,
                                selected_semantic_region=selected_semantic_region)["hint"]


@dataclass(frozen=True)
class ClassifyDifficultyTool:
    catalog: DemoItemCatalog
    name: str = "seasonlens.classify_difficulty"
    version: str = "1.2.0"

    def execute(self, payload: dict[str, object]) -> ToolResult:
        item = self.catalog.get(str(payload["item_id"]))
        response = dict(payload.get("response", payload))  # type: ignore[arg-type]
        scores = score_structured_response(item, response)
        difficulty = classify_difficulty(item, response)
        return ToolResult(
            tool_call_id=str(uuid4()),
            tool_name=self.name,
            tool_version=self.version,
            status=ToolStatus.SUCCEEDED,
            output={"difficulty_code": difficulty.value, "component_checks": scores,
                    "diagnostic": diagnose_response(item, response)},
            reproducibility={
                "code_version": self.version,
                "dataset_checksum": self.catalog.checksum(str(payload["item_id"])),
                "parameters": dict(payload),
            },
        )


@dataclass(frozen=True)
class SelectAllowedHintTool:
    catalog: DemoItemCatalog
    name: str = "seasonlens.select_hint_from_library"
    version: str = "1.3.0"

    def execute(self, payload: dict[str, object]) -> ToolResult:
        item = self.catalog.get(str(payload["item_id"]))
        diagnostic = dict(payload.get("diagnostic") or {})
        fully_correct = (payload["difficulty_code"] == DifficultyCode.CORRECT and
                         diagnostic.get("region_correct") is True and
                         diagnostic.get("cue_correct") is True and
                         diagnostic.get("interpretation_correct") is True)
        if fully_correct:
            decision = {
                "hint": None,
                "positive_feedback": {"text": item.get(
                    "correct_feedback",
                    "Correct. Your selected region, observation, and stage judgement are consistent with the expert answer.",
                )},
                "region_hint_source": None,
                "region_hint_id": None,
                "region_hint_region_id": None,
            }
        else:
            difficulty = (DifficultyCode.CUE_MISIDENTIFIED
                          if payload.get("condition") == YOKED_NON_CONTINGENT
                          else str(payload["difficulty_code"]))
            decision = select_hint_decision(
                item, difficulty,
                level=int(payload.get("hint_level", 1)),
                selected_semantic_region=diagnostic.get("selected_semantic_region"),
            )
            decision["positive_feedback"] = None
        return ToolResult(
            tool_call_id=str(uuid4()),
            tool_name=self.name,
            tool_version=self.version,
            status=ToolStatus.SUCCEEDED,
            output={**decision, "hint_shown_at": payload["hint_shown_at"]},
            reproducibility={
                "code_version": self.version,
                "dataset_checksum": self.catalog.checksum(str(payload["item_id"])),
                "parameters": dict(payload),
            },
        )


class RuleBasedSeasonLensAgent:
    """Creates only the two deterministic automatic proposals used by the MVP."""

    def propose(
        self, intent: UserIntent, state: StateSnapshot
    ) -> Sequence[ActionProposal]:
        event = dict(intent.ui_event or {})
        action = str(event.get("next_action", ""))
        if action == "CLASSIFY_DIFFICULTY":
            return (
                ActionProposal(
                    extension_id=EXTENSION_ID,
                    action_type=action,
                    actor=Actor(ActorType.SYSTEM, "seasonlens.rule-policy-v1"),
                    payload={
                        "item_id": state.data["item_id"],
                        "response": deepcopy(state.data["initial_attempt"]),
                        "action_at": event["action_at"],
                    },
                    expected_state_version=state.version,
                    requires_confirmation=False,
                    rationale="Apply the frozen ordered difficulty rules.",
                ),
            )
        if action == "SELECT_ALLOWED_HINT":
            diagnostic = deepcopy(
                state.data.get("revised_diagnostic") or state.data["diagnostic"]
            )
            difficulty_code = str(diagnostic["primary_error"])
            previous_levels = [
                int(entry["hint_level"])
                for entry in state.data["hint_sequence"]
                if not entry.get("manual_override")
                and entry.get("error_type") == difficulty_code
            ]
            return (
                ActionProposal(
                    extension_id=EXTENSION_ID,
                    action_type=action,
                    actor=Actor(ActorType.SYSTEM, "seasonlens.rule-policy-v1"),
                    payload={
                        "item_id": state.data["item_id"],
                        "difficulty_code": difficulty_code,
                        "condition": state.data["condition"],
                        "diagnostic": diagnostic,
                        "hint_level": min(max(previous_levels, default=0) + 1, 3),
                        "hint_shown_at": event["hint_shown_at"],
                        "action_at": event["action_at"],
                    },
                    expected_state_version=state.version,
                    requires_confirmation=False,
                    rationale="Select exactly one hint from the frozen item library.",
                ),
            )
        raise ValueError(f"Unsupported automatic SeasonLens action: {action}")


class SeasonLensExtension:
    extension_id = EXTENSION_ID

    _expected_stages = {
        "RECORD_INITIAL_OBSERVATION": SeasonLensStage.OBSERVE,
        "CLASSIFY_DIFFICULTY": SeasonLensStage.INITIAL_COMMITTED,
        "SHOW_POSITIVE_FEEDBACK": SeasonLensStage.INITIAL_COMMITTED,
        "SELECT_ALLOWED_HINT": None,
        "BEGIN_UNAIDED_FINAL": SeasonLensStage.INITIAL_COMMITTED,
        "BEGIN_REOBSERVATION": SeasonLensStage.HINT,
        "RECORD_REOBSERVATION": SeasonLensStage.REOBSERVE,
        "REVEAL_EXPERT_CUE": None,
        "BEGIN_REFLECTION": SeasonLensStage.REVEAL,
        "RECORD_FEEDBACK_RESPONSE": SeasonLensStage.REFLECTION,
        "COMPLETE_UNAIDED": SeasonLensStage.REVISED_COMMITTED,
        "OVERRIDE_AUTHORED_HINT": SeasonLensStage.HINT,
        "RECORD_RESEARCHER_NOTE": None,
    }

    def validate(self, proposal: ActionProposal, state: StateSnapshot) -> None:
        _require(proposal.extension_id == self.extension_id, "Wrong extension ID.")
        _require(proposal.action_type in self._expected_stages, "Unknown action type.")
        expected = self._expected_stages[proposal.action_type]
        _require(
            expected is None or state.data["stage"] == expected.value,
            f"{proposal.action_type} requires {expected.value if expected else 'a session'}; "
            f"current stage is {state.data['stage']}.",
        )
        payload = dict(proposal.payload)
        if proposal.action_type == "RECORD_INITIAL_OBSERVATION":
            self._validate_observation(payload, include_confidence=True)
            _require(state.data["initial_attempt"] is None, "Initial attempt is immutable.")
        elif proposal.action_type == "CLASSIFY_DIFFICULTY":
            _require(state.data["initial_attempt"] is not None, "Initial attempt is missing.")
            _require(state.data["difficulty_code"] is None, "Difficulty already classified.")
        elif proposal.action_type == "SHOW_POSITIVE_FEEDBACK":
            _require(state.data["difficulty_code"] == DifficultyCode.CORRECT.value,
                     "Positive feedback requires a fully correct initial response.")
        elif proposal.action_type == "SELECT_ALLOWED_HINT":
            _require(state.data["difficulty_code"] is not None, "Difficulty is not classified.")
            _require(state.data["stage"] in {
                SeasonLensStage.INITIAL_COMMITTED.value,
                SeasonLensStage.REVISED_COMMITTED.value,
            }, "Hints can only follow a committed response.")
        elif proposal.action_type == "RECORD_REOBSERVATION":
            self._validate_observation(payload, include_confidence=False)
        elif proposal.action_type == "REVEAL_EXPERT_CUE":
            _require(state.data["stage"] in {
                SeasonLensStage.POSITIVE_FEEDBACK.value,
                SeasonLensStage.REVISED_COMMITTED.value,
            }, "REVEAL_EXPERT_CUE requires POSITIVE_FEEDBACK or REVISED_COMMITTED; "
               f"current stage is {state.data['stage']}.")
        elif proposal.action_type == "RECORD_FEEDBACK_RESPONSE":
            _require(isinstance(payload.get("reflection_text"), str) and bool(payload["reflection_text"].strip()), "Reflection is required.")
            _require(payload.get("reflection_category") in (None, "", "Where I looked", "What feature I noticed",
                     "What the feature meant", "My confidence", "Other"), "Choose a reflection option.")
        elif proposal.action_type in {"OVERRIDE_AUTHORED_HINT", "RECORD_RESEARCHER_NOTE"}:
            _require(proposal.actor.actor_id == "seasonlens.researcher", "Researcher action required.")

    @staticmethod
    def _validate_observation(payload: dict[str, object], *, include_confidence: bool) -> None:
        region = payload.get("selected_region")
        _require(normalized_rectangle(region) is not None, "Draw a rectangle on the image before submitting.")
        _require(isinstance(payload.get("observation_text"), str) and bool(payload["observation_text"].strip()), "Observation is required.")
        has_stage_id = isinstance(payload.get("selected_stage_id"), str) and bool(payload["selected_stage_id"].strip())
        has_legacy_interpretation = isinstance(payload.get("interpretation_text"), str) and bool(payload["interpretation_text"].strip())
        _require(has_stage_id or has_legacy_interpretation, "Choose a plant stage.")
        if include_confidence:
            confidence = payload.get("confidence")
            _require(isinstance(confidence, int) and not isinstance(confidence, bool) and 1 <= confidence <= 5,
                     "Choose confidence from 1 to 5.")

    def reduce(
        self,
        state: StateSnapshot,
        proposal: ActionProposal,
        result: ToolResult | None,
    ) -> tuple[StateSnapshot, Sequence[EventEnvelope]]:
        data = deepcopy(dict(state.data))
        action = proposal.action_type
        event_type = ""
        event_payload: dict[str, Any] = {}

        if action == "RECORD_INITIAL_OBSERVATION":
            data["initial_attempt"] = deepcopy(dict(proposal.payload))
            data["initial_attempt"]["selected_region"] = normalized_rectangle(proposal.payload["selected_region"])
            data["stage"] = SeasonLensStage.INITIAL_COMMITTED.value
            event_type = "seasonlens.initial-observation-recorded"
            event_payload = {"initial_attempt": deepcopy(data["initial_attempt"])}
        elif action == "CLASSIFY_DIFFICULTY":
            _require(result is not None, "Classification requires a tool result.")
            data["difficulty_code"] = result.output["difficulty_code"]
            data["component_checks"] = deepcopy(result.output["component_checks"])
            data["diagnostic"] = deepcopy(result.output["diagnostic"])
            data["participant_path"] = [
                "INITIAL_CORRECT"
                if data["difficulty_code"] == DifficultyCode.CORRECT.value
                else data["difficulty_code"]
            ]
            event_type = "seasonlens.difficulty-classified"
            event_payload = {"difficulty_code": data["difficulty_code"], "diagnostic": deepcopy(data["diagnostic"])}
        elif action == "SHOW_POSITIVE_FEEDBACK":
            data["positive_feedback"] = {
                "text": proposal.payload["text"],
                "shown_at": proposal.payload["shown_at"],
            }
            data["stage"] = SeasonLensStage.POSITIVE_FEEDBACK.value
            event_type = "seasonlens.positive-feedback-shown"
            event_payload = deepcopy(data["positive_feedback"])
        elif action == "SELECT_ALLOWED_HINT":
            _require(result is not None, "Hint selection requires a tool result.")
            feedback = deepcopy(result.output.get("positive_feedback"))
            if feedback is not None:
                data["positive_feedback"] = {
                    "text": feedback["text"],
                    "shown_at": result.output["hint_shown_at"],
                }
                event_type = "seasonlens.positive-feedback-shown"
                event_payload = deepcopy(data["positive_feedback"])
                data["stage"] = SeasonLensStage.POSITIVE_FEEDBACK.value
            else:
                hint = deepcopy(result.output["hint"])
                data["hint_exposure"] = {
                    "hint_id": hint["id"],
                    "automatic_hint_id": hint["id"],
                    "actual_hint_id": hint["id"],
                    "manual_override": False,
                    "region_hint_source": result.output["region_hint_source"],
                    "region_hint_id": result.output["region_hint_id"],
                    "region_hint_region_id": result.output["region_hint_region_id"],
                    "automatic_region_hint_source": result.output["region_hint_source"],
                    "automatic_region_hint_id": result.output["region_hint_id"],
                    "hint_level": hint["level"],
                    "hint_type": hint["type"],
                    "hint_text": hint["text"],
                    "hint_shown_at": result.output["hint_shown_at"],
                    "error_type": proposal.payload["difficulty_code"],
                    "hint_provenance": result.output["region_hint_source"] or "authored_error_type",
                }
                data["hint_sequence"].append(deepcopy(data["hint_exposure"]))
                data["participant_path"].append(f"L{hint['level']}")
                event_type = "seasonlens.authored-hint-shown"
                event_payload = deepcopy(data["hint_exposure"])
                data["stage"] = SeasonLensStage.HINT.value
        elif action == "BEGIN_UNAIDED_FINAL":
            data["stage"] = SeasonLensStage.REOBSERVE.value
            event_type = "seasonlens.unaided-final-started"
        elif action == "BEGIN_REOBSERVATION":
            data["stage"] = SeasonLensStage.REOBSERVE.value
            event_type = "seasonlens.reobservation-started"
        elif action == "RECORD_REOBSERVATION":
            _require(result is not None, "Revision diagnosis requires a tool result.")
            data["revised_diagnostic"] = deepcopy(result.output["diagnostic"])
            data["revised_attempt"] = deepcopy(dict(proposal.payload))
            data["revised_attempt"]["selected_region"] = normalized_rectangle(proposal.payload["selected_region"])
            data["revised_attempts"].append(deepcopy(data["revised_attempt"]))
            data["revised_diagnostics"].append(deepcopy(data["revised_diagnostic"]))
            data["participant_path"].append(data["revised_diagnostic"]["primary_error"])
            data["stage"] = SeasonLensStage.REVISED_COMMITTED.value
            event_type = "seasonlens.reobservation-recorded"
            event_payload = {"revised_attempt": deepcopy(data["revised_attempt"]),
                             "revised_diagnostic": deepcopy(data["revised_diagnostic"])}
        elif action == "REVEAL_EXPERT_CUE":
            data["expert_reveal_at"] = proposal.payload["expert_reveal_at"]
            data["stage"] = SeasonLensStage.REVEAL.value
            event_type = "seasonlens.expert-cue-revealed"
            event_payload = {"expert_reveal_at": data["expert_reveal_at"]}
        elif action == "BEGIN_REFLECTION":
            data["stage"] = SeasonLensStage.REFLECTION.value
            event_type = "seasonlens.reflection-started"
        elif action == "RECORD_FEEDBACK_RESPONSE":
            data["reflection"] = deepcopy(dict(proposal.payload))
            data["completed_at"] = proposal.payload["reflection_submitted_at"]
            data["stage"] = SeasonLensStage.COMPLETE.value
            event_type = "seasonlens.reflection-recorded"
            event_payload = {"reflection": deepcopy(data["reflection"])}
        elif action == "COMPLETE_UNAIDED":
            data["completed_at"] = proposal.payload["completed_at"]
            data["stage"] = SeasonLensStage.COMPLETE.value
            event_type = "seasonlens.unaided-response-completed"
            event_payload = {"completed_at": data["completed_at"]}
        elif action == "OVERRIDE_AUTHORED_HINT":
            hint = proposal.payload["hint"]
            data["hint_exposure"] = {
                "hint_id": hint["id"], "actual_hint_id": hint["id"],
                "automatic_hint_id": data["hint_exposure"]["automatic_hint_id"],
                "automatic_region_hint_source": data["hint_exposure"]["automatic_region_hint_source"],
                "automatic_region_hint_id": data["hint_exposure"]["automatic_region_hint_id"],
                "region_hint_source": hint["region_hint_source"],
                "region_hint_id": hint["id"] if hint["category"] == "REGION_MISS" else None,
                "region_hint_region_id": hint["region_id"],
                "manual_override": True, "hint_level": hint["level"], "hint_type": hint["type"],
                "hint_text": hint["text"], "hint_shown_at": proposal.payload["action_at"],
                "error_type": hint["category"],
                "hint_provenance": "researcher_override",
            }
            data["hint_sequence"].append(deepcopy(data["hint_exposure"]))
            event_type = "seasonlens.manual-hint-overridden"
            event_payload = deepcopy(data["hint_exposure"])
        elif action == "RECORD_RESEARCHER_NOTE":
            data["researcher_notes"] = proposal.payload["researcher_notes"]
            event_type = "seasonlens.researcher-note-recorded"
            event_payload = {"researcher_notes": data["researcher_notes"]}

        if data["stage"] != state.data["stage"]:
            transition = {"from": state.data["stage"], "to": data["stage"],
                          "at": proposal.payload["action_at"]}
            data["stage_transitions"].append(transition)
            event_payload["stage_transition"] = transition

        new_state = StateSnapshot(
            extension_id=state.extension_id,
            aggregate_id=state.aggregate_id,
            version=state.version + 1,
            data=data,
        )
        event = EventEnvelope(
            session_id=str(data["session_id"]),
            extension_id=state.extension_id,
            aggregate_id=state.aggregate_id,
            aggregate_version=new_state.version,
            actor=proposal.actor,
            event_type=event_type,
            payload=event_payload,
            correlation_id=proposal.proposal_id,
            causation_id=proposal.proposal_id,
        )
        return new_state, (event,)
