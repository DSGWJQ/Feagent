# Phase 2: 对话Agent智能规划增强开发计划

## 需求概述

**目标**：为ConversationAgent增强智能规划能力，使其能从用户的模糊自然语言描述中自动构建包含复杂逻辑的工作流。

**核心能力**：
1. **自然语言→结构化规划**：识别决策点、循环迭代、依赖顺序
2. **动态工作流编排**：自动生成条件节点（布尔分支）+ 循环节点（集合遍历）
3. **反馈驱动调整**：根据执行结果动态修改条件表达式、循环策略

**示例场景**：
```
用户输入："分析多个数据集并根据数据质量决定预处理"

Agent应识别：
- 循环：多个数据集
- 条件判断：数据质量检查
- 分支处理：高质量→直接分析，低质量→预处理→分析

自动生成工作流：
1. LOOP节点（遍历数据集）
2. CONDITION节点（质量检查）
3. 分支边（连接到不同子工作流）
```

## Codex分析摘要

### 现有能力（Phase 1已完成）
- ✅ WorkflowAgent 支持边级条件判断（ExpressionEvaluator）
- ✅ NodeType.LOOP 支持 for_each/map/filter 三种循环类型
- ✅ ExpressionEvaluator 支持多层上下文（global/workflow/context/item）

### 关键Gap（需在Phase 2解决）
- ❌ ConversationAgent 规划时未识别控制流语义
- ❌ NodeType.CONDITION 未作为决策节点执行（仅边条件）
- ❌ NodeRegistry 配置字段与 WorkflowAgent 实际使用不一致
- ❌ 无反馈驱动的运行时更新接口

## 实现方案（按优先级排序）

### Priority 1: 统一控制流配置与执行支持

**目标**：对齐 NodeDefinition/NodeRegistry/WorkflowAgent 的配置字段，支持 CONDITION 节点执行

**修改文件**：
- `src/domain/services/node_registry.py`
- `src/domain/agents/node_definition.py`
- `src/domain/agents/workflow_agent.py`

**关键修改**：
1. NodeRegistry schema 对齐（LOOP 使用 collection_field, transform_expression, filter_condition）
2. NodeDefinition 验证 CONDITION/LOOP 必填字段
3. WorkflowAgent 增加 `evaluate_condition_node()` 方法

**测试用例**（tests/unit/domain/agents/test_node_definition_control_flow.py）：
- [ ] test_node_registry_loop_schema_fields
- [ ] test_condition_node_requires_expression
- [ ] test_loop_node_requires_loop_type_and_collection
- [ ] test_workflow_agent_executes_condition_node

---

### Priority 2: ExpressionEvaluator 增强

**目标**：支持表达式编译复用、变量解析辅助方法

**修改文件**：
- `src/domain/services/expression_evaluator.py`

**新增方法**：
```python
def compile_expression(expression: str) -> ast.AST:
    """预编译表达式为AST节点，供重复使用"""

def evaluate_compiled(
    compiled_ast: ast.AST,
    context: dict,
    workflow_vars: dict | None = None,
    global_vars: dict | None = None
) -> Any:
    """执行编译后的表达式"""

def resolve_variables(output_dict: dict) -> dict:
    """扁平化节点输出供条件使用"""
```

**测试用例**（tests/unit/domain/services/test_expression_evaluator_compiled.py）：
- [ ] test_compile_expression_returns_ast
- [ ] test_evaluate_compiled_reuses_ast
- [ ] test_resolve_variables_flattens_nested_dict

---

### Priority 3: ConversationAgent 控制流规划 ⭐ 核心功能

**目标**：从自然语言中提取控制流IR，自动插入决策/循环节点

**修改文件**：
- `src/domain/agents/conversation_agent.py`

**新增方法**：
```python
def extract_control_flow(
    goal: str,
    context: dict
) -> ControlFlowIR:
    """
    识别决策点、循环需求，返回中间表示

    ControlFlowIR包含：
    - tasks: List[Task] - 任务列表
    - decision_points: List[DecisionPoint] - 决策点
    - loops: List[Loop] - 循环需求
    - dependencies: Dict[str, List[str]] - 依赖关系
    """

def build_control_nodes(ir: ControlFlowIR) -> Tuple[List[NodeDefinition], List[EdgeDefinition]]:
    """将IR转换为NodeDefinition + EdgeDefinition"""

# 修改现有方法
def create_workflow_plan(goal: str, context: dict):
    """后处理LLM输出，注入控制流节点"""
```

