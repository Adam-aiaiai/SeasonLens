import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import csv
import io

from seasonlens import SeasonLensService


class Clock:
    def __init__(self) -> None:
        self.tick = 0

    def __call__(self) -> str:
        self.tick += 1
        return (datetime(2026, 9, 16, tzinfo=timezone.utc) + timedelta(seconds=self.tick)).isoformat()


class FlowTests(unittest.TestCase):
    def test_complete_flow_preserves_initial_attempt_and_exports_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export_directory = Path(directory)
            service = SeasonLensService(export_directory=export_directory, clock=Clock())
            created = service.create_session("participant-001")
            session_id = created["data"]["session_id"]
            hinted = service.submit_initial(session_id, {
                "selected_region": {"x": 0.2, "y": 0.7, "width": 0.1, "height": 0.1},
                "observation_text": "I see a branch.",
                "selected_stage_id": "not_sure",
                "visual_evidence_reason": "The branch shape made me unsure.",
                "judgement_source": "image_evidence",
                "confidence": 2,
            })
            self.assertEqual(hinted["data"]["stage"], "HINT")
            self.assertNotIn("difficulty_code", hinted["data"])
            self.assertEqual(hinted["data"]["hint"]["hint_id"], "demo_anemone_region_01")
            service.begin_reobservation(session_id)
            service.submit_revision(session_id, {
                "selected_region": {"x": 0.31, "y": 0.07, "width": 0.11, "height": 0.2},
                "observation_text": "Several rounded flower buds remain closed.",
                "selected_stage_id": "flower_buds_present",
            })
            revealed = service.reveal_expert_cue(session_id)
            self.assertEqual(revealed["data"]["stage"], "REVEAL")
            self.assertEqual(revealed["data"]["expert_reveal"]["diagnostic_cue"],
                             "叶片上方可见几个圆形花蕾，花瓣尚未开放。")
            service.begin_reflection(session_id)
            completed = service.submit_reflection(session_id, "I changed from the whole branch to its terminal bud.", "Where I looked")
            self.assertEqual(completed["data"]["stage"], "COMPLETE")
            log = service.export_study_log(session_id)
            self.assertEqual(log["initial_region"], {"x": 0.2, "y": 0.7, "width": 0.1, "height": 0.1})
            self.assertEqual(log["revised_region"], {"x": 0.31, "y": 0.07, "width": 0.11, "height": 0.2})
            self.assertEqual(log["difficulty_code"], "REGION_MISS")
            self.assertEqual(log["condition"], "observation-first-contingent")
            self.assertEqual(log["participant_id"], "participant-001")
            self.assertEqual(log["plant_name"], "弗吉尼亚银莲花（Anemone virginiana）")
            self.assertEqual(log["cue_family"], "花蕾")
            self.assertEqual(log["initial_visual_evidence_reason"], "The branch shape made me unsure.")
            self.assertEqual(log["initial_judgement_source"], "image_evidence")
            self.assertEqual(log["initial_stage_id"], "not_sure")
            self.assertEqual(log["revised_stage_id"], "flower_buds_present")
            self.assertEqual(log["correct_stage_id"], "flower_buds_present")
            self.assertFalse(log["initial_stage_correct"])
            self.assertTrue(log["revised_stage_correct"])
            self.assertEqual(log["initial_region_iou"], log["target_region_iou"])
            self.assertEqual(log["initial_region_correct"], log["region_correct"])
            self.assertEqual(log["initial_cue_correct"], log["cue_correct"])
            self.assertTrue(log["hint_received"])
            self.assertEqual(log["hint_error_type"], "REGION_MISS")
            self.assertIsNotNone(log["hint_provenance"])
            self.assertGreater(log["total_session_time"], 0)
            self.assertEqual(len(log["events"]), 11)
            saved = json.loads((export_directory / f"{session_id}.json").read_text(encoding="utf-8"))
            self.assertTrue(saved["reflection_text"].startswith("I changed"))
            self.assertEqual(saved["reflection_category"], "Where I looked")
            for key in ["item_started_at", "initial_submitted_at", "hint_shown_at", "revision_submitted_at",
                        "reveal_at", "reflection_submitted_at", "item_completed_at"]:
                self.assertIsNotNone(saved[key])
            self.assertEqual([entry["to"] for entry in saved["stage_transitions"]],
                             ["OBSERVE", "INITIAL_COMMITTED", "HINT", "REOBSERVE", "REVISED_COMMITTED", "REVEAL", "REFLECTION", "COMPLETE"])

    def test_invalid_transition_and_initial_overwrite_are_rejected(self) -> None:
        service = SeasonLensService(clock=Clock())
        created = service.create_session("participant-002")
        session_id = created["data"]["session_id"]
        with self.assertRaisesRegex(ValueError, "requires POSITIVE_FEEDBACK or REVISED_COMMITTED"):
            service.reveal_expert_cue(session_id)
        initial = {
            "selected_region": {"x": 0.31, "y": 0.07, "width": 0.11, "height": 0.2},
            "observation_text": "rounded closed flower buds",
            "selected_stage_id": "flower_buds_present",
            "visual_evidence_reason": "The rounded structures look closed.",
            "judgement_source": "image_evidence",
            "confidence": 5,
        }
        service.submit_initial(session_id, initial)
        with self.assertRaisesRegex(ValueError, "requires OBSERVE"):
            service.submit_initial(session_id, initial)


class FormativeStudyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SeasonLensService(clock=Clock())
        self.session_id = self.service.create_session("study-participant")["data"]["session_id"]
        self.initial = {
            "selected_region": {"x": 0.31, "y": 0.07, "width": 0.11, "height": 0.2},
            "observation_text": "rounded closed flower buds", "selected_stage_id": "flower_buds_present", "confidence": 4,
            "visual_evidence_reason": "The visible rounded buds are still closed.",
            "judgement_source": "image_evidence",
        }

    def complete(self) -> None:
        self.service.submit_initial(self.session_id, self.initial)
        self.service.reveal_expert_cue(self.session_id)
        self.service.begin_reflection(self.session_id)
        self.service.submit_reflection(self.session_id, "I checked the bud again.")

    def test_initial_response_cannot_be_mutated_by_caller_or_projection(self) -> None:
        projection = self.service.submit_initial(self.session_id, self.initial)
        self.initial["selected_region"]["x"] = 0
        self.initial["visual_evidence_reason"] = "overwritten by caller"
        projection["data"]["initial_attempt"]["observation_text"] = "overwritten"
        projection["data"]["initial_attempt"]["judgement_source"] = "guessing"
        log = self.service.export_study_log(self.session_id)
        log["initial_region"]["x"] = 0
        preserved = self.service.export_study_log(self.session_id)
        self.assertEqual(preserved["initial_region"]["x"], 0.31)
        self.assertEqual(preserved["initial_observation"], "rounded closed flower buds")
        self.assertEqual(preserved["initial_visual_evidence_reason"],
                         "The visible rounded buds are still closed.")
        self.assertEqual(preserved["initial_judgement_source"], "image_evidence")

    def test_fully_correct_response_shows_positive_confirmation(self) -> None:
        projection = self.service.submit_initial(self.session_id, self.initial)
        self.assertEqual(projection["data"]["stage"], "POSITIVE_FEEDBACK")
        self.assertIsNone(projection["data"]["hint"])
        self.assertEqual(projection["data"]["positive_feedback"]["text"],
                         "很好。你选择的可见证据与当前阶段一致。")
        log = self.service.export_study_log(self.session_id)
        self.assertTrue(log["region_correct"])
        self.assertTrue(log["interpretation_correct"])
        self.assertIsNone(log["hint_text"])
        self.assertIsNone(log["hint_type"])
        self.assertIsNone(log["hint_level"])
        self.assertTrue(log["positive_feedback_shown"])
        self.assertEqual(log["positive_feedback_text"],
                         "很好。你选择的可见证据与当前阶段一致。")
        self.assertFalse(log["hint_received"])
        self.assertIsNone(log["revised_response"])
        self.assertEqual(log["participant_path"], "INITIAL_CORRECT")
        self.assertIsNone(log["hint_id"])
        self.assertIsNone(log["hint_level"])

    def test_no_hint_reflection_omits_hint_learning_answer_without_validation(self) -> None:
        self.service.submit_initial(self.session_id, self.initial)
        self.service.reveal_expert_cue(self.session_id)
        self.service.begin_reflection(self.session_id)
        completed = self.service.submit_reflection(
            self.session_id, reflection_category="My confidence"
        )
        self.assertEqual(completed["data"]["stage"], "COMPLETE")
        log = self.service.export_study_log(self.session_id)
        self.assertFalse(log["hint_received"])
        self.assertIsNone(log["hint_learning_reflection"])
        self.assertIsNone(log["reflection_text"])
        self.assertEqual(log["reflection_category"], "My confidence")
        row = next(csv.DictReader(io.StringIO(self.service.export_study_csv(self.session_id))))
        self.assertEqual(row["hint_learning_reflection"], "")

    def test_hint_learning_reflection_persists_after_correct_or_incorrect_revision(self) -> None:
        cases = [("observation-first-contingent", True), ("observation-first-yoked", False)]
        for condition, revised_correct in cases:
            with self.subTest(revised_correct=revised_correct):
                service = SeasonLensService(clock=Clock())
                session_id = service.create_session(
                    f"hint-reflection-{revised_correct}", condition=condition
                )["data"]["session_id"]
                initial = dict(
                    self.initial,
                    selected_region={"x": 0.25, "y": 0.58, "width": 0.5, "height": 0.39},
                    observation_text="只看到叶片",
                    selected_stage_id="not_sure",
                )
                hinted = service.submit_initial(session_id, initial)
                self.assertTrue(hinted["data"]["hint_received"])
                service.begin_reobservation(session_id)
                revision = (self.initial if revised_correct else dict(
                    self.initial, observation_text="仍然只看到叶片", selected_stage_id="fruiting"
                ))
                revised = service.submit_revision(session_id, revision)
                self.assertEqual(revised["data"]["stage"], "REVISED_COMMITTED")
                service.reveal_expert_cue(session_id)
                service.begin_reflection(session_id)
                with self.assertRaisesRegex(ValueError, "Hint-learning reflection is required"):
                    service.submit_reflection(session_id)
                answer = "提示让我注意到之前忽略的花蕾。"
                completed = service.submit_reflection(
                    session_id, hint_learning_reflection=answer
                )
                self.assertEqual(completed["data"]["stage"], "COMPLETE")
                log = service.export_study_log(session_id)
                self.assertTrue(log["hint_received"])
                self.assertEqual(log["hint_learning_reflection"], answer)
                self.assertEqual(log["reflection_text"], answer)
                self.assertEqual(log["events"][-1]["payload"]["reflection"]["hint_learning_reflection"], answer)
                row = next(csv.DictReader(io.StringIO(service.export_study_csv(session_id))))
                self.assertEqual(row["hint_learning_reflection"], answer)

    def test_partial_answers_keep_existing_corrective_hints(self) -> None:
        cases = [
            (dict(self.initial, selected_region={"x": 0.2, "y": 0.7, "width": 0.1, "height": 0.1}),
             "demo_anemone_region_01"),
            (dict(self.initial, selected_stage_id="fruiting"), "demo_anemone_stage_01"),
            (dict(self.initial, observation_text="a green shape"), "demo_anemone_feature_01"),
        ]
        for initial, expected_hint_id in cases:
            with self.subTest(expected_hint_id=expected_hint_id):
                service = SeasonLensService(clock=Clock())
                session_id = service.create_session("partial-answer")["data"]["session_id"]
                projection = service.submit_initial(session_id, initial)
                self.assertEqual(projection["data"]["hint"]["hint_id"], expected_hint_id)
                self.assertNotEqual(projection["data"]["hint"]["hint_text"], "Correct answer!")

    def test_unaided_and_transfer_modes_skip_guidance_reveal_and_reflection(self) -> None:
        for mode in ["unaided_test", "transfer"]:
            with self.subTest(mode=mode):
                service = SeasonLensService(clock=Clock())
                created = service.create_session("independent", study_mode=mode)
                session_id = created["data"]["session_id"]
                projection = service.submit_initial(session_id, self.initial)
                self.assertEqual(projection["data"]["stage"], "REOBSERVE")
                self.assertIsNone(projection["data"]["hint"])
                self.assertIsNone(projection["data"]["positive_feedback"])
                self.assertNotIn("expert_reveal", projection["data"])
                service.submit_revision(session_id, self.initial)
                with self.assertRaises(ValueError):
                    service.reveal_expert_cue(session_id)
                completed = service.complete_unaided(session_id)
                self.assertEqual(completed["data"]["stage"], "COMPLETE")
                log = service.export_study_log(session_id)
                self.assertEqual(log["study_mode"], mode)
                self.assertIsNone(log["hint_text"])

    def test_experimental_conditions_are_visible_and_select_guidance_strategy(self) -> None:
        answer_first = SeasonLensService(clock=Clock()).create_session(
            "group-a", condition="answer-first"
        )
        self.assertIn("expert_reveal", answer_first["data"])

        wrong_region = dict(
            self.initial,
            selected_region={"x": 0.2, "y": 0.7, "width": 0.1, "height": 0.1},
        )
        yoked = SeasonLensService(clock=Clock())
        yoked_id = yoked.create_session(
            "group-b", condition="observation-first-yoked"
        )["data"]["session_id"]
        yoked_projection = yoked.submit_initial(yoked_id, wrong_region)
        self.assertEqual(yoked_projection["data"]["hint"]["hint_id"], "demo_anemone_feature_01")
        self.assertIn("non-contingent", yoked.export_study_log(yoked_id)["hint_trigger_reason"])

        adaptive = SeasonLensService(clock=Clock())
        adaptive_id = adaptive.create_session(
            "group-c", condition="observation-first-contingent"
        )["data"]["session_id"]
        adaptive_projection = adaptive.submit_initial(adaptive_id, wrong_region)
        self.assertEqual(adaptive_projection["data"]["hint"]["hint_id"], "demo_anemone_region_01")

    def test_log_records_self_correction_after_guidance(self) -> None:
        initial = dict(self.initial, selected_stage_id="fruiting")
        self.service.submit_initial(self.session_id, initial)
        self.service.begin_reobservation(self.session_id)
        self.service.submit_revision(self.session_id, self.initial)
        log = self.service.export_study_log(self.session_id)
        self.assertTrue(log["self_corrected"])
        self.assertTrue(log["self_corrected_after_hint"])

    def test_adaptive_hints_escalate_to_level_three_then_stop(self) -> None:
        wrong = dict(
            self.initial,
            selected_region={"x": 0.25, "y": 0.58, "width": 0.5, "height": 0.39},
            observation_text="large leaves",
            selected_stage_id="fruiting",
        )
        projection = self.service.submit_initial(self.session_id, wrong)
        self.assertEqual(projection["data"]["hint"]["hint_level"], 1)
        for expected_level in (2, 3):
            self.service.begin_reobservation(self.session_id)
            projection = self.service.submit_revision(self.session_id, wrong)
            self.assertEqual(projection["data"]["stage"], "HINT")
            self.assertEqual(projection["data"]["hint"]["hint_level"], expected_level)
        self.service.begin_reobservation(self.session_id)
        projection = self.service.submit_revision(self.session_id, wrong)
        self.assertEqual(projection["data"]["stage"], "REVISED_COMMITTED")
        log = self.service.export_study_log(self.session_id)
        self.assertEqual([entry["hint_level"] for entry in log["hint_sequence"]], [1, 2, 3])
        self.assertEqual(log["participant_path"],
                         "REGION_MISS → L1 → REGION_MISS → L2 → REGION_MISS → L3 → REGION_MISS")
        self.assertFalse(log["final_correctness"])

    def test_changed_error_type_restarts_at_level_one_and_correct_stops_loop(self) -> None:
        leaf = dict(
            self.initial,
            selected_region={"x": 0.25, "y": 0.58, "width": 0.5, "height": 0.39},
        )
        self.service.submit_initial(self.session_id, leaf)
        self.service.begin_reobservation(self.session_id)
        stage_wrong = dict(self.initial, selected_stage_id="fruiting")
        projection = self.service.submit_revision(self.session_id, stage_wrong)
        self.assertEqual(projection["data"]["hint"]["hint_id"], "demo_anemone_stage_01")
        self.assertEqual(projection["data"]["hint"]["hint_level"], 1)
        self.service.begin_reobservation(self.session_id)
        projection = self.service.submit_revision(self.session_id, self.initial)
        self.assertEqual(projection["data"]["stage"], "REVISED_COMMITTED")
        log = self.service.export_study_log(self.session_id)
        self.assertEqual(log["participant_path"],
                         "REGION_MISS → L1 → INTERPRETATION_ERROR → L1 → CORRECT")
        self.assertTrue(log["final_correctness"])

    def test_manual_override_preserves_diagnostic_and_automatic_hint(self) -> None:
        self.service.submit_initial(self.session_id, dict(self.initial, observation_text="a brown shape"))
        automatic = self.service.export_study_log(self.session_id)
        overridden = self.service.override_hint(self.session_id, "demo_anemone_region_02")
        log = self.service.export_study_log(self.session_id)
        self.assertEqual(log["diagnostic"], automatic["diagnostic"])
        self.assertEqual(log["automatic_hint_id"], "demo_anemone_feature_01")
        self.assertEqual(log["actual_hint_id"], "demo_anemone_region_02")
        self.assertTrue(log["manual_override"])
        self.assertEqual(log["hint_level"], 2)
        self.assertEqual(log["hint_type"], "region_directing")
        self.assertEqual(len(log["hint_sequence"]), 2)
        self.assertFalse(log["hint_sequence"][0]["manual_override"])
        self.assertEqual(log["events"][-1]["actor"]["actor_id"], "seasonlens.researcher")
        self.assertEqual(overridden["data"]["hint"]["hint_level"], 2)
        self.service.override_hint(self.session_id, "demo_anemone_feature_01")
        self.assertEqual(len(self.service.export_study_log(self.session_id)["hint_sequence"]), 3)

    def test_override_rejects_unknown_cross_item_hints_and_wrong_stage(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires HINT"):
            self.service.override_hint(self.session_id, "demo_anemone_region_02")
        self.service.submit_initial(self.session_id, dict(self.initial, observation_text="a brown shape"))
        before = self.service.export_study_log(self.session_id)
        for hint_id in ["not-authored", "demo_solidago_region_01"]:
            with self.assertRaises(ValueError):
                self.service.override_hint(self.session_id, hint_id)
        self.assertEqual(self.service.export_study_log(self.session_id)["hint_sequence"], before["hint_sequence"])
        self.service.begin_reobservation(self.session_id)
        with self.assertRaisesRegex(ValueError, "requires HINT"):
            self.service.override_hint(self.session_id, "demo_anemone_region_02")

    def test_participant_projection_hides_research_data_and_codes(self) -> None:
        self.service.submit_initial(self.session_id, dict(self.initial, observation_text="a branch"))
        self.service.save_researcher_notes(self.session_id, "Private study note")
        for stage in ["HINT", "REOBSERVE", "REVISED_COMMITTED", "REVEAL", "REFLECTION", "COMPLETE"]:
            projection = self.service.participant_projection(self.session_id)
            serialized = json.dumps(projection)
            for secret in ["CUE_MISIDENTIFIED", "REGION_MISS", "INTERPRETATION_ERROR", "CORRECT",
                           '"diagnostic":', "primary_error", "region_correct", "accepted_cue_keywords",
                           "region_iou_threshold", "researcher_notes", "Private study note", "manual_override",
                           "automatic_hint_id", "hint_sequence"]:
                self.assertNotIn(secret, serialized)
            if stage in {"HINT", "REOBSERVE", "REVISED_COMMITTED"}:
                self.assertNotIn("target_region", serialized)
                self.assertNotIn("expert_reveal", serialized)
            if stage == "HINT": self.service.begin_reobservation(self.session_id)
            elif stage == "REOBSERVE": self.service.submit_revision(self.session_id, self.initial)
            elif stage == "REVISED_COMMITTED": self.service.reveal_expert_cue(self.session_id)
            elif stage == "REVEAL": self.service.begin_reflection(self.session_id)
            elif stage == "REFLECTION": self.service.submit_reflection(self.session_id, "I checked again.")

    def test_notes_are_separate_and_edits_have_append_only_events(self) -> None:
        self.service.save_researcher_notes(self.session_id, "First note")
        self.service.save_researcher_notes(self.session_id, "Revised note")
        log = self.service.export_study_log(self.session_id)
        self.assertEqual(log["researcher_notes"], "Revised note")
        self.assertIsNone(log["initial_observation"])
        notes = [event for event in log["events"] if event["event_type"] == "seasonlens.researcher-note-recorded"]
        self.assertEqual([event["payload"]["researcher_notes"] for event in notes], ["First note", "Revised note"])

    def test_next_item_links_sessions_and_keeps_completed_log(self) -> None:
        with self.assertRaises(ValueError): self.service.next_item(self.session_id)
        self.complete()
        before = self.service.export_study_log(self.session_id)
        next_projection = self.service.next_item(self.session_id)
        self.assertEqual(next_projection["data"]["item"]["item_id"], "demo_solidago_001")
        self.assertEqual(next_projection["data"]["participant_id"], "study-participant")
        self.assertTrue(next_projection["data"]["has_next_item"])
        self.assertIsNone(next_projection["data"]["initial_attempt"])
        after = self.service.export_study_log(self.session_id)
        self.assertEqual(after["initial_observation"], before["initial_observation"])
        self.assertEqual(after["events"][:-1], before["events"])
        self.assertEqual(after["events"][-1]["actor"]["actor_id"], "study-participant")
        self.assertEqual(self.service.export_study_log(next_projection["data"]["session_id"])["previous_session_id"], self.session_id)

    def test_new_plant_items_complete_the_training_flow(self) -> None:
        cases = {
            "demo_solidago_001": ("顶部有开放的黄色花朵", "flowering"),
            "demo_anemone_001": ("茎尖有圆形花蕾", "flower_buds_present"),
            "demo_butterfly_weed_001": (
                "花簇中有开放的橙色花和未开放的花蕾",
                "active_flowering_with_unopened_buds",
            ),
        }
        for item_id, (observation, stage_id) in cases.items():
            with self.subTest(item_id=item_id):
                service = SeasonLensService(clock=Clock())
                created = service.create_session("new-item-flow", item_id)
                session_id = created["data"]["session_id"]
                item = service.catalog.get(item_id)
                response = {
                    "selected_region": item["target_region"]["rect"],
                    "observation_text": observation,
                    "selected_stage_id": stage_id,
                    "visual_evidence_reason": "Visible reproductive structures support this choice.",
                    "judgement_source": "image_evidence",
                    "confidence": 4,
                }
                confirmed = service.submit_initial(session_id, response)
                self.assertEqual(confirmed["data"]["stage"], "POSITIVE_FEEDBACK")
                self.assertIsNone(confirmed["data"]["hint"])
                revealed = service.reveal_expert_cue(session_id)
                self.assertEqual(revealed["data"]["expert_reveal"]["target_region"], item["target_region"]["rect"])
                service.begin_reflection(session_id)
                completed = service.submit_reflection(session_id, "I checked the visible reproductive structures.")
                self.assertEqual(completed["data"]["stage"], "COMPLETE")
                log = service.export_study_log(session_id)
                self.assertEqual(log["item_id"], item_id)
                self.assertAlmostEqual(log["target_region_iou"], 1)
                self.assertIsNone(log["revised_target_region_iou"])

    def test_reset_creates_fresh_session_and_retains_original_audit(self) -> None:
        self.service.submit_initial(self.session_id, self.initial)
        self.service.save_researcher_notes(self.session_id, "Keep this note in old log")
        before = self.service.export_study_log(self.session_id)
        fresh = self.service.reset_item(self.session_id)
        self.assertNotEqual(fresh["data"]["session_id"], self.session_id)
        self.assertEqual(fresh["data"]["stage"], "OBSERVE")
        self.assertIsNone(fresh["data"]["initial_attempt"])
        old = self.service.export_study_log(self.session_id)
        self.assertEqual(old["initial_observation"], "rounded closed flower buds")
        self.assertEqual(old["researcher_notes"], "Keep this note in old log")
        self.assertEqual(old["events"][:-1], before["events"])
        self.assertEqual(old["events"][-1]["event_type"], "seasonlens.demo-reset")

    def test_invalid_submissions_leave_state_and_events_unchanged(self) -> None:
        invalid = [dict(self.initial, selected_region=None),
                   dict(self.initial, selected_region={"x": 0.5, "y": 0.5}),
                   dict(self.initial, selected_region=dict(self.initial["selected_region"], width=0)),
                   dict(self.initial, observation_text="  "), dict(self.initial, selected_stage_id=None),
                   dict(self.initial, selected_stage_id="not_an_option")]
        invalid += [dict(self.initial, confidence=value) for value in [None, 0, 6, 2.5, True, "3"]]
        invalid += [dict(self.initial, visual_evidence_reason=value) for value in [None, "  "]]
        invalid += [dict(self.initial, judgement_source=value) for value in [None, "invalid_source"]]
        before = self.service.export_study_log(self.session_id)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.service.submit_initial(self.session_id, payload)
            self.assertEqual(self.service.participant_projection(self.session_id)["data"]["stage"], "OBSERVE")
            self.assertEqual(self.service.export_study_log(self.session_id)["events"], before["events"])

    def test_invalid_transitions_and_reflection_options(self) -> None:
        actions = [self.service.begin_reobservation, self.service.begin_reflection,
                   self.service.reveal_expert_cue, lambda sid: self.service.submit_revision(sid, self.initial),
                   lambda sid: self.service.submit_reflection(sid, "Too early")]
        for action in actions:
            with self.assertRaises(ValueError): action(self.session_id)
        self.service.submit_initial(self.session_id, self.initial)
        with self.assertRaises(ValueError): self.service.submit_revision(self.session_id, self.initial)
        with self.assertRaises(ValueError): self.service.begin_reobservation(self.session_id)
        with self.assertRaises(ValueError): self.service.submit_revision(self.session_id, self.initial)
        self.service.reveal_expert_cue(self.session_id)
        self.service.begin_reflection(self.session_id)
        with self.assertRaises(ValueError): self.service.submit_reflection(self.session_id, "Changed", "Invalid choice")
        self.service.submit_reflection(self.session_id, " ", "What the feature meant")
        with self.assertRaises(ValueError): self.service.submit_reflection(self.session_id, "Overwritten")

    def test_csv_retains_false_flags_nested_regions_and_escaped_text(self) -> None:
        self.service.submit_initial(self.session_id, self.initial)
        self.service.save_researcher_notes(self.session_id, '=example, "quoted"\nsecond line')
        row = next(csv.DictReader(io.StringIO(self.service.export_study_csv(self.session_id))))
        self.assertEqual(row["manual_override"], "False")
        self.assertEqual(json.loads(row["initial_region"]), self.initial["selected_region"])
        self.assertEqual(row["initial_stage_id"], "flower_buds_present")
        self.assertEqual(row["initial_visual_evidence_reason"], self.initial["visual_evidence_reason"])
        self.assertEqual(row["initial_judgement_source"], "image_evidence")
        self.assertEqual(row["correct_stage_id"], "flower_buds_present")
        self.assertTrue(row["researcher_notes"].startswith("'=example"))
        self.assertIn('\nsecond line', row["researcher_notes"])


if __name__ == "__main__":
    unittest.main()
