from __future__ import annotations

import json
import csv
import io
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from shared_platform import (
    ActionProposal,
    Actor,
    ActorType,
    AllowlistPolicy,
    EventEnvelope,
    InMemoryEventStore,
    InMemoryStateStore,
    Orchestrator,
    Registry,
    StateSnapshot,
    UserIntent,
)

from .catalog import DemoItemCatalog
from .domain import (
    ANSWER_FIRST,
    CONDITION,
    EXTENSION_ID,
    YOKED_NON_CONTINGENT,
    ClassifyDifficultyTool,
    RuleBasedSeasonLensAgent,
    SeasonLensExtension,
    SeasonLensStage,
    SelectAllowedHintTool,
    diagnostic_reason,
)


TRAINING_MODE = "training"
UNAIDED_TEST_MODE = "unaided_test"
TRANSFER_MODE = "transfer"
STUDY_MODES = frozenset({TRAINING_MODE, UNAIDED_TEST_MODE, TRANSFER_MODE})
CONDITIONS = frozenset({ANSWER_FIRST, YOKED_NON_CONTINGENT, CONDITION})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SeasonLensService:
    """Application service that composes the shared runtime for one MVP condition."""

    def __init__(
        self,
        *,
        export_directory: Path | None = None,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.catalog = DemoItemCatalog()
        self.states = InMemoryStateStore()
        self.events = InMemoryEventStore()
        self.clock = clock
        self.export_directory = export_directory

        extension = SeasonLensExtension()
        registry = Registry()
        registry.register_extension(extension)
        registry.register_tool(
            EXTENSION_ID, "CLASSIFY_DIFFICULTY", ClassifyDifficultyTool(self.catalog)
        )
        registry.register_tool(
            EXTENSION_ID, "SELECT_ALLOWED_HINT", SelectAllowedHintTool(self.catalog)
        )
        registry.register_tool(
            EXTENSION_ID, "RECORD_REOBSERVATION",
            ClassifyDifficultyTool(self.catalog, name="seasonlens.classify_revision")
        )
        actions = frozenset(extension._expected_stages)
        policy = AllowlistPolicy(
            allowed_actions={EXTENSION_ID: actions},
            auto_actions={
                EXTENSION_ID: frozenset(
                    {"CLASSIFY_DIFFICULTY", "SELECT_ALLOWED_HINT"}
                )
            },
        )
        self.runtime = Orchestrator(
            agent=RuleBasedSeasonLensAgent(),
            policy=policy,
            tools=registry,
            states=self.states,
            events=self.events,
            extensions=registry.extensions,
        )

    def create_session(self, participant_id: str, item_id: str = "demo_anemone_001", *,
                       study_mode: str = TRAINING_MODE, condition: str = CONDITION,
                       previous_session_id: str | None = None) -> dict[str, Any]:
        participant_id = participant_id.strip()
        if not participant_id:
            raise ValueError("participant_id is required.")
        if study_mode not in STUDY_MODES:
            raise ValueError("Choose training, unaided test, or transfer mode.")
        if condition not in CONDITIONS:
            raise ValueError("Choose a supported experimental condition.")
        item_id = self.catalog.canonical_id(item_id)
        self.catalog.get(item_id)
        session_id = str(uuid4())
        started_at = self.clock()
        state = StateSnapshot(
            extension_id=EXTENSION_ID,
            aggregate_id=session_id,
            version=0,
            data={
                "session_id": session_id,
                "participant_id": participant_id,
                "condition": condition,
                "study_mode": study_mode,
                "item_id": item_id,
                "session_started_at": started_at,
                "previous_session_id": previous_session_id,
                "item_started_at": started_at,
                "stage": SeasonLensStage.OBSERVE.value,
                "stage_transitions": [{"from": None, "to": "OBSERVE", "at": started_at}],
                "initial_attempt": None,
                "difficulty_code": None,
                "component_checks": None,
                "diagnostic": None,
                "revised_diagnostic": None,
                "revised_diagnostics": [],
                "hint_exposure": None,
                "positive_feedback": None,
                "hint_sequence": [],
                "researcher_notes": "",
                "revised_attempt": None,
                "revised_attempts": [],
                "participant_path": [],
                "expert_reveal_at": None,
                "reflection": None,
                "completed_at": None,
            },
        )
        self.states.snapshots[(EXTENSION_ID, session_id)] = state
        self.events.append(
            EventEnvelope(
                session_id=session_id,
                extension_id=EXTENSION_ID,
                aggregate_id=session_id,
                aggregate_version=0,
                actor=Actor(ActorType.SYSTEM, "seasonlens.api"),
                event_type="seasonlens.session-started",
                payload={
                    "participant_id": participant_id,
                    "condition": condition,
                    "study_mode": study_mode,
                    "item_id": item_id,
                },
                correlation_id=str(uuid4()),
            )
        )
        self._persist(session_id)
        return self.participant_projection(session_id)

    def _stage_fields(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.catalog.get(item_id)
        options = item.get("stage_options", [])
        if not options:
            return {
                "selected_stage_id": payload.get("selected_stage_id"),
                "interpretation_text": payload.get("interpretation_text", ""),
            }
        selected_stage_id = payload.get("selected_stage_id")
        option = next((entry for entry in options if entry["id"] == selected_stage_id), None)
        if option is None:
            raise ValueError("Choose one of this item's stage options.")
        return {
            "selected_stage_id": selected_stage_id,
            "interpretation_text": option["label"],
        }

    def submit_initial(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = str(self._state(session_id).data["item_id"])
        attempt = {
            "item_id": item_id,
            "selected_region": payload.get("selected_region"),
            "observation_text": payload.get("observation_text", ""),
            "confidence": payload.get("confidence"),
            "timestamp": self.clock(),
            **self._stage_fields(item_id, payload),
        }
        self._human_action(session_id, "RECORD_INITIAL_OBSERVATION", attempt)
        self._automatic_action(session_id, "CLASSIFY_DIFFICULTY")
        if self._state(session_id).data["study_mode"] == TRAINING_MODE:
            state = self._state(session_id)
            if state.data["difficulty_code"] == "CORRECT":
                shown_at = self.clock()
                item = self.catalog.get(str(state.data["item_id"]))
                self._system_action(session_id, "SHOW_POSITIVE_FEEDBACK", {
                    "text": item.get(
                        "correct_feedback",
                        "Correct. Your selected region, observation, and stage judgement are consistent with the expert answer.",
                    ),
                    "shown_at": shown_at,
                    "action_at": shown_at,
                })
            else:
                self._automatic_action(
                    session_id, "SELECT_ALLOWED_HINT", hint_shown_at=self.clock()
                )
        else:
            self._human_action(session_id, "BEGIN_UNAIDED_FINAL", {})
        self._persist(session_id)
        return self.participant_projection(session_id)

    def begin_reobservation(self, session_id: str) -> dict[str, Any]:
        self._human_action(session_id, "BEGIN_REOBSERVATION", {})
        self._persist(session_id)
        return self.participant_projection(session_id)

    def submit_revision(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = str(self._state(session_id).data["item_id"])
        revision = {
            "item_id": item_id,
            "selected_region": payload.get("selected_region"),
            "observation_text": payload.get("observation_text", ""),
            "revision_submitted_at": self.clock(),
            **self._stage_fields(item_id, payload),
        }
        self._human_action(session_id, "RECORD_REOBSERVATION", revision)
        state = self._state(session_id)
        current_error = state.data["revised_diagnostic"]["primary_error"]
        if (state.data["study_mode"] == TRAINING_MODE
                and state.data["condition"] == CONDITION
                and current_error != "CORRECT"):
            levels_for_error = [
                int(entry["hint_level"])
                for entry in state.data["hint_sequence"]
                if not entry.get("manual_override")
                and entry.get("error_type") == current_error
            ]
            if max(levels_for_error, default=0) < 3:
                self._automatic_action(
                    session_id, "SELECT_ALLOWED_HINT", hint_shown_at=self.clock()
                )
        self._persist(session_id)
        return self.participant_projection(session_id)

    def reveal_expert_cue(self, session_id: str) -> dict[str, Any]:
        if self._state(session_id).data["study_mode"] != TRAINING_MODE:
            raise ValueError("Expert reveal is not available in unaided test or transfer mode.")
        self._human_action(
            session_id, "REVEAL_EXPERT_CUE", {"expert_reveal_at": self.clock()}
        )
        self._persist(session_id)
        return self.participant_projection(session_id)

    def begin_reflection(self, session_id: str) -> dict[str, Any]:
        if self._state(session_id).data["study_mode"] != TRAINING_MODE:
            raise ValueError("Reflection is only available in training mode.")
        self._human_action(session_id, "BEGIN_REFLECTION", {})
        self._persist(session_id)
        return self.participant_projection(session_id)

    def submit_reflection(self, session_id: str, reflection_text: str,
                          reflection_category: str | None = None) -> dict[str, Any]:
        self._human_action(
            session_id,
            "RECORD_FEEDBACK_RESPONSE",
            {
                "reflection_text": reflection_text,
                "reflection_category": reflection_category or None,
                "reflection_submitted_at": self.clock(),
            },
        )
        self._persist(session_id)
        return self.participant_projection(session_id)

    def override_hint(self, session_id: str, hint_id: str) -> dict[str, Any]:
        state = self._state(session_id)
        if state.data["stage"] != SeasonLensStage.HINT.value:
            raise ValueError(f"OVERRIDE_AUTHORED_HINT requires HINT; current stage is {state.data['stage']}.")
        if state.data["study_mode"] != TRAINING_MODE or state.data["hint_exposure"] is None:
            raise ValueError("A corrective training hint must be active before it can be overridden.")
        hint = self.catalog.get_hint(str(state.data["item_id"]), hint_id)
        self._human_action(session_id, "OVERRIDE_AUTHORED_HINT", {"hint": hint}, researcher=True)
        self._persist(session_id)
        return self.participant_projection(session_id)

    def complete_unaided(self, session_id: str) -> dict[str, Any]:
        if self._state(session_id).data["study_mode"] == TRAINING_MODE:
            raise ValueError("Training sessions continue to reveal and reflection.")
        self._human_action(session_id, "COMPLETE_UNAIDED", {"completed_at": self.clock()})
        self._persist(session_id)
        return self.participant_projection(session_id)

    def save_researcher_notes(self, session_id: str, notes: str) -> dict[str, Any]:
        if not isinstance(notes, str):
            raise ValueError("Researcher notes must be text.")
        self._human_action(session_id, "RECORD_RESEARCHER_NOTE", {"researcher_notes": notes}, researcher=True)
        self._persist(session_id)
        return self.participant_projection(session_id)

    def researcher_projection(self, session_id: str) -> dict[str, Any]:
        log = self.export_study_log(session_id)
        return {"log": log, "hints": self.catalog.hint_library(str(log["item_id"])),
                "regions": self.catalog.researcher_regions(str(log["item_id"]))}

    def next_item(self, session_id: str) -> dict[str, Any]:
        state = self._state(session_id)
        if state.data["stage"] != SeasonLensStage.COMPLETE.value:
            raise ValueError("Complete this observation before moving to the next item.")
        item_ids = [item["item_id"] for item in self.catalog.list_items()]
        index = item_ids.index(state.data["item_id"])
        if index + 1 >= len(item_ids):
            raise ValueError("All demo items are complete. Start a new session to repeat them.")
        result = self.create_session(str(state.data["participant_id"]), item_ids[index + 1],
                                     study_mode=str(state.data["study_mode"]),
                                     condition=str(state.data["condition"]),
                                     previous_session_id=session_id)
        self._append_admin_event(session_id, "seasonlens.next-item-started",
                                 {"next_session_id": result["data"]["session_id"], "item_id": item_ids[index + 1]},
                                 researcher=False)
        return result

    def reset_item(self, session_id: str) -> dict[str, Any]:
        state = self._state(session_id)
        result = self.create_session(str(state.data["participant_id"]), str(state.data["item_id"]),
                                     study_mode=str(state.data["study_mode"]),
                                     condition=str(state.data["condition"]),
                                     previous_session_id=session_id)
        self._append_admin_event(session_id, "seasonlens.demo-reset",
                                 {"replacement_session_id": result["data"]["session_id"]})
        return result

    def _append_admin_event(self, session_id: str, event_type: str, payload: dict[str, Any], *,
                            researcher: bool = True) -> None:
        state = self._state(session_id)
        self.events.append(EventEnvelope(
            session_id=session_id, extension_id=EXTENSION_ID, aggregate_id=session_id,
            aggregate_version=state.version, actor=Actor(ActorType.HUMAN,
                "seasonlens.researcher" if researcher else str(state.data["participant_id"])),
            event_type=event_type, payload={**payload, "action_at": self.clock()}, correlation_id=str(uuid4())))
        self._persist(session_id)

    def participant_projection(self, session_id: str) -> dict[str, Any]:
        state = self._state(session_id)
        data = state.data
        projection: dict[str, Any] = {
            "extension_id": EXTENSION_ID,
            "aggregate_id": session_id,
            "state_version": state.version,
            "projection_type": "field-observation-flow",
            "data": {
                "session_id": session_id,
                "participant_id": data["participant_id"],
                "condition": data["condition"],
                "study_mode": data["study_mode"],
                "stage": data["stage"],
                "item": self.catalog.participant_view(str(data["item_id"])),
                "initial_attempt": data["initial_attempt"],
                "revised_attempt": data["revised_attempt"],
                "hint": ({key: data["hint_exposure"][key] for key in
                          ("hint_id", "hint_level", "hint_text", "hint_shown_at")}
                         if data["hint_exposure"] else None),
                "positive_feedback": deepcopy(data["positive_feedback"]),
                "hint_received": bool(data["hint_sequence"]),
                "reflection": data["reflection"],
                "has_next_item": str(data["item_id"]) != self.catalog.list_items()[-1]["item_id"],
            },
        }
        if (data["expert_reveal_at"] is not None or
                (data["study_mode"] == TRAINING_MODE and data["condition"] == ANSWER_FIRST)):
            projection["data"]["expert_reveal"] = self.catalog.expert_view(
                str(data["item_id"])
            )
        return deepcopy(projection)

    def export_study_log(self, session_id: str) -> dict[str, Any]:
        state = self._state(session_id)
        data = state.data
        initial = data["initial_attempt"] or {}
        revised = data["revised_attempt"] or {}
        hint = data["hint_exposure"] or {}
        reflection = data["reflection"] or {}
        diagnostic = data["diagnostic"] or {}
        revised_diagnostic = data["revised_diagnostic"] or {}
        item = self.catalog.get(str(data["item_id"]))
        correct_stage_id = item.get("correct_stage_id")
        correct_stage_label = next(
            (option["label"] for option in item.get("stage_options", [])
             if option["id"] == correct_stage_id),
            None,
        )
        self_corrected = (None if not revised_diagnostic else
                          diagnostic.get("primary_error") not in (None, "CORRECT") and
                          revised_diagnostic.get("primary_error") == "CORRECT")
        positive_feedback = data["positive_feedback"] or {}
        current_diagnostic = revised_diagnostic or diagnostic
        final_correctness = (
            None if not current_diagnostic else
            current_diagnostic.get("primary_error") == "CORRECT"
        )
        reflection_type = (
            "hint_reflection" if data["hint_sequence"] else "no_hint_reflection"
        )
        start = datetime.fromisoformat(str(data["session_started_at"]))
        end_value = data["completed_at"] or self.clock()
        end = datetime.fromisoformat(str(end_value))
        matching_events = [
            self._event_dict(event)
            for event in self.events.events
            if event.session_id == session_id
        ]
        return deepcopy({
            "session_id": session_id,
            "participant_id": data["participant_id"],
            "condition": data["condition"],
            "study_mode": data["study_mode"],
            "guidance_strategy": (
                "none-unaided" if data["study_mode"] != TRAINING_MODE else
                "answer-first" if data["condition"] == ANSWER_FIRST else
                "yoked-non-contingent-planned-not-fully-implemented" if data["condition"] == YOKED_NON_CONTINGENT else
                "error-contingent-adaptive"
            ),
            "item_id": data["item_id"],
            "plant_name": self.catalog.get(str(data["item_id"]))["plant_name"],
            "cue_family": self.catalog.get(str(data["item_id"]))["cue_family"],
            "state_version": state.version,
            "item_definition_checksum": self.catalog.checksum(str(data["item_id"])),
            "stage": data["stage"],
            "session_started_at": data["session_started_at"],
            "previous_session_id": data["previous_session_id"],
            "item_started_at": data["item_started_at"],
            "stage_transitions": deepcopy(data["stage_transitions"]),
            "diagnostic": deepcopy(data["diagnostic"]),
            "initial_diagnostic": deepcopy(data["diagnostic"]),
            "initial_correctness": diagnostic.get("primary_error") == "CORRECT" if diagnostic else None,
            "revised_diagnostic": deepcopy(data["revised_diagnostic"]),
            "selected_semantic_region": diagnostic.get("selected_semantic_region"),
            "selected_region_label": diagnostic.get("selected_region_label"),
            "target_region_id": diagnostic.get("target_region_id"),
            "target_region_iou": diagnostic.get("target_iou"),
            "best_distractor_iou": diagnostic.get("best_distractor_iou"),
            "initial_selected_semantic_region": diagnostic.get("selected_semantic_region"),
            "revised_selected_semantic_region": revised_diagnostic.get("selected_semantic_region"),
            "revised_selected_region_label": revised_diagnostic.get("selected_region_label"),
            "revised_target_region_iou": revised_diagnostic.get("target_iou"),
            "revised_best_distractor_iou": revised_diagnostic.get("best_distractor_iou"),
            "region_correct": diagnostic.get("region_correct"),
            "cue_correct": diagnostic.get("cue_correct"),
            "interpretation_correct": diagnostic.get("interpretation_correct"),
            "primary_error": diagnostic.get("primary_error"),
            "diagnostic_reason": diagnostic_reason(diagnostic),
            "initial_response": deepcopy(initial) if initial else None,
            "initial_region": initial.get("selected_region"),
            "initial_region_iou": diagnostic.get("target_iou"),
            "initial_region_correct": diagnostic.get("region_correct"),
            "initial_observation": initial.get("observation_text"),
            "initial_cue_correct": diagnostic.get("cue_correct"),
            "initial_interpretation": initial.get("interpretation_text"),
            "initial_stage_id": initial.get("selected_stage_id"),
            "initial_stage": initial.get("selected_stage_id"),
            "initial_stage_correct": diagnostic.get("stage_correct"),
            "initial_confidence": initial.get("confidence"),
            "initial_submitted_at": initial.get("timestamp"),
            "difficulty_code": data["difficulty_code"],
            "hint_id": hint.get("hint_id"),
            "hint_received": bool(data["hint_sequence"]),
            "automatic_hint_id": hint.get("automatic_hint_id"),
            "region_hint_source": hint.get("region_hint_source"),
            "region_hint_id": hint.get("region_hint_id"),
            "automatic_region_hint_source": hint.get("automatic_region_hint_source"),
            "automatic_region_hint_id": hint.get("automatic_region_hint_id"),
            "actual_hint_id": hint.get("actual_hint_id"),
            "manual_override": hint.get("manual_override", False),
            "hint_type": hint.get("hint_type"),
            "hint_error_type": hint.get("error_type"),
            "hint_provenance": hint.get("hint_provenance"),
            "hint_sequence": deepcopy(data["hint_sequence"]),
            "hint_level": hint.get("hint_level"),
            "hint_text": hint.get("hint_text"),
            "hint_shown_at": hint.get("hint_shown_at"),
            "hint_trigger_reason": (
                "Fixed non-contingent placeholder guidance for Group B."
                if hint and data["condition"] == YOKED_NON_CONTINGENT
                else diagnostic_reason(diagnostic) if hint else None
            ),
            "positive_feedback_shown": bool(positive_feedback),
            "positive_feedback_text": positive_feedback.get("text"),
            "positive_feedback_shown_at": positive_feedback.get("shown_at"),
            "revised_region": revised.get("selected_region"),
            "revised_observation": revised.get("observation_text"),
            "revised_interpretation": revised.get("interpretation_text"),
            "revised_stage_id": revised.get("selected_stage_id"),
            "revised_stage": revised.get("selected_stage_id"),
            "revised_stage_correct": revised_diagnostic.get("stage_correct"),
            "revised_response": deepcopy(revised) if revised else None,
            "revised_attempts": deepcopy(data["revised_attempts"]),
            "revised_diagnostics": deepcopy(data["revised_diagnostics"]),
            "final_correctness": final_correctness,
            "participant_path": " → ".join(data["participant_path"]),
            "correct_stage_id": correct_stage_id,
            "correct_stage_label": correct_stage_label,
            "revision_submitted_at": revised.get("revision_submitted_at"),
            "self_corrected": self_corrected,
            "self_corrected_after_hint": self_corrected if hint else None,
            "expert_reveal_at": data["expert_reveal_at"],
            "reveal_at": data["expert_reveal_at"],
            "reflection_text": reflection.get("reflection_text"),
            "reflection_type": reflection_type,
            "reflection_category": reflection.get("reflection_category"),
            "reflection_submitted_at": reflection.get("reflection_submitted_at"),
            "researcher_notes": data["researcher_notes"],
            "item_completed_at": data["completed_at"],
            "total_session_time": round((end - start).total_seconds(), 3),
            "timings": {
                "session_started_at": data["session_started_at"],
                "initial_submitted_at": initial.get("timestamp"),
                "hint_shown_at": hint.get("hint_shown_at"),
                "revision_submitted_at": revised.get("revision_submitted_at"),
                "reveal_at": data["expert_reveal_at"],
                "reflection_submitted_at": reflection.get("reflection_submitted_at"),
                "item_completed_at": data["completed_at"],
                "total_session_time": round((end - start).total_seconds(), 3),
            },
            "events": matching_events,
        })

    def export_study_csv(self, session_id: str) -> str:
        log = self.export_study_log(session_id)
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=list(log))
        writer.writeheader()
        row = {}
        for key, value in log.items():
            text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else ("" if value is None else str(value))
            # Keep free text literal when opened in spreadsheet software.
            row[key] = "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
        writer.writerow(row)
        return output.getvalue()

    def _state(self, session_id: str) -> StateSnapshot:
        try:
            return self.states.get(EXTENSION_ID, session_id)
        except KeyError as error:
            raise ValueError(f"Unknown session: {session_id}") from error

    def _human_action(
        self, session_id: str, action_type: str, payload: dict[str, Any], *, researcher: bool = False
    ) -> None:
        state = self._state(session_id)
        actor = Actor(ActorType.HUMAN, "seasonlens.researcher" if researcher else str(state.data["participant_id"]))
        proposal = ActionProposal(
            extension_id=EXTENSION_ID,
            action_type=action_type,
            actor=actor,
            payload={**deepcopy(payload), "action_at": next((payload[key] for key in
                     ("timestamp", "revision_submitted_at", "expert_reveal_at", "reflection_submitted_at")
                     if key in payload), None) or self.clock()},
            expected_state_version=state.version,
            requires_confirmation=True,
        )
        intent = UserIntent(
            session_id=session_id,
            extension_id=EXTENSION_ID,
            actor=actor,
            ui_event={"action": action_type},
        )
        self.runtime.execute_approved(
            intent=intent, aggregate_id=session_id, proposal=proposal
        )

    def _automatic_action(self, session_id: str, action_type: str, **extra: Any) -> None:
        intent = UserIntent(
            session_id=session_id,
            extension_id=EXTENSION_ID,
            actor=Actor(ActorType.SYSTEM, "seasonlens.rule-policy-v1"),
            ui_event={"next_action": action_type, "action_at": extra.get("hint_shown_at") or self.clock(), **extra},
        )
        outcomes = self.runtime.propose(intent, session_id)
        if len(outcomes) != 1 or outcomes[0].state is None:
            raise RuntimeError(f"Automatic action did not execute: {action_type}")

    def _system_action(self, session_id: str, action_type: str, payload: dict[str, Any]) -> None:
        state = self._state(session_id)
        actor = Actor(ActorType.SYSTEM, "seasonlens.rule-policy-v1")
        proposal = ActionProposal(
            extension_id=EXTENSION_ID,
            action_type=action_type,
            actor=actor,
            payload=deepcopy(payload),
            expected_state_version=state.version,
            requires_confirmation=False,
        )
        intent = UserIntent(
            session_id=session_id,
            extension_id=EXTENSION_ID,
            actor=actor,
            ui_event={"action": action_type},
        )
        self.runtime.execute_approved(
            intent=intent, aggregate_id=session_id, proposal=proposal
        )

    @staticmethod
    def _event_dict(event: EventEnvelope) -> dict[str, Any]:
        value = asdict(event)
        value["recorded_at"] = event.recorded_at.isoformat()
        value["actor"]["actor_type"] = event.actor.actor_type.value
        return value

    def _persist(self, session_id: str) -> None:
        if self.export_directory is None:
            return
        self.export_directory.mkdir(parents=True, exist_ok=True)
        target = self.export_directory / f"{session_id}.json"
        target.write_text(
            json.dumps(self.export_study_log(session_id), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
