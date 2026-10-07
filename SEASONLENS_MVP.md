# SeasonLens formative-study MVP

This iteration extends the working observation-first contingent prototype within
the existing shared proposal → policy → tool → reducer → state/event contracts.
It does not introduce another application or an LLM. Group A and Group C are
implemented; Group B remains an explicitly labelled, incomplete yoking placeholder.
Different wrong selected regions now produce different authored hints through
overlap matching to semantic regions defined in each item.

## Launch and checks

Run from the repository root:

```powershell
python apps/api/main.py
```

Python 3.11+ is the only runtime dependency. Open <http://127.0.0.1:8000> for the
participant interface, or <http://127.0.0.1:8000/?debug=1> for researcher mode.
The participant introduction requests an anonymous study code such as `F01`; use
study codes rather than names. The introduction appears once when a new formative
session is started and is not repeated between linked items.
Optional server arguments: `--host 127.0.0.1 --port 8000`.

```powershell
python scripts/check_seasonlens.py
node --check apps/web/app.js
node --test apps/web/tests/interaction.test.cjs
Push-Location packages/frontend-core
npm.cmd run typecheck
Pop-Location
$env:PYTHONPATH = "packages/backend-core/src;extensions/seasonlens/backend/src"
python packages/backend-core/examples/agent_lifecycle_demo.py
```

`check_seasonlens.py` runs all SeasonLens unittest cases, including real localhost
HTTP contract checks, and wraps both existing backend-core assertion functions in
unittest cases. It requires no pytest installation. JavaScript tests exercise the
shipped event handlers with DOM doubles; they are not a real-browser visual test.

## Participant workflow

1. **Observe:** drag on the plant image to select the region that best contains
   the visual evidence supporting the judgement. Describe only directly visible
   evidence, choose one item-specific stage option, and record confidence (1–5).
2. **Commit:** choose **Review and commit** to review the draft. **Edit response /
   redraw** returns to Observe with the draft intact. **Commit observation**
   permanently records the initial attempt and runs deterministic layered diagnosis.
3. **Conditional feedback:** a fully correct initial response receives positive
   confirmation and skips Hint and Re-observe. An incorrect response receives an
   authored hint selected for the current error type and level.
4. **Re-observe when needed:** after a hint, inspect again and submit a separate
   revised region, visible-evidence description, and bounded stage choice. The
   original stored attempt is never overwritten. Group C re-diagnoses every revision,
   escalates the same error from Level 1 to Level 3, and stops after Level 3.
5. **Reveal:** explicitly reveal the expert cue, interpretation, and target rectangle.
   The selected rectangle remains visible alongside the expert rectangle.
6. **Reflect:** initially correct participants answer a general visual-evidence
   question. Participants who received guidance answer the neutral prompt “What did
   you notice after seeing the hint?” Save reflection to complete the item.

The progress bar highlights the current participant stage and marks Guidance and
Re-observe as skipped for an initially correct response. Commit review
is local draft UI: the persisted transition into `INITIAL_COMMITTED` happens only
when the participant commits. `REVISED_COMMITTED` stays within Re-observe until
the explicit Reveal action. Completion remains at Reflect.

**Next item** appears after completing an item and starts the next authored item with
the same participant ID. The active order is Anemone, Solidago, then Butterfly weed. Each item has a
fresh session ID and log, linked through `previous_session_id` and an event in the
preceding log. No randomization, cycling, or counterbalancing is implemented.
After the final item, **Start another session** restarts the sequence.

## Rectangle diagnostic and authored content

All `*.json` files under `extensions/seasonlens/data/` load at server startup.
Current definitions and their hint libraries live together in:

- `demo_anemone_001.json` — Virginia anemone with several closed flower buds.
- `demo_solidago_001.json` — Canada goldenrod with upper yellow inflorescences.
- `demo_butterfly_weed_001.json` — Butterfly weed with open flowers and unopened buds.

Each item defines `item_id`, `plant_name`, `image_path`, `cue_family`, `target_region`,
`accepted_cue_keywords`, `accepted_interpretation_keywords`, `expert_cue`,
`expert_interpretation`, `target_structure`, `prompts`, `hints`,
`distractor_regions`, `region_hints`, and `semantic_region_iou_threshold`.
Add another file with the same schema and a local image in `apps/web/assets/`,
then restart the server. The three active items use locally stored real photographs;
their asset inventory is recorded in `extensions/seasonlens/data/image_sources.md`.
Requirements for additional inactive formative items are recorded in
`extensions/seasonlens/data/formative_material_requirements.md`.

