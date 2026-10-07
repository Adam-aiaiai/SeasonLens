# MOSAIC Extension

## 1. Extension purpose

协调 Definition × Collection/Media 两轴敏感性分析，并从 matrix cell 回到 object-level evidence。Agent 编排分析，不直接计算统计结果，也不对未知历史总体作推断。

## 2. Agent responsibilities

- 解析问题中的 concept 和 comparison；
- 提出 candidate definitions 和 data conditions；
- 要求执行 admissibility check；
- 运行或比较 matrix cells；
- 找 counterexamples、boundary cases 和 low-coverage cells；
- 基于 cell/evidence IDs 起草 qualified claim。

Human 批准 definitions 并负责 interpretive significance。Deterministic tools 负责所有数值。

## 3. Domain state

```text
MosaicInquiry
├── question
├── concept_definitions[]
│   ├── family / source / rule
│   ├── applicable_media
│   └── admissibility_status
├── data_conditions[]
│   ├── collections / media / periods
│   └── inclusion and holdout rule
├── matrix_cells[]
│   ├── estimate / interval / direction
│   ├── n / missingness / validity
│   └── object_set / provenance
├── sensitivity_classification
├── object_evidence_sets[]
└── qualified_claim_versions[]
```

## 4. Actions

| Action | Approval |
|---|---|
| `PROPOSE_DEFINITION` | human_commit |
| `ADMIT_DEFINITION` | human_commit |
| `PROPOSE_DATA_CONDITION` | human_commit |
| `RUN_CELL` | auto_compute |
| `RUN_MATRIX` | auto_compute，有计算预算上限 |
| `COMPARE_ROW` | auto_read |
| `COMPARE_COLUMN` | auto_read |
| `RETRIEVE_OBJECTS` | auto_read |
| `CLASSIFY_SENSITIVITY` | auto_compute |
| `SUMMARIZE_LIMITS` | auto_read |
| `DRAFT_QUALIFIED_CLAIM` | human_commit 后成为 active claim |

## 5. Deterministic tools

```text
mosaic.audit_corpus
mosaic.check_definition_admissibility
mosaic.compute_cell
mosaic.compute_missingness
mosaic.leave_one_collection_out
mosaic.retrieve_object_evidence
mosaic.classify_sensitivity
mosaic.compare_cells
```

每个 cell tool result 必须带 object IDs、filters、measurement version、sample counts、missingness categories 和 dataset checksum。

## 6. UI projections

- `matrix-overview`；
- `equivalent-table`；
- `cell-comparison`；
- `object-evidence-drawer`；
- `coverage-missingness-panel`；
- `qualified-claim-editor`。

Direction/effect、uncertainty、coverage 和 warning 不应压缩为单一颜色或 score。

## 7. 与 CeramVA-Agent 的边界

MOSAIC 必须保留第二轴及其独立研究价值：

- multiple collections；
- collection holdout；
- media composition；
- heterogeneous metadata；
- missingness ontology；
- definition × composition joint sensitivity。

如果只比较多个定义，它将退化为 CeramVA-Agent。

## 8. MVP boundary

推荐先做：

- 2 个馆藏；
- 1 个 motif；
- 1 个主要 medium，第二 medium 仅在 audit 通过后进入；
- 2 个 observable measures；
- 3 个 time bins；
- 预计算 matrix cells；
- replication motif 作为投稿扩展。

## 9. Evaluation support

实验条件：

```text
single-condition-reference
equivalent-table
visual-matrix
```

主对照冻结相同 Agent output、cells、labels、evidence links 和 controls。导出 sensitivity classification、affected-axis selection、object inspection、qualified claim、confidence 和 time。
