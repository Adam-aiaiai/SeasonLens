"""Rectangle geometry and deterministic matching to authored study metadata."""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any, Mapping

UNKNOWN_REGION = "UNKNOWN_REGION"


def normalized_rectangle(region: object) -> dict[str, float] | None:
    """Require a finite, nonempty rectangle entirely inside the image."""
    if not isinstance(region, Mapping):
        return None
    try:
        values = {key: float(region[key]) for key in ("x", "y", "width", "height")}
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    x, y, width, height = (values[key] for key in ("x", "y", "width", "height"))
    if not all(isfinite(value) for value in values.values()):
        return None
    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1
            and x + width <= 1 + 1e-9 and y + height <= 1 + 1e-9):
        return None
    return values


def region_iou(selected_region: object, accepted_region: object) -> float:
    """Intersection area / union area; invalid rectangles have overlap zero."""
    selected = normalized_rectangle(selected_region)
    accepted = normalized_rectangle(accepted_region)
    if selected is None or accepted is None:
        return 0.0
    width = max(0.0, min(selected["x"] + selected["width"], accepted["x"] + accepted["width"])
                - max(selected["x"], accepted["x"]))
    height = max(0.0, min(selected["y"] + selected["height"], accepted["y"] + accepted["height"])
                 - max(selected["y"], accepted["y"]))
    intersection = width * height
    union = selected["width"] * selected["height"] + accepted["width"] * accepted["height"] - intersection
    return intersection / union if union > 0 else 0.0


def validate_region_selection(
    selected_region: Mapping[str, object], accepted_region: Mapping[str, object], threshold: float = 0.25
) -> bool:
    """Explicit region selection is accepted at IoU >= 0.25 by default."""
    return region_iou(selected_region, accepted_region) >= threshold


def target_definition(item: Mapping[str, Any]) -> dict[str, Any]:
    """Support the original flat rectangle as well as the semantic target schema."""
    target = item.get("target_region", item.get("accepted_target_region", {}))
    if "rect" in target:
        return deepcopy(dict(target))
    return {"id": "target_region", "label": item.get("target_structure", "target region"),
            "rect": deepcopy(target)}


def classify_semantic_region(item: Mapping[str, Any], selected_region: object) -> dict[str, Any]:
    """Match IoU, never centre points. Accepted target wins; other ties use authored order."""
    target = target_definition(item)
    target_iou = region_iou(selected_region, target["rect"])
    region_correct = target_iou >= item.get("region_iou_threshold", 0.25)
    distractors = item.get("distractor_regions", [])
    overlaps = [region_iou(selected_region, region["rect"]) for region in distractors]
    best_distractor_iou = max(overlaps, default=0.0)
    candidates = [target, *distractors]
    scores = [target_iou, *overlaps]
    best_index = max(range(len(scores)), key=scores.__getitem__)
    best_region = candidates[best_index]
    meaningful = scores[best_index] >= item.get("semantic_region_iou_threshold", 0.25)
    if region_correct:
        matched = target
    elif meaningful:
        matched = best_region
    else:
        matched = {"id": UNKNOWN_REGION, "label": "unmatched region"}
    return {
        "region_correct": region_correct,
        "selected_semantic_region": matched["id"],
        "selected_region_label": matched["label"],
        "target_region_id": target["id"],
        "target_iou": target_iou,
        "best_distractor_iou": best_distractor_iou,
    }


def validate_region_metadata(item: Mapping[str, Any]) -> None:
    """Fail at catalog load for invalid authored coordinates, IDs or thresholds."""
    for key in ("region_iou_threshold", "semantic_region_iou_threshold"):
        value = item.get(key, 0.25)
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not isfinite(value) or not 0 < value <= 1):
            raise ValueError(f"{key} must be a finite IoU threshold in (0, 1].")
    seen = {UNKNOWN_REGION}
    for region in [target_definition(item), *item.get("distractor_regions", [])]:
        region_id = region.get("id")
        if not isinstance(region_id, str) or not region_id.strip() or region_id in seen:
            raise ValueError("Authored semantic region IDs must be nonempty and unique.")
        seen.add(region_id)
        if not isinstance(region.get("label"), str) or not region["label"].strip():
            raise ValueError("Authored semantic regions require a label.")
        if normalized_rectangle(region.get("rect")) is None:
            raise ValueError(f"Invalid normalized rectangle for semantic region {region_id}.")
    if any(region_id not in seen for region_id in item.get("region_hints", {})):
        raise ValueError("Region hint mappings must reference an authored region ID or UNKNOWN_REGION.")
