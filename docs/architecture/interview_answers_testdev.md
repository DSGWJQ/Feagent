# 测试开发面试问题回答（基于真实项目实现）

> 范围说明：回答内容仅基于仓库内真实代码与测试文档；未引用线上指标或未落盘的数据。
> 证据路径会写在每个回答中，便于面试官现场追问时快速定位。

## Q1. 你如何制定该项目的测试金字塔？单测/集成/端到端分别覆盖哪些模块和场景？

**回答**
我按“目录与运行入口”划分测试金字塔：
1. **单元测试（最多）**：集中在 `tests/unit/`，覆盖 Domain 服务与核心规则（如安全校验、WorkflowSaveValidator、RuleEngineFacade）以及应用层用例的状态与边界行为。
2. **集成测试（中层）**：`tests/integration/`，覆盖多 Agent 协作链路、EventBus 中间件拦截、决策到执行的闭环、RunEvent 落库一致性。
3. **E2E（最少）**：Playwright UI 端到端测试，覆盖“创建工作流→执行→回放”的用户旅程，支持 deterministic/hybrid/fullreal 三种模式。
4. **回归/性能/手工**：`tests/regression/`、`tests/performance/`、`tests/manual/` 分别用于稳定性回归、性能阈值守护、真实环境联调。

**证据路径**
- 目录结构：`tests/`（含 `unit/`, `integration/`, `e2e/`, `regression/`, `performance/`, `manual/`, `real/`）
- E2E 执行指南：`docs/testing/E2E_TEST_IMPLEMENTATION_GUIDE.md`
- 性能基准：`tests/performance/test_performance_benchmarks.py`

## Q2. EventBus 的中间件拦截如何测试？如何验证“决策被拒绝”与“纠偏后继续执行”的闭环？

**回答**
我用“允许/拒绝中间件”驱动集成测试，验证在 **allow** 情况下执行与 RunEvent 落库，并在 **deny** 情况下确保 **无副作用**（fail-closed）。
具体流程：
1. 用 EventBus 中间件模拟 allow/deny。
2. 发布 DecisionMadeEvent。
3. allow 时进入执行链路并写入 RunEvent；deny 时不执行且不落库。
这能完整覆盖“决策→验证→执行”的闭环。

**证据路径**
- 允许/拒绝中间件与回放一致性：`tests/integration/api/workflows/test_validated_decision_run_events_replay_e2e.py`
- 决策到执行完整链路：`tests/integration/test_decision_to_execution_e2e.py`
- EventBus 本体：`src/domain/services/event_bus.py`

## Q3. WorkflowSaveValidator 的核心规则如何设计用例？如何构造边界数据？

**回答**
我按“结构合法性 + 能力可执行性 + 失败闭环”拆用例：
1. **结构合法**：无环 DAG、Start→End 主路径存在。
2. **能力可执行**：节点类型是否有执行器，工具节点是否存在/未废弃。
3. **fail-closed**：缺 executor 或 tool 时直接阻断，返回结构化错误码。
用例构造以 Node/Edge 直接组装最小 workflow，确保边界清晰可控。

**证据路径**
- 单测覆盖：`tests/unit/domain/services/test_workflow_save_validator.py`
- 规则实现：`src/domain/services/workflow_save_validator.py`

## Q4. Run 状态 CAS 更新如何做并发测试？如何验证没有状态回退？

**回答**
我在单元测试里用 `MagicMock` + `side_effect` 模拟并发竞争：
1. 第一次 CAS 成功，后续 CAS 返回 False。
2. 验证状态仅被推进一次（created→running），终态不会被覆盖回中间态。
3. 即使 CAS 失败，事件仍能追加（幂等设计）。
这种方式能稳定复现并发竞态而不依赖真实并发。

**证据路径**
- CAS 单测：`tests/unit/application/use_cases/test_append_run_event.py`
- 业务实现：`src/application/use_cases/append_run_event.py`

## Q5. SafetyGuard 的文件/API/人机交互校验如何隔离外部依赖做单测？

**回答**
全部用 **async 单元测试**，输入路径/URL/文案字符串，避免真实文件或网络访问。
覆盖点包括：
- 文件：非法操作、路径遍历、黑白名单、内容过大、缺少 content。
- API：URL scheme、域名黑白名单、SSRF（私有 IP/localhost）。
- 人机交互：提示注入关键词、长度限制、敏感内容检测。
这类测试不需要 IO，完全可重复。

**证据路径**
- SafetyGuard 单测：`tests/unit/domain/services/test_safety_guard.py`
- SafetyGuard 实现：`src/domain/services/safety_guard/core.py`

## Q6. 规则引擎 RuleEngineFacade 的规则优先级、fail-closed 行为怎么验证？

**回答**
我用 TDD 单测覆盖以下维度：
1. **优先级排序**：规则列表按 priority 变化验证。
2. **fail-closed**：规则执行异常视为验证失败，返回 errors。
3. **线程安全**：多线程并发验证统计一致性。
4. **Coordinator 集成**：确保协调者实际使用 Facade 进行验证。

