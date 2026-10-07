# RePlanAI Extension

## 1. Extension purpose

实现 persistent commitment-aware schedule repair。该扩展以 deterministic solver 为核心；生成式 Agent 不是必要条件。

## 2. Recommended intelligence mode

默认：

```text
rule-policy + deterministic solver + template explanation
```

可选 `live-llm` 只用于：

- 将自然语言 disruption 解析成 candidate structured edits；
- 转述已经由 solver 计算并验证的 diff。

任何解析结果在进入 solver state 前均需用户逐字段确认。

## 3. Domain state

```text
PlanningSession
├── plan_versions[]
├── tasks[]
├── fixed_events[]
├── availability_windows[]
├── commitments[]
│   ├── immutable_environmental
│   ├── pin
│   ├── prefer_to_keep
│   └── flexible
├── disruptions[]
├── repair_candidates[]
├── relaxation_records[]
└── approvals[]
```

关键 invariant：

1. active immutable constraint 和 Pin 不被自动违反；
2. 所有变更在提交前出现在 exact preview；
3. Pin relaxation 有明确 scope 和 approver；
4. accepted state 成为下一次 disruption 的输入。

## 4. Actions

| Action | Approval |
|---|---|
| `PARSE_DISRUPTION` | human_commit（确认解析字段） |
| `ADD_COMMITMENT` | human_commit |
| `CHANGE_COMMITMENT` | human_commit |
| `SOLVE_REPAIR` | auto_compute |
| `REQUEST_ALTERNATIVE` | auto_compute |
| `COMPUTE_MINIMAL_RELAXATIONS` | auto_compute |
| `PROTECT_DURING_PREVIEW` | human_commit |
| `APPROVE_RELAXATION` | human_commit |
| `REJECT_REPAIR` | human_commit |
| `ACCEPT_REPAIR` | human_commit |
| `UNDO_ACCEPTED_REPAIR` | human_commit |

## 5. Deterministic tools

```text
replanai.validate_plan
replanai.solve_lexicographic_repair
replanai.enumerate_alternative
replanai.compute_inclusion_minimal_relaxations
replanai.compute_exact_diff
replanai.explain_from_solver_facts
```

推荐 OR-Tools CP-SAT。Tool result 必须包含 solver status、objective tuple、exact change set、constraint violations 和 latency。

## 6. UI projections

- `calendar-plan`；
- `commitment-editor`；
- `repair-preview`；
- `constraint-conflict-panel`；
- `relaxation-negotiation`；
- `plan-version-history`。

## 7. Shared-platform adaptation

`AgentGateway` 使用 rule/replay adapter；`SOLVE_REPAIR` 返回 preview state，不直接 commit。只有 `ACCEPT_REPAIR` reducer 创建 Plan Version。

本扩展需要比其他扩展更严格的 transaction boundary：候选计划、批准和 active plan 必须是三个不同状态。

## 8. MVP boundary

- 一周时间范围；
- fixed-duration 或有限 splitting；
- 四类 disruption；
- 单用户；
- 不接入 LMS/email/calendar provider；
- 不预测成绩或任务重要性；
- explanation 优先 template-based。

## 9. Evaluation support

算法 benchmark conditions：

```text
full-reschedule
commitment-agnostic-minimal-repair
commitment-aware-repair
```

人因实验 conditions：

```text
commitments-absent / commitments-present
review-only / negotiable
```

导出 applicable private commitments、violations、prior approval、exact diff、repair iterations、completion time、reject/undo 和 understanding responses，以计算 UCVR。
