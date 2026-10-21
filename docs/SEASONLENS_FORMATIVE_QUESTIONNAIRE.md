# SeasonLens formative participant questionnaire v3

The authoritative source is
`SeasonLens_Formative_Participant_Questionnaire_v3_Bilingual.docx`. The executable,
versioned transcription is
`extensions/seasonlens/data/formative_questionnaire_v3.json`.

The implementation preserves the A–E structure and question IDs. Minor formatting
normalizations separate Chinese and English prompts, consistently space IDs, and
separate D5/D6 from their answer areas without changing meaning.

## Stable field map

| Section | Fields |
| --- | --- |
| A | `A1`, `A2`, `A3`, `A4`, `A5`, `A6`, `A6_INFO` |
| B | `B1`, `B2`, `B3`, `B4`, `B5`, `B5_CONFIDENCE` |
| C | `C1`, `C2`, `C3`, `C4`, `C5`, `C6` |
| D | `D1`, `D2`, `D3`, `D4`, `D_CONFIDENCE`, `D5`, `D6` |
| E | `E1`, `E2`, `E3`, `E3_WHY`, `E4` |

`D_CONFIDENCE` is an independent field after D4. D5 records when help would have
been wanted and why; D6 records the desired kind of help. E is released only after
all three linked SeasonLens prototype items are complete.

All questionnaire responses may be skipped, matching the participant notice.
Confidence fields accept 1–5 or blank. Choice values are stable language-neutral
codes; labels remain bilingual.

## Observation material IDs

- B: `B_COMPLETE_PLANT_001`
- C earlier: `C_SAME_PLANT_T1_001`
- C current: `C_SAME_PLANT_T2_001`
- D: `D_CHALLENGING_PLANT_001`

The PNG bytes were extracted directly from the authoritative DOCX without
re-encoding. The schema records the DOCX relationship ID, package path, and SHA-256
for each file. No species identification or external substitute has been added.

## Unaided-stage guarantee

B, C, and D are questionnaire-only stages. Their public projections contain no
correct answer, expert region, target region, scoring result, diagnosis, or hint.
Backend stage checks prevent early access, and only an authenticated researcher
with a valid CSRF token can release the next stage.
