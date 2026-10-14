# SeasonLens formative questionnaire

This questionnaire is aligned with the current formative prototype. It evaluates interaction clarity and the observation-first scaffolding experience; it is not the final main-study instrument.

## Participant task wording

For each item:

1. Select the region that best contains the visual evidence supporting your judgement.
2. Describe only what you can directly see in the selected region.
3. Choose the stage that best describes the plant from the provided options.
4. Explain why the visible image evidence supports that stage.
5. Select the main judgement source: image evidence, prior plant-observation
   experience, learned knowledge, guessing, or other.
6. Record confidence from 1 (low) to 5 (high), review, and commit.

The observation response concerns visible evidence. The bounded stage choice records
the participant's judgement separately. The required initial reasoning fields are
stored as `visual_evidence_reason` and `judgement_source`; they are collected before
the first commit and are not part of the post-reveal reflection.

## Path-specific reflection

- **No recorded hint exposure:** the hint-learning question is omitted.
- **At least one recorded hint exposure:** “提示是否帮助你注意到或理解了之前没有发现的植物特征？如果有，你学到了什么？”

The prompt is open-ended and permits participants to report that the hint did not
help. Visibility follows recorded hint exposure, not inferred correctness.

## Post-task formative questions

These questions form an **external post-task questionnaire**. They are study
materials, not fields implemented in the SeasonLens website. The website implements
only the in-flow, path-specific reflection above.

Use a 1–5 agreement scale unless marked open response.

1. The region-selection instruction was clear.
2. It was clear that the observation box asked for visible features rather than a stage answer.
3. The available stage choices were understandable.
4. The sequence of steps was easy to follow.
5. The expert reveal was easy to compare with my response.
6. When guidance appeared, it directed my attention without simply giving me the answer. *(Ask only if guidance was received.)*
7. What, if anything, was confusing about selecting a region? *(Open response.)*
8. What, if anything, was confusing about describing visible evidence? *(Open response.)*
9. What, if anything, was confusing about choosing a stage? *(Open response.)*
10. What would you change about the guidance, reveal, or reflection? *(Open response.)*

## Researcher note

Group B is a visible but incomplete formative placeholder. Do not describe it to participants or reviewers as full yoked matching. The current prototype uses deterministic rule-based diagnosis and a frozen authored hint library; it does not generate ecological answers with an LLM or vision model.
