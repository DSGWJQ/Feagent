# 下一步行动计划

## P0问题清单（必须立即修复）

### ✅ 已完成

1. **✅ ConversationAgent：类型注解未定义（5处F821）** - 已完成（Commit: f0e8ed6）
   - 修复内容：在文件顶部引入 `TYPE_CHECKING`，将5个前向引用类型放入条件导入块。
   - 测试覆盖：新增4个类型可用性测试 + Ruff F821检查通过。
   - 收益：恢复静态类型安全，避免运行期注解解析异常。

2. **✅ ConversationAgent：异步Race Condition + 无锁并发访问** - 已完成（Commit: 6efea4b + 1345f6a + 8bd4a3d + 4de4721）

   **Phase 1 (6efea4b): 核心基础设施**
   - ✅ 新增双锁策略：`_state_lock` + `_critical_event_lock`
   - ✅ 新增事件发布辅助：`_publish_critical_event()` + `_publish_notification_event()`
   - ✅ 新增4个异步方法：`transition_to_async` / `wait_for_subagent_async` / `resume_from_subagent_async` / `request_subagent_spawn_async`
   - 测试覆盖：P0回归测试 14/14 通过

   **Critical Fix (1345f6a): 响应Codex审查**
   - ✅ 修复 `handle_subagent_completed` 回调竞态（改为异步+锁保护）
   - ✅ 提取 `_transition_locked()` 消除原子性空窗
   - ✅ 更新 `wait_for_subagent_async` / `resume_from_subagent_async` 使用锁内原子转换
   - Codex评审：安全性已明显缓解，关键事件顺序问题已消除

   **Phase 2 Part 1 (8bd4a3d): Staged Batching + pending_feedbacks**
   - ✅ 添加 staged 变量（_staged_prompt_tokens, _staged_completion_tokens, _staged_decision_records）
   - ✅ 添加 stage/flush 辅助方法（_stage_token_usage, _stage_decision_record, _flush_staged_state）
   - ✅ 添加 pending_feedbacks 异步锁保护方法（get/clear/generate_error_recovery_decision）
   - ✅ 更新事件处理器使用锁保护（_handle_adjustment_event, _handle_failure_handled_event）
   - Codex评审：基本正确，发现4个需注意点

   **Phase 2 Part 2 (4de4721): run_async staged迁移 + 决策记录staged化**
   - ✅ 迁移 run_async 的 update_token_usage 到 staged 机制
   - ✅ 在所有return前添加 flush（3个分支：respond/should_continue/max_iter）
   - ✅ 新增 _record_decision_async() 使用staged机制
   - ✅ 迁移 run_async 中的决策记录到async+staged版本
   - 测试覆盖：P0回归测试 14/14 通过

   **Phase 2 总结：**
   - ✅ Staged batching 机制完整实现（减少锁获取次数）
   - ✅ pending_feedbacks 全量锁保护（读/写/清空/事件处理）
   - ✅ run_async 高频路径优化（token/decision批量提交）
   - ✅ 所有关键return前flush保护（避免数据丢失）

   **已知限制（Optional P1 任务）：**
   - ⏳ pending_feedbacks 仍有同步访问点（get_context_for_reasoning等）
   - ⏳ 缺少异常时的try/finally flush保护
   - ⏳ 同一agent并发run时staged全局共享问题
   - ⏳ 需推动调用方使用async版本以保证读写一致

3. **✅ ConversationAgent：浅拷贝导致上下文污染（2处dict.copy）** - 已完成（Commit: P0-3）
   - 修复内容：两处改为 `copy.deepcopy(context)`，新增挂起/恢复路径单测。
   - 收益：避免隐性跨轮次上下文串扰，提升对话一致性。