**测试用例**（tests/unit/domain/agents/test_conversation_agent_control_flow.py）：
- [ ] test_extract_control_flow_identifies_simple_condition
- [ ] test_extract_control_flow_identifies_loop
- [ ] test_extract_control_flow_identifies_combined_logic
- [ ] test_build_control_nodes_generates_condition_node
- [ ] test_build_control_nodes_generates_loop_node
- [ ] test_build_control_nodes_connects_edges_correctly

---

### Priority 4: WorkflowAgent 反馈驱动更新API

**目标**：支持运行时修改条件表达式、循环策略

**修改文件**：
- `src/domain/agents/workflow_agent.py`

**新增方法**：
```python
def update_edge_condition(
    edge_id: str,
    expression: str
) -> None:
    """修改边条件表达式"""

def update_loop_config(
    node_id: str,
    loop_type: str | None = None,
    collection_field: str | None = None,
    transform_expression: str | None = None,
    filter_condition: str | None = None
) -> None:
    """修改循环配置"""
```

**测试用例**（tests/unit/domain/agents/test_workflow_agent_feedback.py）：
- [ ] test_update_edge_condition_modifies_expression
- [ ] test_update_loop_config_modifies_loop_type
- [ ] test_updated_config_effective_in_next_execution

---

### Priority 5: 集成测试

**目标**：端到端验证从自然语言到工作流执行

**测试文件**：tests/integration/test_dynamic_workflow_e2e.py

**测试场景**：
- [ ] test_e2e_natural_language_to_condition_workflow
- [ ] test_e2e_loop_with_condition_filter
- [ ] test_e2e_feedback_adjustment_and_reexecution

---

## TDD 开发顺序

### Phase 1: Priority 1（统一配置）
1. 编写 test_node_definition_control_flow.py 中的4个测试
2. 实现 NodeRegistry schema 修改
3. 实现 NodeDefinition 验证逻辑
4. 实现 WorkflowAgent.evaluate_condition_node()
5. 运行测试确保通过

### Phase 2: Priority 2（表达式增强）
1. 编写 test_expression_evaluator_compiled.py 中的3个测试
2. 实现 compile_expression()
3. 实现 evaluate_compiled()
4. 实现 resolve_variables()
5. 运行测试确保通过

### Phase 3: Priority 3（智能规划 ⭐）
1. 编写 test_conversation_agent_control_flow.py 中的6个测试
2. 实现 extract_control_flow()
3. 实现 build_control_nodes()
4. 修改 create_workflow_plan()
5. 运行测试确保通过

### Phase 4: Priority 4（反馈更新）
1. 编写 test_workflow_agent_feedback.py 中的3个测试
2. 实现 update_edge_condition()
3. 实现 update_loop_config()
4. 运行测试确保通过

### Phase 5: Priority 5（集成测试）
1. 编写 test_dynamic_workflow_e2e.py 中的3个场景
2. 端到端验证所有功能
3. 修复发现的问题

---

## 进度跟踪

### 探索阶段
- [x] Codex深度分析现有架构
- [x] Codex提供实现方案建议
- [x] 创建开发计划文档

### 规划阶段
- [x] 完成测试策略设计
- [x] 完成实现方案设计

### TDD阶段
- [ ] Phase 1: 统一控制流配置与执行支持
- [ ] Phase 2: ExpressionEvaluator 增强
- [ ] Phase 3: ConversationAgent 控制流规划 ⭐
- [ ] Phase 4: WorkflowAgent 反馈驱动更新API
- [ ] Phase 5: 集成测试

### 实现阶段
- [ ] 循环实现直到所有测试通过

### 提交阶段
- [ ] Codex代码审查
- [ ] 根据反馈修改
- [ ] 创建PR
- [ ] 清理临时文件

