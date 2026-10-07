# VizWorkspace Extension

## 1. Extension purpose

建立 Human 和 Agent 共同读写的 evidence-bound argument state。研究核心是 Claim/Evidence relation、ownership、contested state 和 correction protocol，而不是恢复隐藏 Chain-of-Thought。

## 2. Agent mode

Agent 可以：

- 提出 Question、Claim 和 visual epistemic action；
- 将 tool result 提议为 SUPPORT/REBUT evidence；
- 对 relation 发起 challenge；
- 根据 human correction 读取新的 active state 后继续工作。

Agent 不能：

- 自动批准自己的 SUPPORT/REBUT interpretation；
- 覆盖用户拥有的 Claim；
- 把 numerical predicate verification 等同于因果或文化解释；
- 直接删除原始 relation。

## 3. Domain state

```text
ArgumentSession
├── questions[]
├── claim_versions[]
├── evidence_bindings[]
├── relations[]
│   ├── SUPPORTS | REBUTS | ALTERNATIVE_TO | MOTIVATES | SUPERSEDES
│   ├── proposer / approver
│   └── active | contested | rejected | superseded
├── analysis_states[]
├── candidate_actions[]
└── corrections[]
```

Claim status 和 relation status 分开保存；同一 evidence 可以关联多个 Claim，但每条 relation 有独立 ownership 和 review state。

## 4. Actions

| Action | Approval |
|---|---|
| `PROPOSE_QUESTION` | human_commit |
| `PROPOSE_CLAIM` | human_commit |
| `PROPOSE_VISUAL_ACTION` | human_commit 或 policy-based preview |
| `EXECUTE_VISUAL_ACTION` | auto_compute |
| `BIND_SELECTION_AS_EVIDENCE` | human_commit |
| `PROPOSE_SUPPORT` | human_commit |
| `PROPOSE_REBUT` | human_commit |
| `CONTEST_RELATION` | human_commit |
| `ACCEPT_RELATION` | human_commit |
| `REVISE_CLAIM` | human_commit |
| `REPLAY_EVIDENCE_STATE` | auto_read |
| `CHALLENGE_RELATION` | auto_read，仅产生待检查问题 |

## 5. Deterministic tools

```text
vizworkspace.execute_visual_action
vizworkspace.capture_binding
vizworkspace.replay_state
vizworkspace.validate_predicate
vizworkspace.reverse_lookup
vizworkspace.compare_versions
```

Tool 只能验证 exact binding 和明确 numerical predicate，不决定 SUPPORT/REBUT 的高层语义。

## 6. UI projections

- `current-visualization`；
- `argument-workspace`；
- `structured-history`；
- `activity-replay-strip`；
- `relation-inspector`；
- `ownership-contested-panel`。

## 7. 与 ReasonMap 的边界

本扩展不实现通用 downstream invalidation 和 affected-set repair。它关注：

```text
共同维护 relation
+ ownership
+ disagreement
+ collaborative correction
```

ReasonMap 关注 dependency change impact。两者可共享 record/version/replay 组件，但不得共享相同 primary task 和 outcome 叙述。

## 8. MVP boundary

- single analyst + one Agent；
- prepared analytical episodes；
- tabular data；
- visual actions 只含 filter/group/facet/compare/select/annotate；
- 不构建 multi-Agent debate；
- 不允许 Agent 生成任意前端代码。

## 9. Evaluation support

实验条件：

```text
vizworkspace-structured-history
vizworkspace-shared-argument
```

导出 planted-issue detection、evidence–claim reconstruction、relation/ownership identification、repair action、unnecessary correction、replay use 和 completion time。