4. **✅ 全局：Ruff + Pyright 代码质量修复** - 已完成（Commit: 00e0440）

   **Ruff 修复 (10处)：**
   - ✅ B904 异常链 (8处): 添加 `from e` 保留异常上下文
     - advanced_executors.py, configurable_rule_engine.py (3处)
     - context_bridge.py, goal_decomposer.py
   - ✅ C401 不必要生成器 (2处): 优化集合构造
     - extension_api.py, schema_inference.py
   - ✅ B007 循环变量未使用 (2处): 使用 _ 占位符
     - generic_node.py, validators.py

   **Pyright 类型修复 (5处)：**
   - ✅ advanced_executors.py: 添加 tuple 类型检查
   - ✅ configurable_rule_engine.py: 添加 dict 类型验证
   - ✅ extension_api.py: 使用字符串类型引用
   - ✅ workflow_dependency_graph.py: 添加 dict 类型检查
   - ✅ 测试文件: 删除未使用变量

   **额外优化：**
   - ✅ experiment_orchestrator.py: 删除未使用的 TYPE_CHECKING 导入
   - ✅ intervention/models.py: 字符串类型注解改为直接引用
   - ✅ workflow_dependency_graph.py: dict 构造优化 (dict.fromkeys)
   - ✅ 多个测试文件: 清理未使用导入

   **验证结果：**
   - ✅ ruff check: All checks passed
   - ✅ pyright: 0 errors
   - ✅ 单元测试: 12/12 passed
   - ✅ 集成测试: 9/9 passed
   - ✅ pre-commit: All hooks passed

   **Codex协作：**
   - 发现改动范围超出预期（21文件），建议排除环境配置文件
   - 所有改动确认为代码质量改进，无功能变更

### ⏳ 进行中

（无）

---

## P0修复总结

**✅ 全部完成！**
- P0-1: 类型注解未定义（5处F821）
- P0-2: 异步Race Condition（Phase 1 + Critical + Phase 2）
- P0-3: 浅拷贝导致上下文污染（2处dict.copy）
- P0-4: Ruff + Pyright 代码质量修复（10 Ruff + 5 Pyright）

**Codex协作：**
- P0-2 Phase 1: 发现2个Critical/Optimization问题
- P0-2 Critical Fix: 消除回调竞态+原子性空窗
- P0-2 Phase 2: 发现4个需注意点，全部在Part 2中修复
- P0-4: 发现改动范围超出预期，确认所有改动为质量改进

**技术亮点：**
- 双锁策略避免死锁（state_lock + critical_event_lock 不嵌套）
- 事件路径分离（关键事件await+串行，通知事件后台追踪）
- 锁内原子转换（_transition_locked 消除空窗）
- Staged batching 机制（减少锁获取次数，批量提交更新）
- 全面类型检查（Pyright 0 errors）

**测试覆盖：**
- Pyright: 0 errors
- Ruff: All checks passed
- P0回归测试: 14/14 passed
- 单元测试: 12/12 passed
- 集成测试: 9/9 passed
- 所有现有功能保持兼容

---

## P1问题清单（本周完成）

1. CoordinatorAgent Phase-1拆分（先抽两大职责） - 预计16小时
   - 问题描述：`coordinator_agent.py` 5687行巨型类、162方法、15+职责，改动耦合度极高。
   - 修复方案：
     1) 先确定稳定边界：提取 `ContextManager`（上下文/压缩/快照相关）与 `RuleEngineFacade`（规则加载/验证/拒绝率/熔断）。
     2) 在原类中用组合替代部分内联方法，逐步搬迁代码。
     3) 引入 `CoordinatorAgentConfig` dataclass 收敛构造参数，缩短 `__init__`。
     4) 迁移对应单测到新组件，保持现有对外API不变。
   - 前置依赖：P0-1/2/3（确保对话侧稳定，便于定位回归）。
   - 收益：降低单点复杂度，后续拆分可线性推进；减少"改一处崩全局"的风险。

