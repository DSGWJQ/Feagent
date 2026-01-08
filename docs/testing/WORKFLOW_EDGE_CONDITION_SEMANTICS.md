# Workflow `edge.condition` 语义（可验收规范）

本规范用于定义工作流引擎对 `edge.condition` 的门控（gating）行为：它决定**节点是否执行**与**节点能拿到哪些上游 inputs**。

目标：把行为明确到可测试的 truth table，并与现有实现保持一致，不引入“按条件跳转/goto”或破坏 DAG 无环约束。

## 术语

- **incoming edge**：指向当前节点的边。
- **gating**：当前节点在执行前，会遍历其 incoming edges，根据 `edge.condition` 判断是否允许执行。
- **OR join（默认）**：多个 incoming edges 时，满足任一条件即可执行（至少有一条边“通过”）。
- **input filtering**：只有条件满足的那部分 incoming edges，其 source 输出才会进入当前节点的 `inputs`。

## Truth Table（核心）

对每一条 `edge.condition`：

1. `condition is None` 或 `condition == ""`（仅空白也视为 `""`）
   - 语义：无条件通过
   - gating：通过
   - input filtering：该 edge 的 source 输出会进入 inputs

2. `condition` 是字符串表达式，但求值抛异常（语法错误/访问不存在字段等）
   - 语义：fail-closed（视为 `False`）
   - gating：不通过
   - input filtering：该 edge 的 source 输出不会进入 inputs

3. `condition` 是字符串表达式，求值成功
   - 语义：以求值结果的 truthy/falsy 决定是否通过
   - gating：通过/不通过
   - input filtering：通过则进入 inputs，否则不进入

## 表达式兼容性（最小但稳定）

- 运算符归一化（JS-ish → Python-ish）：
  - `===` → `==`
  - `!==` → `!=`
  - `&&` → `and`
  - `||` → `or`
  - `true/false`（大小写不敏感）→ `True/False`
- 仅用于条件判断（gating），不提供“跳转/控制流”能力。

## `conditional` 输出兼容

为兼容 Conditional 节点输出，若 `edge.condition` 是 `true/false`，并且 source 输出为 dict：

- 若存在 `branch`（字符串且为 `true/false`），优先使用 `branch` 匹配。
- 否则尝试使用 `result`：
  - `result` 为 `bool`：按布尔值匹配
  - `result` 为 `int|float`：按 `bool(result)` 匹配

## 多入边（OR join + input filtering）

节点执行条件：当且仅当其 incoming edges 中 **至少有一条通过** 时执行。

节点 inputs：仅包含通过条件的 source 输出。未通过的边，即使 source 节点已执行，其输出也不会注入 inputs。

## 与代码/测试的映射

- 引擎实现：`src/domain/services/workflow_engine.py`
  - gating：`_should_execute_node(...)`
  - input filtering：`_get_node_inputs(...)`
  - 求值与 fail-closed：`_evaluate_edge_condition(...)`

- 单测映射（至少 3 条）：
  - `tests/unit/domain/services/test_workflow_engine_edge_condition_semantics.py`
    - 空/None 条件无条件通过
    - 求值异常 fail-closed（跳过节点）
    - 多入边 OR join + input filtering
  - 现有回归：
    - `tests/unit/domain/services/test_workflow_executor.py`
    - `tests/integration/test_workflow_condition_gating.py`