Rectangles use `{x, y, width, height}` in image coordinates normalized to [0, 1],
with the top-left corner as origin. Width and height must be positive, coordinates
must be finite, and rectangles must lie inside the image. Missing dimensions,
single points, empty rectangles, and out-of-image rectangles are rejected.
The UI supports mouse, pen, and touch pointer drags in either direction. A cancelled
or tiny drag restores the previous rectangle; redrawing replaces the draft selection.

Region correctness uses **intersection over union (IoU)**:
`intersection area / (selected area + target area − intersection area)`.
The default acceptance threshold is **IoU ≥ 0.25**, also specified by each current
item's `region_iou_threshold`. Selecting the whole image is not sufficient for
these target regions. This threshold is a formative demo choice requiring later
calibration. The catalog retains `accepted_target_region` as an internal compatibility
alias for the original expert-view contract. Point-only submissions are intentionally
no longer accepted. This is explicit region selection, not gaze measurement.

## Semantic regions and hint hierarchy

Semantic target and distractor regions are **authored study metadata**, editable
in the JSON item files. They are not computer-vision predictions, object detections,
plant segmentation, or inferred gaze. The backend uses only rectangle IoU and
generic region IDs, labels, rectangles, and hint mappings; plant structure names
are not hard-coded in backend rules.

The target now uses `{id, label, rect}`. The original flat target rectangle is
still supported for legacy item files, with a generic internal target ID. Expert
reveal API projections retain the flat normalized rectangle contract.

Example from the Anemone item:

```json
{
  "target_region": {
    "id": "upper_bud_region", "label": "prominent upper closed flower bud",
    "rect": {"x": 0.31, "y": 0.07, "width": 0.11, "height": 0.2}
  },
  "distractor_regions": [
    {"id": "large_leaf_region", "label": "large foreground leaves",
     "rect": {"x": 0.25, "y": 0.58, "width": 0.50, "height": 0.39}},
    {"id": "middle_stem", "label": "middle upright stem",
     "rect": {"x": 0.34, "y": 0.29, "width": 0.08, "height": 0.27}}
  ],
  "region_iou_threshold": 0.25,
  "semantic_region_iou_threshold": 0.25,
  "region_hints": {
    "large_leaf_region": [
      {"id": "demo_anemone_large_leaf_01", "level": 1, "type": "contrastive_attention",
       "text": "You are focusing on leaves. Look higher on the plant for reproductive structures."}
    ]
  }
}
```

The active item files define their own target, distractors, generic hint categories,
and authored spatial hints. Region IDs are scoped to an item.

```text
selected rectangle
→ target and distractor IoU / semantic-region classification
  → target incorrect: matching authored region hint → generic REGION_MISS fallback
  → target correct: cue diagnosis → interpretation diagnosis → CORRECT
```

1. Compute target IoU and IoU against every distractor. Target correctness continues
   to use each item's authored `region_iou_threshold`.
2. If the target is accepted, set the selected semantic region to the target and
   continue through the existing cue/interpretation rules. A distractor with a higher
   IoU does not turn an accepted target into a region error.
3. Otherwise choose the region with greatest IoU among the target and distractors,
   requiring IoU ≥ `semantic_region_iou_threshold` (default 0.25). Below that threshold,
   use `UNKNOWN_REGION`. No centre-point rule is used. Exact ties prefer the target,
   then the first distractor in authored JSON order.
4. For a region miss, use the matching `region_hints[region_id]` at the requested
   level if present. If the mapping or requested level is absent, use the existing
   generic `hints.REGION_MISS` at that level. Automatic selection starts at Level 1.
   The active items use the generic fallback when no matching spatial tier exists.
   Authors can optionally map `region_hints.UNKNOWN_REGION` to static hints.

Thresholds are independent and configurable in (0, 1]. With a stricter correctness
threshold, a partial target match can be labelled as the target while still having
`region_correct = false`. This is a descriptive spatial match, not a correctness
claim. Invalid authored rectangles, duplicate semantic region IDs, invalid thresholds,
unknown region-hint mapping keys, and duplicate hint IDs fail at catalog startup.