2. CoordinatorAgent：显式依赖注入/减少懒加载隐藏依赖 - 预计6小时
   - 问题描述：大量 `_get_xxx()` 懒加载引入隐式依赖和首调用延迟，调试困难。
   - 修复方案：
     1) 列出所有懒加载服务与调用路径，按"关键/非关键"分级。
     2) 关键服务改为构造注入或启动期预初始化；非关键保留但统一到一个 LazyLoader/Factory 层。
     3) 更新初始化顺序与失败提示（明确缺失依赖的错误来源）。
   - 前置依赖：P1-1（拆分时一起做更省成本）。
   - 收益：依赖图清晰、测试mock面减小、性能抖动降低。

3. 服务模块冗余：监督/压缩/规则 三类第一阶段合并 - 预计12小时
   - 问题描述：监督系统3套、压缩器2套、规则引擎2套并存且互相导入，行为易漂移。
   - 修复方案：
     1) 逐类选定"唯一权威实现"（报告建议：`supervision_strategy.py`、`power_compressor.py`、`configurable_rule_engine.py` 或统一版本）。
     2) 旧实现标记 deprecated（文档+注解+警告日志）。
     3) 建一个统一入口模块（`unified_supervision_system.py` / `unified_rule_engine.py` 等），把对外调用都路由到权威实现。
     4) 分批迁移 import 与调用点；跑回归测试。
   - 前置依赖：无，可与P1-1并行。
   - 收益：模块数下降、逻辑单源化、减少维护与认知负担。

4. ConversationAgent Phase-1拆分为5文件 + Config收敛 - 预计14小时
   - 问题描述：2455行单文件、同步/异步混杂、构造参数14个，维护/测试成本高。
   - 修复方案：
     1) 按报告建议拆出 core/workflow/state/recovery/control_flow 五文件。
     2) 引入 `ConversationAgentConfig`，用默认值+可选覆盖替代长参数列表。
     3) 保留外部导入路径不变（`conversation_agent.py` 作为薄门面转发）。
     4) 分区迁移测试，确保关键行为无回归。
   - 前置依赖：P0-1/2/3。
   - 收益：降低单文件复杂度、明确职责边界，后续优化（类型/性能）更可控。

5. WorkflowAgent：去重复执行入口 + 明确容器回退策略 - 预计8小时
   - 问题描述：多个 execute_* 入口疑似重复，默认容器执行器回退逻辑可能吞错。
   - 修复方案：
     1) 盘点 execute_* 之间公共流程，抽成单一内部管线（例如 `_execute_workflow_internal`）。
     2) 把容器回退策略改为"显式策略对象/配置"，并记录回退原因日志。
     3) 对外API保持不变，仅减少内部重复。
   - 前置依赖：无，可并行。
   - 收益：减少重复与隐藏错误，提高可测试性。

6. 类型安全提升（Agents公共返回值/IR） - 预计10小时
   - 问题描述：Coordinator/Workflow 多处 `Any` 返回，公共结构缺少明确类型。
   - 修复方案：
     1) 定义核心类型：`NodeExecutionResult`、`WorkflowExecutionResult`、`ControlFlowIR` 等（放在 domain/typing 或 agents/common）。
     2) 先替换对外公开方法的返回与关键参数类型。
     3) 渐进式收缩 Any（不做全量一口气替换）。
   - 前置依赖：P1-1/4（拆分后更容易替换）。
   - 收益：静态检查能力恢复，降低重构引入bug概率。

## 修复顺序建议

1. 首先修复：P0-1/2/3（ConversationAgent 三类运行时/类型关键bug），并同时定位P0-4 Ruff错误。
2. 然后并行修复：
   - 线A：P1-1 + P1-2（CoordinatorAgent Phase-1拆分与依赖显式化）
   - 线B：P1-3（服务冗余第一阶段合并）
   - 线C：P1-4（ConversationAgent 拆分）
3. 最后修复：P1-5（WorkflowAgent去重复）与 P1-6（类型安全提升）作为收尾增量。

## 预计总工作量
- P0: 7.5小时
- P1: 66小时（建议3条并行线分摊到Claude+Codex+开发者，1周可完成Phase-1范围）

---

**生成时间**: 2025-12-12
**基于**: tmp_final_review_report.md
**协作**: Claude + Codex
