# SeasonLens

SeasonLens is an integrated formative-study platform for investigating observation-first scaffolding and novice ecological noticing.

## Live Demo

The deployed prototype can be accessed directly in a web browser:

- **Participant interface:** https://seasonlens-production.up.railway.app/
- **Researcher interface:** https://seasonlens-production.up.railway.app/researcher.html

No local installation is required for the online demo.

> Repository support for PostgreSQL persistence and authenticated researcher access is implemented. Existing live deployments must be redeployed with the documented database and credential variables before those guarantees apply.

## Integrated study flow

```text
Welcome/Consent → A → B → C → D → E → Completion
```

B–D are backend-gated, entirely unaided stages. New studies progress automatically
after each explicit submission; future stages and images remain inaccessible until
then. B uses prototype item 1's image, D uses prototype item 2's image, and C keeps
its approved temporal pair. The standalone prototype remains at `/prototype.html`.

SeasonLens is currently deterministic: ecological facts, accepted evidence regions, stage answers, and hints are frozen authored content. Rule-based diagnosis selects an appropriate hint from that library; the prototype does not use an LLM or vision model to generate botanical answers.

## Current research goal

SeasonLens studies whether asking novices to locate and describe visible plant evidence before receiving guidance can support more deliberate ecological noticing. Region selection is an explicit interaction proxy, not gaze measurement.

## Current prototype flow

```text
Select region
→ Describe visible evidence
→ Bounded stage judgement
→ Explain evidence reasoning and judgement source
→ Rate confidence
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
- Required pre-commit evidence reasoning (`visual_evidence_reason`) and judgement-source selection (`judgement_source`)
- Layered deterministic diagnosis
- Frozen authored adaptive hints with Levels 1–3
- Re-diagnosis after every revised attempt and a Level 3 stopping rule
- Positive confirmation that bypasses guidance for initially correct responses
- Expert reveal and path-specific reflection
- JSON/CSV logging and append-only events
- Simplified Chinese participant interface and Chinese authored participant content
- Researcher/debug panel, item switching, reset, and downloads
- Group A answer-first behavior
- Group C error-contingent adaptive guidance
- Bilingual A–E questionnaire with stable field IDs and draft resume
- Self-guided, server-ordered A→B→C→D→E progression for new studies
- Versioned legacy researcher-assisted workflow for existing studies
- SQLite/PostgreSQL persistence with startup migrations
- Authenticated researcher dashboard with CSRF protection
- Independent and combined JSON/CSV, XLSX, and complete ZIP exports

## Experimental conditions

- **Group A — Answer-first:** implemented in the current prototype.
- **Group B — Yoked non-contingent guidance:** selectable placeholder only; full participant-to-participant yoked matching is not implemented.
- **Group C — Error-contingent adaptive guidance:** implemented with layered diagnosis and Level 1/2/3 escalation.

## Planned / not yet complete

- Full Group B yoked matching
- Cross-item automatic fading
- Ecological expert validation of content, regions, and thresholds
- Main experimental study
- Real-browser/device accessibility validation

## How to run

From the repository root:

```powershell
python apps/api/main.py
```

- Participant: <http://127.0.0.1:8000>
- Standalone prototype: <http://127.0.0.1:8000/prototype.html>
- Researcher: <http://127.0.0.1:8000/researcher.html>

Run the checks with:

```powershell
python scripts/check_seasonlens.py
node --check apps/web/app.js
node --check apps/web/study.js
node --check apps/web/researcher.js
node --test apps/web/tests/*.test.cjs
```

See [SEASONLENS_MVP.md](SEASONLENS_MVP.md) for implementation, logging, and
limitations, and the [formative questionnaire](docs/SEASONLENS_FORMATIVE_QUESTIONNAIRE.md)
for the questionnaire mapping. See [the integrated platform guide](docs/FORMATIVE_STUDY_PLATFORM.md)
for persistence, authentication, researcher workflow, exports, and Railway setup.

## Project status

This repository implements the integrated formative-study platform; ecological content validation and a final main-study protocol remain separate research tasks.