The internal diagnostic adds `selected_semantic_region`, `selected_region_label`,
`target_region_id`, `target_iou`, and `best_distractor_iou`. `region_iou` remains a
compatibility alias for target IoU. Initial classification and every revision use
the same deterministic diagnostic. Revision diagnostics are stored separately and
appended to the participant path. For Group C, an unresolved error selects the next
authored tier for the current error type; a changed error type begins at Level 1.
The initial diagnostic and every hint exposure remain intact.

The diagnostic independently records `region_correct`, `cue_correct`,
`interpretation_correct`, and `region_iou`. Ordered priority determines
`primary_error`: REGION_MISS → CUE_MISIDENTIFIED → INTERPRETATION_ERROR → CORRECT.
Cue and interpretation checks are case-insensitive literal substring matches,
with response whitespace collapsed. Synonyms not authored in the keyword lists,
negation, and meaning are not inferred. Semantic interpretation is a future extension.

Each error category (and CORRECT) has a list of authored hints:

```json
{
  "REGION_MISS": [
    {"id": "demo_anemone_region_01", "level": 1, "type": "attention_directing",
     "text": "Look again at the upper part of the plant."},
    {"id": "demo_anemone_region_02", "level": 2, "type": "region_directing",
     "text": "Focus on the ends of the upright stems."}
  ]
}
```

Automatic selection starts at Level 1, preferring the matching authored spatial
library for REGION_MISS and using the category library for other codes. `hint_level`,
`hint_type`, and the append-only `hint_sequence` drive Level 1/2/3 escalation within
each error type. Cross-item fading is not implemented. Tools record an item
content checksum for reproducibility. All displayed hint text comes from the library.
The exported `item_definition_checksum` identifies the loaded authored definition,
and `state_version` identifies the current state snapshot.

## Researcher controls

Open `?debug=1`, then expand **Researcher controls and study log**. The panel shows
session/participant/item IDs, current backend stage, independent diagnostic checks,
actual hint and level, initial and revised responses side by side, confidence,
reflection, and a full JSON log containing timestamps and stage transitions.
It also displays the automatic hint ID/text and separate initial/revised semantic
diagnoses, primary errors, target IoUs, and best distractor IoUs. Two researcher-only
image panels overlay each committed participant rectangle (orange), expert target
(gold), and authored distractors (purple dashed). Draft drags are not classified
until submission. The participant image never gains distractor overlays; its expert
rectangle still appears only after reveal.

- **Manual authored hint override:** during Hint, choose any hint from the current
  item's category or region-specific library, then **Show chosen hint**. The chooser
  labels spatial hints with their region ID. This immediately displays the chosen
  authored text and records `automatic_hint_id`, `actual_hint_id`, `manual_override`,
  level, type, and exposure timestamp. The automatic diagnostic and first automatic
  hint ID stay intact. Further overrides append exposures and audit events. Overrides
  are rejected before Hint or after moving to Re-observe, and cross-item IDs are rejected.
- **Researcher notes:** write free text and explicitly save it. Notes are stored
  separately from participant responses; edits retain prior note text in audit events.
  Saving a note leaves an unfinished participant form and selected rectangle intact.
- **Reset current item:** creates a fresh session for the same item and participant.
  It preserves the previous log and responses, appends a reset event linking to the
  replacement, and clears the current participant draft and researcher note field.
- **Download JSON / Download CSV:** exports the latest saved current-session log at
  any stage. JSON contains the full event history; CSV has one row per session and
  serializes nested regions, transitions, diagnostics, and events as JSON cells.
  Spreadsheet formula-like free text is prefixed with an apostrophe in CSV only.
  Unsaved form drafts and unsaved researcher notes are not part of exports.

The participant projection allowlists public item information and shown hint
fields. It omits keyword lists, thresholds, diagnostic codes/objects, researcher
notes, automatic hint metadata, and the hint history. Expert information appears
only after the Reveal action. The participant UI renders no raw internal JSON.
Semantic diagnostic fields and authored distractor metadata stay exclusively in
the researcher API; the participant only receives the actual authored hint content
and the existing public hint fields.

