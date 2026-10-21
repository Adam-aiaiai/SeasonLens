# SeasonLens formative participant questionnaire

The authoritative source for the original instrument is
`SeasonLens_Formative_Participant_Questionnaire_v3_Bilingual.docx`. Its preserved
executable transcription remains at
`extensions/seasonlens/data/formative_questionnaire_v3.json`.

The current default is the bilingual v3.1 revision at
`extensions/seasonlens/data/formative_questionnaire_v3_1.json`. It preserves the
A–E structure, IDs, response types, observation-first intent, uncertainty options,
and D5/D6 constructs. Wording in B–D now foregrounds visible evidence of seasonal
plant conditions and changes without identifying a correct stage or expected cue.

## Stable field map

| Section | Fields |
| --- | --- |
| A | `A1`, `A2`, `A3`, `A4`, `A5`, `A6`, `A6_INFO` |
| B | `B1`, `B2`, `B3`, `B4`, `B5`, `B5_CONFIDENCE` |
| C | `C1`, `C2`, `C3`, `C4`, `C5`, `C6` |
| D | `D1`, `D2`, `D3`, `D4`, `D_CONFIDENCE`, `D5`, `D6` |
| E | `E1`, `E2`, `E3`, `E3_WHY`, `E4` |

`D_CONFIDENCE` remains an independent field after D4. D5 records when help would
have been wanted and why; D6 records the desired kind of help. All questions remain
skippable. Confidence fields accept 1–5 or blank, and choice values remain stable
language-neutral codes.

## v3.1 materials

- B: `B_PROTO_ITEM_1_ANEMONE_001`, directly referencing prototype item 1
  (`/assets/real/anemone_virginiana_001.jpg`).
- C earlier: `C_SAME_PLANT_T1_001` (unchanged).
- C current: `C_SAME_PLANT_T2_001` (unchanged).
- D: `D_PROTO_ITEM_2_SOLIDAGO_001`, directly referencing prototype item 2
  (`/assets/real/solidago_canadensis_001.jpg`).

The schema records source provenance and SHA-256 for every image. Existing v3
study rows retain their original material records; new rows store material-set
version `3.1`.

## Workflow and unaided-stage guarantee

New v3.1 studies use `study_mode=self_guided` and
`enable_prototype_stage=false`: Consent→A→B→C→D→E→Completion. E refers only to
the observation tasks completed in B, C, and D.

B, C, and D projections expose only image paths, material IDs, task metadata, and
question fields. They contain no correct answer, expert or target region, score,
diagnosis, hint, or reveal. Server-side transitions prevent future-section access,
duplicate submission, and stage skipping while preserving drafts and resume.

Historical v3 studies retain their stored researcher-assisted workflow and may
continue through the linked prototype stage. `/prototype.html` and its authored
items, diagnostics, hints, logs, and tests remain unchanged.
