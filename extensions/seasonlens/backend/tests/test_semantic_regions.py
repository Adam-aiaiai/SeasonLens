from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from seasonlens import (
    DemoItemCatalog, SeasonLensService, classify_semantic_region,
    diagnose_response, select_hint_decision, select_hint_from_library,
)


class SemanticFixture:
    def setUp(self):
        self.item = DemoItemCatalog().get("demo_anemone_001")
        self.target = self.item["target_region"]["rect"]
        self.regions = {region["id"]: region["rect"] for region in self.item["distractor_regions"]}
        self.background = {"x": 0.02, "y": 0.86, "width": 0.1, "height": 0.1}

    def response(self, rect, observation="closed flower buds", interpretation="flower buds present"):
        return {"selected_region": deepcopy(rect), "observation_text": observation,
                "interpretation_text": interpretation,
                "selected_stage_id": "fruiting" if interpretation == "late summer" else "flower_buds_present",
                "confidence": 3}

    def decision(self, response):
        diagnostic = diagnose_response(self.item, response)
        return select_hint_decision(self.item, diagnostic["primary_error"],
                                   selected_semantic_region=diagnostic["selected_semantic_region"])


class SemanticRegionTests(SemanticFixture, unittest.TestCase):
    def test_target_region_continues_to_cue_and_interpretation_checks(self):
        diagnostic = diagnose_response(self.item, self.response(self.target))
        self.assertTrue(diagnostic["region_correct"])
        self.assertEqual(diagnostic["selected_semantic_region"], "upper_bud_region")
        self.assertEqual(diagnostic["primary_error"], "CORRECT")
        self.assertAlmostEqual(diagnostic["target_iou"], 1)
        self.assertEqual(self.decision(self.response(self.target))["hint"]["id"], "demo_anemone_correct_01")

    def test_large_leaf_region_selects_leaf_specific_authored_hint(self):
        response = self.response(self.regions["large_leaf_region"])
        diagnostic = diagnose_response(self.item, response)
        self.assertFalse(diagnostic["region_correct"])
        self.assertEqual(diagnostic["selected_semantic_region"], "large_leaf_region")
        self.assertEqual(diagnostic["selected_region_label"], "large foreground leaves")
        self.assertEqual(diagnostic["primary_error"], "REGION_MISS")
        self.assertEqual(diagnostic["best_distractor_iou"], 1)
        decision = self.decision(response)
        self.assertEqual(decision["hint"]["id"], "demo_anemone_large_leaf_01")
        self.assertEqual(decision["region_hint_source"], "semantic_region")
        self.assertEqual(select_hint_from_library(self.item, "REGION_MISS", 2,
                         selected_semantic_region="large_leaf_region")["id"], "demo_anemone_region_02")

    def test_branch_region_selects_a_different_spatial_hint(self):
        response = self.response(self.regions["middle_stem"])
        self.assertEqual(diagnose_response(self.item, response)["selected_semantic_region"], "middle_stem")
        self.assertEqual(self.decision(response)["hint"]["id"], "demo_anemone_middle_stem_01")
        self.assertNotEqual(self.decision(response)["hint"]["text"],
                            self.decision(self.response(self.regions["large_leaf_region"]))["hint"]["text"])

    def test_background_region_uses_generic_hint_and_optional_authored_unknown_mapping(self):
        diagnostic = diagnose_response(self.item, self.response(self.background))
        self.assertEqual(diagnostic["selected_semantic_region"], "UNKNOWN_REGION")
        self.assertEqual(diagnostic["target_iou"], 0)
        self.assertEqual(diagnostic["best_distractor_iou"], 0)
        decision = self.decision(self.response(self.background))
        self.assertEqual(decision["hint"]["id"], "demo_anemone_region_01")
        self.assertEqual(decision["region_hint_source"], "generic_region_miss")
        self.item["region_hints"]["UNKNOWN_REGION"] = [{"id": "authored_unknown", "level": 1,
            "type": "general_attention", "text": "Focus on changing plant structures."}]
        self.assertEqual(self.decision(self.response(self.background))["hint"]["id"], "authored_unknown")

    def test_correct_region_wrong_cue_gets_cue_hint(self):
        response = self.response(self.target, "The leaf is becoming greener.")
        diagnostic = diagnose_response(self.item, response)
        self.assertTrue(diagnostic["region_correct"])
        self.assertFalse(diagnostic["cue_correct"])
        self.assertEqual(diagnostic["primary_error"], "CUE_MISIDENTIFIED")
        decision = self.decision(response)
        self.assertEqual(decision["hint"]["id"], "demo_anemone_feature_01")
        self.assertIsNone(decision["region_hint_source"])
        self.assertIsNone(decision["region_hint_id"])

    def test_correct_region_and_cue_wrong_interpretation_gets_interpretation_hint(self):
        response = self.response(self.target, interpretation="late summer")
        diagnostic = diagnose_response(self.item, response)
        self.assertTrue(diagnostic["region_correct"])
        self.assertTrue(diagnostic["cue_correct"])
        self.assertFalse(diagnostic["interpretation_correct"])
        self.assertEqual(diagnostic["primary_error"], "INTERPRETATION_ERROR")
        self.assertEqual(self.decision(response)["hint"]["id"], "demo_anemone_stage_01")

    def test_best_overlap_and_threshold_not_centre_point(self):
        item = deepcopy(self.item)
        item["target_region"] = {"id": "target", "label": "target", "rect": {"x": 0.8, "y": 0.8, "width": 0.1, "height": 0.1}}
        rect = {"x": 0, "y": 0, "width": 0.4, "height": 0.4}
        item["distractor_regions"] = [
            {"id": "smaller", "label": "smaller", "rect": dict(rect, width=0.2)},
            {"id": "larger", "label": "larger", "rect": rect},
        ]
        self.assertEqual(classify_semantic_region(item, rect)["selected_semantic_region"], "larger")
        item["semantic_region_iou_threshold"] = 0.5
        selection = dict(rect, width=0.8)
        self.assertEqual(classify_semantic_region(item, selection)["selected_semantic_region"], "larger")
        item["semantic_region_iou_threshold"] = 0.51
        self.assertEqual(classify_semantic_region(item, selection)["selected_semantic_region"], "UNKNOWN_REGION")
        # A centre inside the region is insufficient when the area overlap is small.
        self.assertEqual(classify_semantic_region(item, {"x": 0, "y": 0, "width": 0.8, "height": 0.8})["selected_semantic_region"], "UNKNOWN_REGION")

    def test_correct_target_takes_priority_even_if_distractor_iou_is_higher(self):
        item = deepcopy(self.item)
        selection = dict(self.target, width=self.target["width"] / 2)
        item["distractor_regions"] = [{"id": "overlapping", "label": "overlapping distractor", "rect": selection}]
        diagnostic = classify_semantic_region(item, selection)
        self.assertTrue(diagnostic["region_correct"])
        self.assertEqual(diagnostic["selected_semantic_region"], "upper_bud_region")
        self.assertAlmostEqual(diagnostic["target_iou"], 0.5)
        self.assertAlmostEqual(diagnostic["best_distractor_iou"], 1)

    def test_ties_follow_authored_order_and_partial_target_is_distinguished_from_correct(self):
        item = deepcopy(self.item)
        region = deepcopy(item["distractor_regions"][0])
        item["distractor_regions"] = [region, dict(region, id="equal_second")]
        self.assertEqual(classify_semantic_region(item, region["rect"])["selected_semantic_region"], "large_leaf_region")
        item["region_iou_threshold"] = 0.75
        selected = dict(self.target, width=self.target["width"] / 2)
        diagnostic = classify_semantic_region(item, selected)
        self.assertFalse(diagnostic["region_correct"])
        self.assertEqual(diagnostic["selected_semantic_region"], "upper_bud_region")

    def test_unmapped_region_and_missing_specific_tier_fall_back_to_generic(self):
        self.item["region_hints"].pop("background_vegetation")
        decision = self.decision(self.response(self.regions["background_vegetation"]))
        self.assertEqual(decision["hint"]["id"], "demo_anemone_region_01")
        self.assertEqual(decision["region_hint_source"], "generic_region_miss")
        self.item["region_hints"]["large_leaf_region"] = self.item["region_hints"]["large_leaf_region"][:1]
        hint = select_hint_from_library(self.item, "REGION_MISS", 2, selected_semantic_region="large_leaf_region")
        self.assertEqual(hint["id"], "demo_anemone_region_02")

    def test_flower_item_uses_its_own_metadata_and_authored_hints(self):
        item = DemoItemCatalog().get("demo_solidago_001")
        large_leaf_region = next(region for region in item["distractor_regions"] if region["id"] == "middle_leaf_region")
        diagnostic = diagnose_response(item, self.response(large_leaf_region["rect"]))
        decision = select_hint_decision(item, diagnostic["primary_error"],
                                        selected_semantic_region=diagnostic["selected_semantic_region"])
        self.assertEqual(decision["hint"]["id"], "demo_solidago_middle_leaves_01")
        self.assertEqual(diagnostic["target_region_id"], "upper_flowering_region")

    def test_old_flat_target_schema_remains_supported(self):
        item = deepcopy(self.item)
        item["target_region"] = deepcopy(self.target)
        item.pop("distractor_regions")
        item.pop("region_hints")
        diagnostic = diagnose_response(item, self.response(self.target))
        self.assertTrue(diagnostic["region_correct"])
        self.assertEqual(diagnostic["primary_error"], "CORRECT")


