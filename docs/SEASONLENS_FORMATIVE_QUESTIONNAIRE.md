# SeasonLens formative participant questionnaire

The active bilingual questionnaire is v3.2 at
`extensions/seasonlens/data/formative_questionnaire_v3_2.json`. The original v3
instrument and the complete v3.1 definition remain at
`formative_questionnaire_v3.json` and `formative_questionnaire_v3_1.json` for
historical interpretation and in-progress study recovery.

## Active v3.2 field map

| Section | Fields |
| --- | --- |
| A | `A1`, `A2`, `A3`, `A4`, `A5`, `A6`, `A6_INFO` |
| B | `B1`, `B2`, `B3`, `B4`, `B4_CONFIDENCE` |
| C | `C1`, `C2`, `C3`, `C4`, `C5`, `C6` |
| D | `D1`, `D2`, `D3`, `D4`, `D_CONFIDENCE`, `D5`, `D6` |
| E | `E1`, `E2`, `E3`, `E3_WHY`, `E4` |

The executable schema contains 30 fields: 7 + 5 + 6 + 7 + 5. Of these, 25
are required; `A2`, `A4`, `A5`, `A6`, and `A6_INFO` are optional. `A6_INFO` is
shown only after a nonblank A6 response other than `never`; `E3_WHY` is required
when E3 has a selection. Drafts may remain incomplete, but applicable required
fields must be answered before submission.

### Section B v3.2 change

The former v3.1 B4 about changing viewing distance, angle, or position is not in
v3.2. The former seasonal-judgment B5 is now B4, followed immediately by the
renamed numeric confidence field B4_CONFIDENCE. No active Section B ID has a gap.

### Section C v3.2 change

C2 now asks which plant parts were compared and what differed. C3 asks about
difficulty or uncertainty without assuming it occurred. C4 asks participants to
connect visible differences to a possible growth-related change and explain why.
C1, C5, and C6 are unchanged from v3.1.

## Materials

Questionnaire v3.2 reuses material-set version `3.1` without changing images:

- B: `B_PROTO_ITEM_1_ANEMONE_001` at
  `/assets/real/anemone_virginiana_001.jpg`.
- C: `C_SAME_PLANT_T1_001` and `C_SAME_PLANT_T2_001`.
- D: `D_PROTO_ITEM_2_SOLIDAGO_001` at
  `/assets/study/section-d-solidago.png`.

The schema records project-relative paths, provenance, and SHA-256 values. The
participant projection omits hashes and provenance.

## Workflow and version compatibility

New v3.2 studies use `study_mode=self_guided` and
`enable_prototype_stage=false`: Consent → A → B → C → D → E → Completion.
The prototype is not part of this default flow.

Every study stores its questionnaire version at creation. Resume, autosave,
validation, and submission resolve that stored version, so a partially completed
v3.1 study continues with the preserved v3.1 IDs and wording. Researcher details
and every export expose `questionnaire_version`; raw response IDs are never
renamed. Consequently, v3.1 B4 (viewing position), B5 (seasonal judgment), and
B5_CONFIDENCE remain distinct from v3.2 B4 (seasonal judgment) and
B4_CONFIDENCE. Unknown versions remain researcher-readable/exportable as raw IDs
but are not projected to participants using a guessed schema.

Historical v3 studies retain their researcher-assisted workflow and may continue
through the linked prototype stage. No stored response is migrated or rewritten.

## External-document synchronization

The repository does not contain an editable copy of the external Word
questionnaire named by the historical schemas. That Word document requires
manual synchronization with the v3.2 definition before supervisor or ethics
submission. This documentation records implementation state only and does not
claim ethics approval.
