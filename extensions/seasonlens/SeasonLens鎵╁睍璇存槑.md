# SeasonLens Extension

> Status: this repository contains a formative prototype, not the final main-study
> system. Fading, full yoking, expert validation, and the main study remain planned.

## 1. Extension purpose

当前 formative prototype 实现 observation-first 和 error-contingent scaffolding。
跨 item fading 与 delayed unaided outcome 属于后续主实验设计，尚未实现。

## 2. Recommended intelligence mode

默认使用 `rule-policy`：

- frozen cue/hint library；
- frozen difficulty classifier；
- finite hint hierarchy；
- deterministic fading rules。

即使接入多模态模型，它也只能提出 observable cue candidate；正式实验中的 ecological content 必须来自已验证 library。模型不得自由生成物种或物候事实。

## 3. Domain state

```text
LearningSession
├── participant_pseudonym
├── station_and_item
├── attempts[]
│   ├── selected_regions
│   ├── selected_cues
│   ├── judgment / confidence
│   └── evidence_response
├── difficulty_codes[]
├── hint_exposures[]
├── fading_state
├── comparison_initiation
└── condition_assignment
```

Region selection 只表示 overt selection proxy，不表示 gaze 或 covert attention。

## 4. Actions

| Action | Approval |
|---|---|
| `RECORD_INITIAL_OBSERVATION` | human_commit |
| `CLASSIFY_DIFFICULTY` | auto_compute |
| `SHOW_POSITIVE_FEEDBACK` | auto_compute |
| `SELECT_ALLOWED_HINT` | auto_compute |
| `REVEAL_HINT` | rule-controlled |
| `RECORD_REOBSERVATION` | human_commit |
| `RECORD_FEEDBACK_RESPONSE` | human_commit |
| `UPDATE_FADING_STATE` | auto_compute |
| `OPEN_TEMPORAL_REFERENCE` | human_commit/logged action |
| `START_UNAIDED_ASSESSMENT` | study_admin |
| `DISABLE_ASSISTANCE` | study_admin |

## 5. Deterministic tools/policies

```text
seasonlens.validate_region_selection
seasonlens.classify_difficulty
seasonlens.select_hint_from_library
seasonlens.apply_yoking_schedule
seasonlens.update_fading
seasonlens.score_structured_response
seasonlens.verify_assistance_disabled
```

Open-response strategy scoring应由 condition-blind human raters 完成；自动 scorer 只能做辅助或技术验证。

## 6. UI projections

- `field-observation-flow`；
- `region-selection-overlay`；
- `cue-selection`；
- `evidence-entry`；
- `progressive-hint-panel`；
- `collapsed-temporal-reference`；
- `study-stage-controller`。

系统默认应把注意力带回真实植物，而不是增加不必要的 screen interaction。

## 7. Experimental condition engine

```text
answer-first
observation-first-yoked
observation-first-contingent
unaided-posttest
```

当前 Group A answer-first 和 Group C error-contingent adaptive guidance 已实现。
Group B 可选，但只是 non-contingent placeholder；完整的 participant-to-participant
yoking assignment 和 matching 尚未实现，不应视为已完成功能。

## 8. MVP boundary

- 约 6 株/类具有可重复转变的 plants；
- 少量 cue families；
- authored hint library；
- 两次 learning session；
- immediate + delayed unaided assessment；
- 不做开放物种识别；
- 不把 region click 解释为 eye tracking。

## 9. Operational risk controls

- 项目第一周开始 weekly reference photography；
- 准备标准化 image fallback，但 physical-plant endpoint 不可被替代；
- condition recruitment 按 weekly/site block 平衡；
- 保存 weather、station、plant state 和 exact delay；
- 预留 attrition 和户外 backup dates。

## 10. Evaluation export

导出 baseline、condition、item、region/cue/comparison/evidence responses、hint dose、observation/interface time、fading state、delay、site/week 和 post-test stage。Delayed test 中 assistance 必须在系统层强制关闭并写入 audit event。

## 11. Current runnable formative prototype

The current prototype exposes Group A, the explicitly incomplete Group B placeholder,
and Group C across three authored items. It reuses the shared `ActionProposal`, policy, deterministic
tool registry, versioned `StateSnapshot`, reducer, and append-only event
contracts. Its explicit stages are:

```text
Initial correct:
OBSERVE → INITIAL_COMMITTED → POSITIVE_FEEDBACK → REVEAL → REFLECTION → COMPLETE

Initial incorrect (Group C):
OBSERVE → INITIAL_COMMITTED → HINT → REOBSERVE → re-diagnose
→ HINT (when another tier is available) or REVISED_COMMITTED
→ REVEAL → REFLECTION → COMPLETE
```

The active item and hint libraries are the three JSON files for Anemone,
Solidago, and Butterfly weed under `data/`. The runtime
implementation is under `backend/src/seasonlens/`; the composition root and web
projection are under `apps/api/` and `apps/web/`.

MVP-local simplifications are intentional: three image items, normalized rectangle
selection, stable-ID stage scoring with a legacy keyword fallback, literal cue
matching, and local JSON logs. Full yoking, cross-item fading, LLM/vision inference,
a database, temporal history, expert validation, participant studies, and delayed
post-test are not implemented. These limitations do not alter the proposal's study logic
or its requirement for a later delayed unaided physical-plant endpoint.
