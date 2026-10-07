# SeasonLens

SeasonLens is a formative research prototype investigating observation-first scaffolding for novice ecological noticing.

The current implementation is deterministic: ecological facts, accepted evidence regions, stage answers, and hints are frozen authored content. Rule-based diagnosis selects an appropriate hint from that library; the prototype does not use an LLM or vision model to generate botanical answers.

## Current research goal

SeasonLens studies whether asking novices to locate and describe visible plant evidence before receiving guidance can support more deliberate ecological noticing. Region selection is an explicit interaction proxy, not gaze measurement.

## Current prototype flow

```text
Select region
→ Describe visible evidence
→ Bounded stage judgement
→ Commit
→ Deterministic diagnostic
→ Conditional guidance
→ Reveal
→ Reflect
```

Correct initial responses skip unnecessary guidance and re-observation. Incorrect responses receive authored guidance targeted to `REGION_MISS`, `CUE_MISIDENTIFIED`, or `INTERPRETATION_ERROR`; Group C can escalate from Level 1 to Level 3 and re-diagnoses every revision.

## Current items

The active order is:

1. *Anemone virginiana*
2. *Solidago canadensis*
3. *Asclepias tuberosa*

All three use project-local whole-plant or whole-branch photographs so the participant must locate the relevant structure. Item metadata and frozen hint libraries are in `extensions/seasonlens/data/`.

## Implemented

- Whole-plant observation items and explicit rectangle selection
- Normalized intersection-over-union (IoU) scoring
- Visible-cue checking
- Bounded, item-specific stage judgement using stable radio-button IDs
- Layered deterministic diagnosis
- Frozen authored adaptive hints with Levels 1–3
- Re-diagnosis after every revised attempt and a Level 3 stopping rule
- Positive confirmation that bypasses guidance for initially correct responses
- Expert reveal and path-specific reflection
- JSON/CSV logging and append-only events
- Researcher/debug panel, item switching, reset, and downloads
- Group A answer-first behavior
- Group C error-contingent adaptive guidance

## Experimental conditions

- **Group A — Answer-first:** implemented in the current prototype.
- **Group B — Yoked non-contingent guidance:** selectable placeholder only; full participant-to-participant yoked matching is not implemented.
- **Group C — Error-contingent adaptive guidance:** implemented with layered diagnosis and Level 1/2/3 escalation.

## Planned / not yet complete

- Full Group B yoked matching
- Cross-item automatic fading
- Ecological expert validation of content, regions, and thresholds
- Formative participant study and calibration
- Main experimental study
- Persistent database and authenticated researcher access
- Real-browser/device accessibility validation

## How to run

From the repository root:

```powershell
python apps/api/main.py
```

- Participant: <http://127.0.0.1:8000>
- Researcher/debug: <http://127.0.0.1:8000/?debug=1>

Run the checks with:

```powershell
python scripts/check_seasonlens.py
node --check apps/web/app.js
node --test apps/web/tests/interaction.test.cjs
```

See [SEASONLENS_MVP.md](SEASONLENS_MVP.md) for implementation, logging, and
limitations, and the [formative questionnaire](docs/SEASONLENS_FORMATIVE_QUESTIONNAIRE.md)
for the path-aligned evaluation wording.

## Project status

This repository currently represents the formative prototype rather than the final main-study system.