---

## 风险评估

### 1. 控制流识别准确性
**风险**：LLM可能误判决策点或循环需求
**对策**：先实现基于规则的模板匹配（"如果"、"对每个"等关键词），LLM作为补充

### 2. 工作流复杂度控制
**风险**：自动生成的工作流可能过于复杂
**对策**：限制最大节点数（≤20）、嵌套深度（≤3），超限时提示用户简化需求

### 3. 反馈调整的稳定性
**风险**：动态修改可能导致不可预测行为
**对策**：版本化工作流定义，支持回滚到上一个稳定版本

### 4. 向后兼容性
**风险**：现有工作流可能受影响
**对策**：新功能通过feature flag控制，默认关闭

---

## 参考资料

**Codex分析结果**：
- Session ID: 019b05d8-641e-77c3-9495-508d2209a369
- 关键发现：NodeRegistry/WorkflowAgent配置不一致，CONDITION节点未真正执行

**相关文件**：
- ConversationAgent: src/domain/agents/conversation_agent.py:1459 (create_workflow_plan)
- WorkflowAgent: src/domain/agents/workflow_agent.py:1074 (execute_workflow_with_conditions)
- NodeDefinition: src/domain/agents/node_definition.py:44,611 (NodeType, from_yaml)
- NodeRegistry: src/domain/services/node_registry.py:451,460 (CONDITION/LOOP schemas)
- ExpressionEvaluator: src/domain/services/expression_evaluator.py:27

**现有测试**：
- tests/unit/domain/agents/test_workflow_conditional_execution.py
- tests/unit/domain/agents/test_workflow_collection_operations.py
- tests/unit/domain/services/test_expression_evaluator.py

---

**创建时间**：2025-12-10
**最后更新**：2025-12-10
**当前状态**：Priority 1 已完成 ✅，等待创建PR

---

## Priority 1 完成总结（2025-12-10）

### ✅ 已实现功能
1. **NodeRegistry LOOP schema 扩展** - 3个测试通过
   - 添加 collection_field, transform_expression, filter_condition 字段
   - 保持向后兼容（兼容 collection, condition 旧字段）

2. **NodeDefinition 验证增强** - 8个测试通过
   - 添加 `__post_init__` 方法（仅对 CONDITION/LOOP 强制验证）
   - CONDITION 节点：expression 必填
   - LOOP 节点：loop_type, collection_field 必填
   - map 类型：transform_expression 必填
   - filter 类型：filter_condition 必填

3. **WorkflowAgent.evaluate_condition_node()** - 5个测试通过
   - 评估条件节点表达式并返回布尔值
   - 多层上下文支持：节点输出、工作流变量、全局变量
   - 混合上下文策略：既扁平化又命名空间化（避免键冲突）

### 📊 测试结果
- **总测试数**：16/16 全部通过
- **测试文件**：tests/unit/domain/agents/test_node_definition_control_flow.py
- **代码覆盖**：新增代码 100% 覆盖

### 🔍 Codex审查与修复
**审查会话**：Session ID 019b05d8-641e-77c3-9495-508d2209a369

**发现的问题**：
1. **High**: __post_init__ 可能破坏向后兼容性
   - **修复**：仅对 CONDITION/LOOP 节点强制验证，其他节点保持兼容
2. **Medium**: 节点输出扁平化导致键冲突
   - **修复**：采用混合策略（既扁平化又命名空间化）

**代码质量评价**：
- ✅ 企业生产级别的代码质量
- ✅ 完整的文档字符串和注释
- ✅ 符合DDD架构规范
- ✅ Domain层无框架依赖
- ✅ 异常处理完善

### 📝 修改文件
1. `src/domain/services/node_registry.py` - LOOP schema 扩展
2. `src/domain/agents/node_definition.py` - 验证逻辑 + __post_init__
3. `src/domain/agents/workflow_agent.py` - evaluate_condition_node() 方法
4. `tests/unit/domain/agents/test_node_definition_control_flow.py` - 16个测试用例

### 下一步
- 创建 Priority 1 PR并提交
- （可选）继续 Priority 2-5 的开发，或在PR合并后再继续
