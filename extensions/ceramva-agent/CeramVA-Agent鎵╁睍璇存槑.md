# CeramVA-Agent Extension

## 1. Extension purpose

将模糊文化概念的多种 admissible operationalizations 转换为可执行分析规格，比较结果对定义选择的敏感性，并支持 object-grounded qualified claim。

## 2. Agent responsibilities

- 识别 target objects、comparison 和 ambiguous concept；
- 提出候选指标、组合规则、controls 和来源；
- 把获准定义转换为 structured specification；
- 调用确定性分析工具；
- 提示 omitted control、low-coverage subgroup 或 counterexample；
- 引用 result/object IDs 起草限定性 claim。

Agent 不批准自己的定义，不直接输出统计数值，也不把文化解释写成领域真理。

## 3. Domain state

```text
CeramInquiry
├── question
├── candidate_operationalizations[]
│   ├── indicators
│   ├── aggregation
│   ├── controls
│   ├── sources
│   └── validity/admissibility/version
├── analysis_specifications[]
├── result_profiles[]
│   ├── direction / estimate / interval
│   ├── coverage / measurement status
│   └── object provenance
├── sensitivity_classification
├── challenges[]
└── qualified_claim_versions[]
```

## 4. Actions

| Action | Approval |
|---|---|
| `PARSE_RESEARCH_QUESTION` | human_commit |
| `PROPOSE_OPERATIONALIZATION` | human_commit |
| `CHECK_ADMISSIBILITY` | auto_compute |
| `ADMIT_OPERATIONALIZATION` | human_commit |
| `COMPILE_ANALYSIS_SPEC` | auto_compute |
| `RUN_SPEC` | auto_compute |
| `COMPARE_OPERATIONALIZATIONS` | auto_read |
| `RETRIEVE_OBJECT_EVIDENCE` | auto_read |
| `CHALLENGE_PROFILE` | auto_read，仅生成待执行问题 |
| `RUN_CHALLENGE` | auto_compute |
| `CLASSIFY_PROFILE` | auto_compute |
| `DRAFT_QUALIFIED_CLAIM` | human_commit 后成为 active claim |

## 5. Deterministic tools

```text
ceramva.query_objects
ceramva.check_admissibility
ceramva.compile_spec
ceramva.compute_prevalence
ceramva.compute_diversity
ceramva.compute_decorative_coverage
ceramva.estimate_effect
ceramva.classify_profile
ceramva.retrieve_object_evidence
```

所有 partition、aggregation 和 resampling 都以 `object_id` 为单位，避免多图像/VQA records 造成 pseudo-replication。

## 6. UI projections

- `operationalization-editor`；
- `visual-osp`；
- `equivalent-table`；
- `definition-comparison`；
- `object-evidence-drawer`；
- `challenge-panel`；
- `qualified-claim-editor`。

## 7. 与 MOSAIC 的边界

CeramVA-Agent 的主轴是 operationalization sensitivity，语料集中于中国陶瓷。它不承担多馆藏 leave-one-out 和 collection/media joint sensitivity 的主要贡献。

可以共享：

- operationalization schema；
- admissibility workflow；
- analysis service；
- object evidence drawer；
- qualified claim editor。

## 8. MVP boundary

- 冻结 CiQi-VQA object-level subset；
- 一个模糊概念；
- 至少三种 admissible operationalizations；
- prevalence/diversity 为核心指标；
- decorative coverage 仅在可靠性验证通过后进入 confirmatory profile；
- 不实现 embedding exploration 或大量视觉复杂度 features。

## 9. Evaluation support

实验条件：

```text
single-definition-reference
equivalent-table
visual-osp
```

导出 sensitivity classification、decisive operationalization、object/counterexample inspection、qualified claim、confidence、time 和 workload。正式实验使用 frozen held-out objects、tool outputs 和 Agent messages。
