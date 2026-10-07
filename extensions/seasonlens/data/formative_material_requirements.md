# Additional formative-study material requirements

Only the bud and flower items are active because they are the only cue families
with suitable, locally stored real photographs and complete authored regions.
The catalog automatically loads `*.json`; therefore incomplete items are kept out
of that active set rather than exposing broken image links to participants.

To reach the intended 4–5 item formative set, add at least two of the following
real photographs to `apps/web/assets/real/`, then author normalized target and
distractor rectangles against the exact local files:

| Proposed item | Required local filename | Required visible comparison |
| --- | --- | --- |
| Leaf development | `leaf_001_<species>.jpg` | A clearly expanding/unfolding leaf plus plausible nearby distractors |
| Fruit development | `fruit_001_<species>.jpg` | A defensible visible fruit-development cue plus other structures/stages |
| Senescence | `senescence_001_<species>.jpg` | Localized senescence evidence with non-senescent foliage in the same frame |

Each activated item must follow the existing authored JSON structure and include:
`item_id`, `plant_name`, `image_path`, `cue_family`, `target_structure`,
`target_region`, `region_iou_threshold`, `semantic_region_iou_threshold`,
`distractor_regions`, accepted observation and interpretation keywords, expert cue
and bounded interpretation, participant prompts, deterministic diagnosis hints,
and any useful distractor-specific hints. Record provenance and licence details in
`image_sources.md`. Do not activate an item until the image, ecological wording,
and every rectangle have been reviewed together.