**证据路径**
- Facade 单测（含 fail-closed/线程安全）：`tests/unit/domain/services/test_rule_engine_facade.py`
- 与 Coordinator 集成测试：`tests/unit/domain/agents/test_coordinator_agent.py`
- Facade 实现：`src/domain/services/rule_engine_facade.py`

## Q7. 上下文压缩触发条件如何稳定复现？如何测试冻结/解冻与回滚？

**回答**
通过设置 `context_limit` 和 `token_usage` 人为触发 `usage_ratio >= 0.92`，然后添加一轮对话触发事件。
集成测试验证：
1. 触发 ShortTermSaturatedEvent；
2. 事件仅触发一次；
3. 触发时通过流式 emitter 发送系统通知。
压缩过程的冻结/解冻和回滚由 MemoryCompressionHandler 管理（备份→冻结→压缩→回写→解冻）。

**证据路径**
- 饱和检测单测：`tests/unit/domain/services/test_short_term_saturation.py`
- 饱和事件集成测试：`tests/integration/test_saturation_flow_integration.py`
- 压缩处理器：`src/domain/services/memory_compression_handler.py`

## Q8. 如何处理测试中的时间/随机性（如 uuid、时间戳）以保证可重复？

**回答**
我主要用三种策略：
1. **mock/桩替换**：AsyncMock/MagicMock 替代 LLM、外部执行器等非确定性依赖。
2. **避免断言精确时间**：多数测试只断言“存在/非空”，不依赖精确时间戳。
3. **确定性运行模式**：E2E 使用 deterministic 模式，LLM/HTTP 走 stub/mock。
另外在 `conftest.py` 里确保同步测试始终有事件循环，避免事件循环状态导致的偶发失败。

**证据路径**
- LLM/执行器 mock：`tests/integration/test_decision_to_execution_e2e.py`
- 测试基线与 mock 外部 HTTP：`tests/conftest.py`
- E2E deterministic 模式说明：`docs/testing/E2E_TEST_IMPLEMENTATION_GUIDE.md`

## Q9. 是否有“可回放”的事件或日志，支持回归测试/复现线上问题？

**回答**
有两层“可回放”：
1. **EventBus 事件日志**：EventBus 内部维护 event_log，可用于回放事件序列。
2. **RunEvent 持久化**：执行过程中关键事件落库，可用于 replay 与一致性验证。
对应测试通过“allow/deny 决策”验证“执行事件可回放、一致性不破坏”。

**证据路径**
- EventBus 事件日志：`src/domain/services/event_bus.py`
- RunEvent 落库与 replay：`tests/integration/api/workflows/test_validated_decision_run_events_replay_e2e.py`
- RunEvent 落库一致性：`tests/integration/api/workflows/test_run_event_persistence.py`

## Q10. CI 中如何划分慢测试与快测试？如何避免偶发失败（flaky）？

**回答**
项目文档明确将 **deterministic** 作为 PR/日常验证入口，**fullreal** 放夜间（需外网和 API Key）。
flaky 管控以“repeat-each=10 的稳定性门禁”作为最低标准，并要求失败闭环记录。
因此我会把：
- 单元/集成测试作为 PR 快速反馈；
- deterministic E2E 作为 PR 门禁；
- fullreal E2E 与性能基准跑夜间或手动触发。

**证据路径**
- PR/nightly 入口与模式说明：`docs/testing/E2E_TEST_IMPLEMENTATION_GUIDE.md`
- flaky 失败闭环与稳定性门禁：`docs/testing/FAILURE_CLOSED_LOOP.md`

## Q11. 你如何定义“安全规则覆盖面”的测试标准？

**回答**
我用“类别 × 关键边界”的覆盖矩阵定义安全规则覆盖面：
- **文件**：黑白名单、路径遍历、内容大小、写操作必填 content；
- **API**：scheme 白名单、域名黑白名单、SSRF（私网/回环）；
- **人机交互**：提示注入关键词、长度限制、敏感内容检测；
再通过 WorkflowSaveValidator 做“结构与可执行性”兜底，确保保存即执行可行。

**证据路径**
- SafetyGuard 单测：`tests/unit/domain/services/test_safety_guard.py`
- WorkflowSaveValidator 单测：`tests/unit/domain/services/test_workflow_save_validator.py`

## Q12. 线上问题回溯时，测试如何与日志/指标联动定位？

**回答**
我把“可复现证据”绑定到测试与日志：
1. **E2E 失败闭环模板**：固定记录复现命令、trace、截图、风险评估与回归证据。
2. **RunEvent 落库**：执行链路事件可查询，用于回溯“哪里执行失败”。
3. **统一日志接口**：日志与事件结构化，有测试入口验证集成。
这些机制使问题能被测试用例复现并在文档中固化。

**证据路径**
- 失败闭环模板：`docs/testing/FAILURE_CLOSED_LOOP.md`
- RunEvent 落库与回放：`tests/integration/api/workflows/test_run_event_persistence.py`
- 日志集成手动测试：`tests/manual/test_unified_log_integration_e2e.py`
