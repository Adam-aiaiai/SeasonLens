from __future__ import annotations

import json
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

from .regions import target_definition, validate_region_metadata


DEFAULT_ITEM_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "demo_anemone_001.json"
)


class DemoItemCatalog:
    """Loads the frozen authored item library; it never generates ecological text."""

    def __init__(self, item_path: Path = DEFAULT_ITEM_PATH.parent) -> None:
        paths = sorted(item_path.glob("*.json")) if item_path.is_dir() else [item_path]
        preferred = {
            "demo_anemone_001": 0,
            "demo_solidago_001": 1,
            "demo_butterfly_weed_001": 2,
        }
        paths.sort(key=lambda path: (preferred.get(path.stem, 2), path.name))
        self._items: dict[str, dict[str, Any]] = {}
        for path in paths:
            with path.open(encoding="utf-8") as source:
                item = json.load(source)
            item_id = str(item["item_id"])
            if item_id in self._items:
                raise ValueError(f"Duplicate authored item: {item_id}")
            stage_options = item.get("stage_options")
            if stage_options is not None:
                if not isinstance(stage_options, list) or not stage_options:
                    raise ValueError(f"stage_options must be a non-empty list in {item_id}.")
                stage_ids = [str(option.get("id", "")).strip() for option in stage_options]
                stage_labels = [str(option.get("label", "")).strip() for option in stage_options]
                if any(not value for value in [*stage_ids, *stage_labels]):
                    raise ValueError(f"Every stage option needs an id and label in {item_id}.")
                if len(stage_ids) != len(set(stage_ids)):
                    raise ValueError(f"Duplicate stage option ID in {item_id}.")
                if item.get("correct_stage_id") not in stage_ids:
                    raise ValueError(f"correct_stage_id must name a stage option in {item_id}.")
            # Keep the original accepted_target_region alias for existing callers.
            item["target_region"] = item.get("target_region", item.get("accepted_target_region"))
            validate_region_metadata(item)
            item["accepted_target_region"] = deepcopy(target_definition(item)["rect"])
            hints = [hint for library in (item["hints"], item.get("region_hints", {}))
                     for tier in library.values() for hint in tier]
            hint_ids = [hint["id"] for hint in hints]
            if len(hint_ids) != len(set(hint_ids)):
                raise ValueError(f"Duplicate authored hint ID in {item_id}.")
            self._items[item_id] = item
        if not self._items:
            raise ValueError("No authored SeasonLens items found.")

    def list_items(self) -> list[dict[str, Any]]:
        return [self.participant_view(item_id) for item_id in self._items]

    def hint_library(self, item_id: str) -> list[dict[str, Any]]:
        item = self.get(item_id)
        generic = [dict(hint, category=category, region_id=None,
                        region_hint_source="generic_region_miss" if category == "REGION_MISS" else None)
                   for category, hints in item["hints"].items() for hint in hints]
        spatial = [dict(hint, category="REGION_MISS", region_id=region_id, region_hint_source="semantic_region")
                   for region_id, hints in item.get("region_hints", {}).items() for hint in hints]
        return [*generic, *spatial]

    def researcher_regions(self, item_id: str) -> dict[str, Any]:
        item = self.get(item_id)
        return {"target_region": target_definition(item),
                "distractor_regions": item.get("distractor_regions", []),
                "region_iou_threshold": item.get("region_iou_threshold", 0.25),
                "semantic_region_iou_threshold": item.get("semantic_region_iou_threshold", 0.25)}

    def get_hint(self, item_id: str, hint_id: str) -> dict[str, Any]:
        for hint in self.hint_library(item_id):
            if hint["id"] == hint_id:
                return hint
        raise ValueError("Choose a hint from this item's authored library.")

    def get(self, item_id: str) -> dict[str, Any]:
        item_id = self.canonical_id(item_id)
        try:
            return deepcopy(self._items[item_id])
        except KeyError as error:
            raise ValueError(f"Unknown SeasonLens item: {item_id}") from error

    @staticmethod
    def canonical_id(item_id: str) -> str:
        return item_id

    def checksum(self, item_id: str) -> str:
        content = json.dumps(self.get(item_id), sort_keys=True).encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    def participant_view(self, item_id: str) -> dict[str, Any]:
        item = self.get(item_id)
        return {
            "item_id": item["item_id"],
            "plant_name": item["plant_name"],
            "image_path": item["image_path"],
            "cue_family": item["cue_family"],
            "prompts": item["prompts"],
            "stage_options": deepcopy(item.get("stage_options", [])),
            "region_selection_kind": "explicit-rectangle-proxy",
        }

    def expert_view(self, item_id: str) -> dict[str, Any]:
        item = self.get(item_id)
        return {
            "relevant_region": item["target_structure"],
            "diagnostic_cue": item["expert_cue"],
            "interpretation": item["expert_interpretation"],
            "correct_stage_id": item.get("correct_stage_id"),
            "correct_stage_label": next(
                (option["label"] for option in item.get("stage_options", [])
                 if option["id"] == item.get("correct_stage_id")),
                None,
            ),
            "target_region": item["accepted_target_region"],
        }
