# SeasonLens Questionnaire Consistency Audit

## Audit outcome

The current default participant questionnaire is executable schema version **3.2**. It contains **30 fields** across Sections A–E; **25 are required**. The project-maintained ethics-review questionnaire documents the same field IDs, wording, response types, requirements, conditions, materials, and versioning policy.

This repository change updates the active questionnaire and its renderer-facing schema. It does not claim ethics approval and does not alter stored participant records.

## Sources and authority

1. Active executable definition: `extensions/seasonlens/data/formative_questionnaire_v3_2.json`
2. Preserved v3.1 definition: `extensions/seasonlens/data/formative_questionnaire_v3_1.json`
3. Preserved legacy v3 definition: `extensions/seasonlens/data/formative_questionnaire_v3.json`
4. Participant renderer and validation: `apps/web/study.js`
5. Version-aware workflow, validation, dashboard data, and exports: `extensions/seasonlens/backend/src/seasonlens/study.py`
6. Project documentation: `docs/SEASONLENS_FORMATIVE_QUESTIONNAIRE.md`, `docs/FORMATIVE_STUDY_PLATFORM.md`, and `SeasonLens_Formative_Study_Questionnaire_Ethics_Review.md`

Executable definitions take precedence over prose documentation.

## Active v3.2 completeness map

| Stage | Active field IDs | Count | Required |
| --- | --- | ---: | ---: |
| A | `A1`, `A2`, `A3`, `A4`, `A5`, `A6`, `A6_INFO` | 7 | 2 |
| B | `B1`, `B2`, `B3`, `B4`, `B4_CONFIDENCE` | 5 | 5 |
| C | `C1`, `C2`, `C3`, `C4`, `C5`, `C6` | 6 | 6 |
| D | `D1`, `D2`, `D3`, `D4`, `D_CONFIDENCE`, `D5`, `D6` | 7 | 7 |
| E | `E1`, `E2`, `E3`, `E3_WHY`, `E4` | 5 | 5 |
| **Total** |  | **30** | **25** |

`A6_INFO` is shown only for the applicable nonblank A6 answers. `E3_WHY` is shown and required after any valid E3 selection. Required counts include conditional `E3_WHY` because it is required whenever applicable.

Study-entry consent controls and researcher-labelled metadata controls are not questionnaire fields and are not included in the total.

## v3.2 change audit

### Section B

The v3.1 viewing-distance question has been removed from the active definition. The v3.1 seasonal-judgment field and its confidence field have been renumbered so the final v3.2 sequence is:

`B1` → `B2` → `B3` → `B4` → `B4_CONFIDENCE`

The confidence scale retains numeric values 1–5 and its complete bilingual labels. Rendering and validation are schema-driven, so the deleted field is absent from new forms, drafts, submissions, dashboard detail, and per-study exports.

### Section C

Only C2, C3, and C4 wording changed. Their active English prompts are:

- `C2`: When comparing the two images, which parts of the plant did you focus on? What differences did you notice in those parts?
- `C3`: When comparing the two images, was there anything you found difficult to judge or were unsure about? Why? If not, you may say so.
- `C4`: Based on the differences between the two images, what growth-related change do you think the plant might be undergoing? Why do you think so?

C1, C5, and C6 are byte-for-byte unchanged between the v3.1 and v3.2 schemas. Their IDs, response types, and required status are unchanged.

## Historical compatibility audit

Question IDs are always interpreted under the stored questionnaire version:

| Meaning | v3.1 | v3.2 |
| --- | --- | --- |
| Viewing distance, angle, or position | `B4` | Removed |
| Seasonal judgment | `B5` | `B4` |
| Seasonal-judgment confidence | `B5_CONFIDENCE` | `B4_CONFIDENCE` |

- New studies use v3.2.
- Existing and unfinished v3.1 studies continue to load the preserved v3.1 schema, so their questions and saved drafts do not change midway.
- No migration rewrites historical answers or IDs.
- Participant detail and all exports retain the stored questionnaire version. Combined XLSX answer rows carry an explicit questionnaire-version column, preventing old and new `B4` answers from becoming an unlabeled shared field.
- Records with an unsupported or unreliable version can still be exported with their stored version value and raw answer IDs. The application does not guess a schema or reinterpret those answers.

The preserved v3 workflow remains available for its historical records and is not the active questionnaire.

## Materials, workflow, and feature preservation

- The material set remains version 3.1 because no observation image changed in this questionnaire revision.
- Section D continues to use `/assets/study/section-d-solidago.png`.
- The self-guided sequence remains A → B → C → D → E → Completion.
- Sections A, D, and E, confidence values/labels, bilingual rendering, autosave/recovery, required-field validation, authentication, deletion, dashboard behavior, and export formats remain in place.
- The responsive sticky observation layout remains shared by Sections B, C, and D. Section C retains its two-image material layout.

## Prototype scope

The separate three-item prototype remains disabled for newly created v3.2 integrated studies. Its Chinese-only prompts, guidance, feedback, expert reveal, and reflection branches are historical/standalone material and are not included in the active 30-field count. If that prototype is included in a future bilingual ethics submission, approved English translations are still required.

## Ethics and external-document limitations

This audit verifies repository sources only. It cannot establish ethics approval or confirm external consent forms, recruitment materials, verbal scripts, or files not supplied in the repository. Any external Word questionnaire must be synchronized manually with v3.2, including the Section B renumbering, revised C2–C4 wording, version label, and 30-field total.
