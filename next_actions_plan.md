# 下一步行动计划

## P0问题清单（必须立即修复）

### ✅ 已完成

1. **✅ ConversationAgent：类型注解未定义（5处F821）** - 已完成（Commit: f0e8ed6）
   - 修复内容：在文件顶部引入 `TYPE_CHECKING`，将5个前向引用类型放入条件导入块。
   - 测试覆盖：新增4个类型可用性测试 + Ruff F821检查通过。
   - 收益：恢复静态类型安全，避免运行期注解解析异常。

2. **✅ ConversationAgent：异步Race Condition + 无锁并发访问** - 已完成（Commit: 6efea4b + 1345f6a）

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

   **Phase 2 待完成：**
   - ⏳ 添加 `pending_feedbacks` 访问的锁保护
   - ⏳ 添加 `session_context.update_token_usage()` 的锁保护
   - ⏳ 添加 `session_context.add_decision()` 的锁保护
   - ⏳ 高频路径性能优化（批量提交token更新）

3. **✅ ConversationAgent：浅拷贝导致上下文污染（2处dict.copy）** - 已完成（Commit: P0-3）
   - 修复内容：两处改为 `copy.deepcopy(context)`，新增挂起/恢复路径单测。
   - 收益：避免隐性跨轮次上下文串扰，提升对话一致性。

### ⏳ 进行中

4. **⏳ 全局：Ruff 58个代码质量错误** - Phase 1: P0子集修复中
   - 问题描述：Ruff统计58处错误（实际可能更多，需分层修复）。
   - 修复方案：
     1) 优先修复P0级别（可能导致运行问题）
     2) 分批修复P1级别（代码质量/可维护性）
     3) 最后修复P2级别（风格/约定）
   - 前置依赖：P0-1/2/3 已完成，可安全修复。
   - 收益：清除CI/静态检查阻断点，为后续大规模重构减少噪音。

## P0修复总结

**已完成：** P0-1 (类型注解) + P0-2 Phase 1 & Critical (竞态条件) + P0-3 (浅拷贝)
**Codex协作：**
- Phase 1提交后立即审查，发现2个Critical/Optimization问题
- Critical Fix响应审查意见，消除回调竞态+原子性空窗
- 评估：关键事件顺序问题已消除，共享状态竞态需Phase 2收口

**技术亮点：**
- 双锁策略避免死锁（state_lock + critical_event_lock 不嵌套）
- 事件路径分离（关键事件await+串行，通知事件后台追踪）
- 锁内原子转换（_transition_locked 消除空窗）

**测试覆盖：**
- Pyright: 0 errors
- P0回归测试: 14/14 passed
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
