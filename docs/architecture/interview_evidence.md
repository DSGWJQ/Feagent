# 面试亮点证据化说明（基于当前代码）

> 目的：把简历亮点与真实代码路径对齐，方便面试追问时可直接定位实现。
> 原则：只写“代码里确实存在的能力”，对缺少数据支撑的指标标注待补证。

## 1. DDD 四层架构与聚合根

- 四层结构：`src/domain`（领域）、`src/application`（用例/编排）、`src/infrastructure`（持久化/外部适配）、`src/interfaces`（API/交互）。
- Workflow 聚合根（领域层纯 Python）：
  - 工厂方法 `Workflow.create()` 统一创建逻辑与不变式校验（节点/边一致性）。
  - 领域层声明不依赖框架，使用 dataclass。
- Run 聚合根（可追踪执行实例）：
  - 工厂方法 `Run.create()` / `Run.create_with_idempotency()`，封装状态与幂等规则。
  - 状态流转约束与终态判断集中在实体方法内。

## 2. 多智能体协作闭环（Conversation / Coordinator / Workflow）

- ConversationAgent：负责意图理解、目标分解与“决策”生成。
- CoordinatorAgent：作为 EventBus 中间件，对决策进行规则校验与纠偏。
- WorkflowAgent：执行工作流 DAG、节点调度、结果回传。
- EventBus：发布/订阅 + 中间件链，解耦三者通信，形成“决策→验证→执行”的闭环。

## 3. 安全与规则引擎（RuleEngineFacade + SafetyGuard + SaveValidator）

- RuleEngineFacade 统一封装：规则管理、校验、审计、熔断、告警。
- SafetyGuard 提供多维安全校验：
  - 文件操作：路径遍历、黑白名单、内容大小、敏感信息检测。
  - API 请求：URL scheme、域名白名单/黑名单、SSRF（私有 IP/本地地址）。
  - 人机交互：提示注入关键词、长度限制、敏感内容检测。
- WorkflowSaveValidator 保障“保存即能执行”：
  - DAG 无环、Start-End 主路径完整、节点执行器/工具存在、节点配置合法。

> 备注：代码内有统计与告警钩子，但“>99.5%安全性”“20+验证器”等量化指标未见直接数据来源，建议面试时以“多维校验/规则覆盖面”表述，并补充测试或线上统计。

## 4. 高并发与强一致性

- 线程级：RuleEngineFacade 使用 `threading.RLock` 保护规则与统计。
- 异步级：多个模块使用 `asyncio.Lock`（会话状态、工具执行等）保护并发访问。
- 数据库级（CAS）：Run 状态更新采用“update_if_current”模式避免 TOCTOU。
- 会话冻结/解冻：上下文压缩时冻结 Session，确保压缩过程一致性。

## 5. 上下文管理与压缩流水线

- 四层上下文：Global → Session → Workflow → Node（隔离/继承/生命周期清晰）。
- Token 饱和检测：SessionContext 维护 usage_ratio，达到阈值触发 ShortTermSaturatedEvent。
- 自动压缩：MemoryCompressionHandler 订阅饱和事件，完成“备份→冻结→压缩→回写→解冻→恢复饱和标记”。

## 6. 证据映射（主路径）

| 亮点 | 代码证据路径（示例） | 说明 |
| --- | --- | --- |
| Workflow 聚合根 | `src/domain/entities/workflow.py` | 工厂方法 + 不变式校验 |
| Run 聚合根 | `src/domain/entities/run.py` | 状态流转、幂等创建 |
| EventBus 解耦 | `src/domain/services/event_bus.py` | 发布/订阅/中间件 |
| Conversation/Workflow/Coordinator | `src/domain/agents/*_agent.py` | 三角色职责与闭环 |
| RuleEngineFacade | `src/domain/services/rule_engine_facade.py` | 规则与统计入口 |
| SafetyGuard | `src/domain/services/safety_guard/core.py` | 文件/API/交互校验 |
| WorkflowSaveValidator | `src/domain/services/workflow_save_validator.py` | DAG/配置/执行校验 |
| CAS 并发控制 | `src/application/use_cases/append_run_event.py` | 状态 CAS 更新 |
| 上下文层级 | `src/domain/services/context_manager.py` | Global/Session/Workflow/Node |
| Token 饱和/压缩 | `src/domain/entities/session_context.py` + `src/domain/services/memory_compression_handler.py` | 饱和事件+压缩流水线 |

## 7. 面试口径建议（量化指标补证）

如果面试官追问“99.5%安全性/300%轮次提升/20+验证器”，建议准备以下证据：
1. 自动化测试或压测报告（通过率、失败原因分布）。
2. 线上/日志指标（拒绝率、回滚率、压缩前后 token 变化）。
3. 规则/校验清单（把“校验点”列表化并可复现）。

> 没有数据就不要硬报百分比，可改为“多维校验+自动压缩+可观测指标”并说明如何统计。

## 8. 测试开发岗位面试问题清单（围绕本项目）

1. 你如何制定该项目的测试金字塔？单测/集成/端到端分别覆盖哪些模块和场景？
2. EventBus 的中间件拦截如何测试？如何验证“决策被拒绝”与“纠偏后继续执行”的闭环？
3. WorkflowSaveValidator 的核心规则（无环、主路径、工具可用）如何设计用例？如何构造边界数据？
4. Run 状态 CAS 更新如何做并发测试？如何验证没有状态回退？
5. SafetyGuard 的文件/API/人机交互校验如何隔离外部依赖做单测？
6. 规则引擎 RuleEngineFacade 的规则优先级、fail-closed 行为怎么验证？
7. 上下文压缩触发条件（token 饱和）如何稳定复现？如何测试冻结/解冻与回滚？
8. 如何处理测试中的时间/随机性（如 uuid、时间戳）以保证可重复？
9. 是否有“可回放”的事件或日志，支持回归测试/复现线上问题？
10. CI 中如何划分慢测试与快测试？对于高并发/异步场景如何避免偶发失败（flaky）？
11. 你如何定义“安全规则覆盖面”的测试标准（仅逻辑覆盖还是场景覆盖）？
12. 线上问题回溯时，测试如何与日志/指标联动定位（例如拒绝率、失败原因分布）？

## 9. 项目对测试开发的支持点（证据路径）

- 分层结构清晰，天然利于分层测试（Domain / Application / Infrastructure / Interfaces）。
- 领域层纯 Python + 工厂方法，便于单测（无需框架/数据库依赖）：
  - `src/domain/entities/workflow.py`
  - `src/domain/entities/run.py`
- 规则与校验集中在可单测的服务：
  - `src/domain/services/workflow_save_validator.py`
  - `src/domain/services/rule_engine_facade.py`
  - `src/domain/services/safety_guard/`
- 事件驱动解耦，方便通过 EventBus 回放和中间件拦截测试：
  - `src/domain/services/event_bus.py`
  - `src/domain/services/decision_events.py`
- 并发一致性具备明确的可测“状态更新点”：
  - `src/application/use_cases/append_run_event.py`
- 上下文压缩与冻结/解冻是独立模块，适合黑盒/白盒测试：
  - `src/domain/entities/session_context.py`
  - `src/domain/services/memory_compression_handler.py`
- 项目内已有测试规划与报告目录，可作为测试开发基线材料：
  - `docs/testing/`
  - `tests/`

> 建议面试时：把“测试策略”和“模块证据路径”绑定回答，突出可测性设计与可复现性。
