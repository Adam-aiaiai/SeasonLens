import unittest
from copy import deepcopy

from seasonlens import (
    DemoItemCatalog,
    DifficultyCode,
    classify_difficulty,
    select_hint_from_library,
    validate_region_selection,
    diagnose_response,
    region_iou,
)


def response(rect: dict, observation: str, interpretation: str) -> dict:
    return {
        "selected_region": rect,
        "observation_text": observation,
        "interpretation_text": interpretation,
        "selected_stage_id": "fruiting" if interpretation == "fruiting" else "flower_buds_present",
    }


class DomainTests(unittest.TestCase):
    def test_classifier_applies_ordered_frozen_rules(self) -> None:
        item = DemoItemCatalog().get("demo_anemone_001")
        target = item["target_region"]["rect"]
        miss = {"x": 0.7, "y": 0.2, "width": 0.1, "height": 0.1}
        self.assertIs(classify_difficulty(item, response(miss, "rounded buds", "flower buds present")), DifficultyCode.REGION_MISS)
        self.assertIs(classify_difficulty(item, response(target, "green shape", "flower buds present")), DifficultyCode.CUE_MISIDENTIFIED)
        self.assertIs(classify_difficulty(item, response(target, "closed flower buds", "fruiting")), DifficultyCode.INTERPRETATION_ERROR)
        self.assertIs(classify_difficulty(item, response(target, "swollen bud", "flower buds present")), DifficultyCode.CORRECT)

    def test_structured_stage_id_is_authoritative_with_legacy_keyword_fallback(self) -> None:
        item = DemoItemCatalog().get("demo_anemone_001")
        target = item["target_region"]["rect"]
        wrong_id = response(target, "swollen bud", "flower buds present")
        wrong_id["selected_stage_id"] = "fruiting"
        self.assertIs(classify_difficulty(item, wrong_id), DifficultyCode.INTERPRETATION_ERROR)

        legacy_item = deepcopy(item)
        legacy_item.pop("stage_options")
        legacy_item.pop("correct_stage_id")
        legacy_response = response(target, "swollen bud", "flower buds present")
        legacy_response.pop("selected_stage_id")
        self.assertIs(classify_difficulty(legacy_item, legacy_response), DifficultyCode.CORRECT)

    def test_region_overlap_uses_normalized_rectangles(self) -> None:
        target = {"x": 0.68, "y": 0.08, "width": 0.22, "height": 0.30}
        self.assertTrue(validate_region_selection(target, target))
        self.assertAlmostEqual(region_iou(target, target), 1)
        half = {"x": 0.68, "y": 0.08, "width": 0.11, "height": 0.30}
        self.assertAlmostEqual(region_iou(half, target), 0.5)
        self.assertEqual(region_iou({"x": 0, "y": 0, "width": 0.1, "height": 0.1}, target), 0)
        self.assertFalse(validate_region_selection({"x": 1.2, "y": 0.2}, target))
        self.assertFalse(validate_region_selection({}, target))
        self.assertFalse(validate_region_selection({"x": 0.68, "y": 0.08}, target))
        for bad in [dict(target, width=0), dict(target, x=float("nan")),
                    dict(target, height=float("inf")), dict(target, x=0.95), dict(target, y=-0.1)]:
            self.assertEqual(region_iou(bad, target), 0)
        a = {"x": 0, "y": 0, "width": 0.5, "height": 0.5}
        b = dict(a, x=0.25)
        self.assertAlmostEqual(region_iou(a, b), 1 / 3)
        self.assertTrue(validate_region_selection(b, a, threshold=1 / 3))
        self.assertFalse(validate_region_selection(b, a, threshold=0.34))

    def test_hint_is_selected_only_from_authored_library(self) -> None:
        item = DemoItemCatalog().get("demo_anemone_001")
        hint = select_hint_from_library(item, DifficultyCode.REGION_MISS)
        self.assertEqual(hint, item["hints"]["REGION_MISS"][0])
        self.assertEqual(select_hint_from_library(item, "REGION_MISS", level=2), item["hints"]["REGION_MISS"][1])
        hint["text"] = "changed"
        self.assertNotEqual(hint, item["hints"]["REGION_MISS"][0])
        with self.assertRaises(ValueError):
            select_hint_from_library(item, "REGION_MISS", level=99)

    def test_diagnostic_checks_are_independent(self) -> None:
        item = DemoItemCatalog().get("demo_anemone_001")
        diagnostic = diagnose_response(item, response(
            {"x": 0.7, "y": 0.2, "width": 0.1, "height": 0.1},
            "CLOSED FLOWER BUDS", "FLOWER   BUDS PRESENT"
        ))
        self.assertFalse(diagnostic["region_correct"])
        self.assertTrue(diagnostic["cue_correct"])
        self.assertTrue(diagnostic["interpretation_correct"])
        self.assertEqual(diagnostic["primary_error"], "REGION_MISS")
        self.assertEqual(diagnostic["region_iou"], 0)

    def test_multiple_items_and_participant_catalog(self) -> None:
        catalog = DemoItemCatalog()
        self.assertEqual([item["item_id"] for item in catalog.list_items()], [
            "demo_anemone_001", "demo_solidago_001", "demo_butterfly_weed_001",
        ])
        solidago = catalog.get("demo_solidago_001")
        self.assertEqual(classify_difficulty(solidago, {
            "selected_region": solidago["target_region"]["rect"],
            "observation_text": "open yellow flowers", "interpretation_text": "flowering",
            "selected_stage_id": "flowering",
        }), DifficultyCode.CORRECT)
        self.assertEqual([item["cue_family"] for item in catalog.list_items()], [
            "Flower bud", "Flower", "Flower",
        ])
        for item in catalog.list_items():
            self.assertTrue(item["stage_options"])
            self.assertNotIn("hints", item)
            self.assertNotIn("target_region", item)
            self.assertNotIn("accepted_cue_keywords", item)
        with self.assertRaises(ValueError):
            catalog.get("unknown")


if __name__ == "__main__":
    unittest.main()