class SemanticStudyLogTests(SemanticFixture, unittest.TestCase):
    def test_initial_and_revised_diagnostics_are_separate_in_saved_log_csv_and_events(self):
        with tempfile.TemporaryDirectory() as directory:
            service = SeasonLensService(export_directory=Path(directory))
            session_id = service.create_session("semantic-participant")["data"]["session_id"]
            service.submit_initial(session_id, self.response(self.regions["large_leaf_region"], observation="a leaf"))
            initial = service.export_study_log(session_id)
            service.begin_reobservation(session_id)
            service.submit_revision(session_id, self.response(self.target))
            log = service.export_study_log(session_id)
            self.assertEqual(log["initial_selected_semantic_region"], "large_leaf_region")
            self.assertEqual(log["revised_selected_semantic_region"], "upper_bud_region")
            self.assertEqual(log["selected_semantic_region"], "large_leaf_region")
            self.assertEqual(log["diagnostic"], initial["diagnostic"])
            self.assertEqual(log["primary_error"], "REGION_MISS")
            self.assertEqual(log["revised_diagnostic"]["primary_error"], "CORRECT")
            self.assertEqual(log["region_hint_source"], "semantic_region")
            self.assertEqual(log["region_hint_id"], "demo_anemone_large_leaf_01")
            self.assertEqual(log["target_region_iou"], 0)
            self.assertEqual(log["best_distractor_iou"], 1)
            self.assertAlmostEqual(log["revised_target_region_iou"], 1)
            self.assertEqual(log["events"][:len(initial["events"])], initial["events"])
            self.assertEqual(log["events"][-1]["payload"]["revised_diagnostic"]["selected_semantic_region"], "upper_bud_region")
            saved = json.loads((Path(directory) / f"{session_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["initial_selected_semantic_region"], "large_leaf_region")
            self.assertEqual(saved["revised_selected_semantic_region"], "upper_bud_region")
            row = next(csv.DictReader(io.StringIO(service.export_study_csv(session_id))))
            self.assertEqual(row["initial_selected_semantic_region"], "large_leaf_region")
            self.assertEqual(row["revised_selected_semantic_region"], "upper_bud_region")

    def test_participant_projection_hides_labels_and_regions_at_each_stage(self):
        service = SeasonLensService()
        session_id = service.create_session("semantic-participant")["data"]["session_id"]
        stages = [None,
            lambda: service.submit_initial(session_id, self.response(self.regions["middle_stem"])),
            lambda: service.begin_reobservation(session_id),
            lambda: service.submit_revision(session_id, self.response(self.target)),
            lambda: service.reveal_expert_cue(session_id),
            lambda: service.begin_reflection(session_id),
            lambda: service.submit_reflection(session_id, "I changed the selected region."),
        ]
        for action in stages:
            if action: action()
            projection = service.participant_projection(session_id)
            # Inspect fields, not hint IDs or authored text which can mention a feature.
            for secret in ["selected_semantic_region", "selected_region_label", "target_region_id",
                           "target_iou", "best_distractor_iou", "region_hint_source", "region_hint_id",
                           "initial_diagnostic", "revised_diagnostic", "distractor_regions", "region_hints"]:
                self.assertNotIn('"' + secret + '":', json.dumps(projection))
            if projection["data"]["stage"] in {"OBSERVE", "HINT", "REOBSERVE", "REVISED_COMMITTED"}:
                self.assertNotIn("target_region", json.dumps(projection))

    def test_researcher_projection_exposes_both_diagnostics_regions_and_spatial_override_hints(self):
        service = SeasonLensService()
        session_id = service.create_session("semantic-participant")["data"]["session_id"]
        service.submit_initial(session_id, self.response(self.regions["middle_stem"]))
        researcher = service.researcher_projection(session_id)
        self.assertEqual(researcher["log"]["selected_semantic_region"], "middle_stem")
        self.assertEqual(researcher["regions"]["target_region"]["id"], "upper_bud_region")
        self.assertEqual(len(researcher["regions"]["distractor_regions"]), 3)
        self.assertIn("demo_anemone_large_leaf_01", [hint["id"] for hint in researcher["hints"]])
        service.override_hint(session_id, "demo_anemone_large_leaf_01")
        log = service.export_study_log(session_id)
        self.assertEqual(log["diagnostic"], researcher["log"]["diagnostic"])
        self.assertEqual(log["automatic_hint_id"], "demo_anemone_middle_stem_01")
        self.assertEqual(log["actual_hint_id"], "demo_anemone_large_leaf_01")
        self.assertEqual(log["region_hint_id"], "demo_anemone_large_leaf_01")
        self.assertEqual(log["automatic_region_hint_id"], "demo_anemone_middle_stem_01")
        self.assertEqual([hint["region_hint_id"] for hint in log["hint_sequence"]],
                         ["demo_anemone_middle_stem_01", "demo_anemone_large_leaf_01"])


class AuthoredMetadataTests(SemanticFixture, unittest.TestCase):
    def test_bad_rectangles_duplicate_region_ids_and_invalid_thresholds_are_rejected_at_load(self):
        bad_items = []
        for value in [0, 1.1, float("nan"), float("inf"), True]:
            bad_items.append(dict(self.item, semantic_region_iou_threshold=value))
        item = deepcopy(self.item)
        item["distractor_regions"][0]["rect"]["width"] = 2
        bad_items.append(item)
        item = deepcopy(self.item)
        item["distractor_regions"][0]["id"] = "upper_bud_region"
        bad_items.append(item)
        item = deepcopy(self.item)
        item["region_hints"]["unconfigured_region"] = []
        bad_items.append(item)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "item.json"
            for item in bad_items:
                with self.subTest(item=item):
                    path.write_text(json.dumps(item), encoding="utf-8")
                    with self.assertRaises(ValueError): DemoItemCatalog(path)

    def test_flat_item_file_loads_and_expert_projection_stays_a_flat_rectangle(self):
        item = deepcopy(self.item)
        item["target_region"] = deepcopy(self.target)
        item.pop("distractor_regions")
        item.pop("region_hints")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "item.json"
            path.write_text(json.dumps(item), encoding="utf-8")
            catalog = DemoItemCatalog(path)
            self.assertEqual(catalog.expert_view("demo_anemone_001")["target_region"], self.target)
        catalog = DemoItemCatalog()
        self.assertEqual(catalog.expert_view("demo_anemone_001")["target_region"], self.target)


if __name__ == "__main__":
    unittest.main()
