# ReasonMap Extension

## 1. Extension purpose

在共享 Agentic VA session 上增加版本化语义 provenance、依赖传播和局部修复。核心研究对象是显式 assertion/evidence/analysis-state dependency，而不是 Agent 的隐藏推理。

## 2. Agent mode

- `live-llm`：从显式 statement 和已记录 action 中抽取候选语义记录；
- `replay`：正式 graph/table 实验中重放相同 extraction 和 Agent messages；
- Agent 只提出 candidate assertion、binding 和 dependency；
- human 可以确认、纠正、rebind、retract 或 supersede。

## 3. Domain state

```text
ReasoningSession
├── assertions[]
│   ├── assertion_id / version_id
│   ├── role: question | hypothesis | observation | conclusion | assumption
│   ├── actor / source spans
│   └── active/stale/contested/retracted/superseded
├── evidence_records[]
│   ├── binding_state
│   ├── predicate_state
│   └── inference_review_state
├── analysis_states[]
├── dependency_edges[]
├── argument_edges[]
├── correction_events[]
└── active_repair_branch
```

Dependency-bearing graph 必须为 DAG；`SUPERSEDES` 时间链和 argumentative overlay 不进入 invalidation traversal。

## 4. Actions

| Action | 作用 | Approval |
|---|---|---|
| `EXTRACT_ASSERTIONS` | 从明确文本创建候选 assertion records | human_commit |
| `PROPOSE_DEPENDENCY` | 提出依赖边 | human_commit |
| `BIND_EVIDENCE` | 绑定 evidence 与 analysis state | human_commit |
| `VALIDATE_PREDICATE` | 检查明确数值 predicate | auto_compute |
| `INVALIDATE_ROOT` | 指定 root error 并计算影响集 | human_commit |
| `TRACE_IMPACT` | 只读返回 dependency paths | auto_read |
| `RERUN_ANALYSIS_STATE` | 重算受影响 analysis state | auto_compute |
| `REVALIDATE_RECORD` | 标记新版本经审查 | human_commit |
| `SUPERSEDE_ASSERTION` | 创建 assertion 新版本 | human_commit |
| `RETRACT_ASSERTION` | 保留历史并撤回 active assertion | human_commit |
| `FINISH_REPAIR` | 检查无 unresolved required records | human_commit |

## 5. Deterministic tools

```text
reasonmap.capture_state
reasonmap.replay_state
reasonmap.validate_predicate
reasonmap.check_cycle
reasonmap.compute_affected_set
reasonmap.compute_dependency_paths
reasonmap.compare_versions
reasonmap.check_repair_completion
```

LLM extractor 不是 deterministic tool；其输出必须保留 source event IDs，并作为候选进入审核。

## 6. UI projections

- `provenance-graph`：time-aware layered graph；
- `semantic-table`：信息等价主对照；
- `impact-panel`：direct/transitive/unaffected records；
- `replay-view`：dataset、query、view spec、selection；
- `version-diff`：旧记录、新记录和 correction rationale；
- `repair-checklist`：remaining stale 和 untouched branches。

## 7. Shared-platform reuse

直接复用：

- append-only events；
- optimistic versioning；
- approval tray；
- replay AgentGateway；
- evidence inspector；
- condition parity checker。

本扩展新增：DAG validator、impact traversal、repair completion invariant 和 graph/table projections。

## 8. MVP boundary

- single analyst、single session；
- frozen tabular datasets；
- operation 仅限 filter/group/aggregate/select/compare；
- 30–60 semantic records per episode；
- prepared root errors 和 affected sets；
- 不支持任意 Python、外部 API 或跨 session replay。

## 9. Evaluation support

实验条件：

```text
reasonmap-semantic-table
reasonmap-provenance-graph
```

共享 episode 必须固定 records、warnings、replay links、repair actions 和 Agent output。扩展导出 root localization、selected affected set、repair actions、unnecessary edits、completion time 和 replay usage。