Researcher endpoints require `X-SeasonLens-Researcher: 1`, sent by the debug UI.
This is a local demonstration-mode gate, **not authentication or authorization**.
Use the default localhost binding. A participant can deliberately enable debug
mode; studies needing access separation require a later authenticated researcher surface.

## Logs and API

The running server writes `runtime-data/seasonlens/{session_id}.json` after each
public mutation. Snapshots are refreshed, while the contained audit event trace
is append-only. Reset and item advancement preserve old files. Existing logs from
the point-selection MVP remain untouched; newly created logs use rectangles.

Logs include IDs/condition, stage transitions, separate initial/revised responses,
confidence, all component diagnostic flags and primary error, automatic/actual hint
IDs, override flag, type, numeric level, exposure sequence, reflection text/category,
researcher notes, and item start, initial submission, hint exposure, revision,
reveal, reflection submission, and completion timestamps. `difficulty_code`,
`hint_id`, and `expert_reveal_at` remain as compatibility aliases. Timestamps use
server UTC; `hint_shown_at` records server selection/exposure time, not measured
browser paint time. Event envelopes additionally retain their recorded timestamps.

Semantic analysis fields in JSON and CSV:

- `selected_semantic_region`, `selected_region_label`, `target_region_id`,
  `target_region_iou`, and `best_distractor_iou` refer to the initial diagnostic.
- `initial_selected_semantic_region` and `revised_selected_semantic_region` preserve
  transitions such as `leaf_region → terminal_bud`. Revised label, target IoU, and
  best distractor IoU also have separate `revised_*` fields.
- `initial_diagnostic` (also aliased as `diagnostic`) and `revised_diagnostic` contain
  independent full checks. Submitting a revision never replaces the initial checks.
- `region_hint_source` is `semantic_region`, `generic_region_miss`, or null for a
  cue/interpretation/correct hint. `region_hint_id` identifies the current spatial
  or generic region hint; it is null for other categories. These fields describe the
  actual hint, including manual overrides. `automatic_region_hint_source` and
  `automatic_region_hint_id` preserve the automatic routing decision separately.
  Every exposure in `hint_sequence` retains its own source/IDs and mapped region ID.

Before the relevant submission, diagnostic fields are null. Each Group C revision
may add a new authored exposure until the response is correct or Level 3 has been used.

Participant API: `GET /api/items`, `GET /api/items/{item_id}`,
`POST /api/sessions`, `GET /api/sessions/{session_id}`, and session actions
`initial-observation`, `reobserve`, `revision`, `reveal`, `reflection-stage`,
`reflection`, and `next-item`.
Researcher API: `GET /api/sessions/{session_id}/researcher`, `/log`, `/log.csv`,
and POST session actions `hint-override`, `researcher-notes`, `reset`.
All POST actions use JSON bodies. The HTTP boundary serializes access to the shared
in-memory runtime, and invalid submissions/transitions leave state and events intact.

Sessions remain in memory; server restart retains exported files but does not
restore or resume live sessions. There is no database, full Group B yoking,
counterbalancing, randomization, cross-item fading, LLM scoring/hints, delayed transfer
study, or statistical analysis. Validate content and calibrate region overlap before
a controlled experiment. Pointer accessibility and real-browser visual checks still
need participant/device testing; no keyboard rectangle editor is included.

## Verification and files

The repository check commands cover Python flow/API/domain behavior, JavaScript
interaction behavior, JavaScript syntax, and frontend TypeScript contracts. See the
latest task report or run the commands above for current counts. Real-browser visual
and device verification remains part of formative testing.

Current implementation map:

- `extensions/seasonlens/backend/src/seasonlens/{catalog,domain,regions,service,__init__}.py`
- `extensions/seasonlens/backend/tests/` — domain, flow, semantic-region, and HTTP checks
- `extensions/seasonlens/data/{demo_anemone_001,demo_solidago_001,demo_butterfly_weed_001}.json`
- `apps/api/main.py`, `apps/web/{index.html,app.js,styles.css}`
- `apps/web/assets/real/*.jpg`, `apps/web/tests/interaction.test.cjs`
- `packages/frontend-core/src/seasonlens.ts`
- `README.md`, `SEASONLENS_MVP.md`
