# 项目精简与去冗余总规划（一次性收敛版）

**文档版本**: 1.0.0
**创建日期**: 2026-02-05
**最后更新**: 2026-02-06
**优先级**: P0（必须执行）
**目标**: 以“单一路径/单一契约/单一权威实现”为原则，一次性消除重复与双轨机制，避免后续继续“写一点想一点”导致的架构膨胀。

**执行状态（2026-02-06）**:
- Phase 0/1/2/3/4/6：已完成（证据：`python -m compileall -q src`、`pytest -q`、`cd web && pnpm test`）
- Phase 5：暂缓（仅当确有“Domain LLM 抽象统一”的收益与需求时再推进；避免不必要复杂度）

---

## 0. 已确认的架构决策（不可回退的红线）

1. **彻底放弃 WebSocket 运行时链路**
   统一使用 **HTTP + SSE**（服务端单向推流）作为唯一的实时通道。任何新的 WebSocket 入口视为架构违规。

2. **Workflow Chat 的唯一权威用例**
   `UpdateWorkflowByChatUseCase` 作为唯一权威（SoT），禁止同功能的第二套用例与“条件切换逻辑”。

3. **事件系统单轨**
   以 **EventBus** 为唯一事件主干，逐步清零 `event_callback`/callback 语义，SSE/落库/验收环均从同一事件流派生。

4. **工作流执行引擎单一权威**
   `WorkflowEngine`（`src/domain/services/workflow_engine.py`）为唯一执行语义来源；移除/下线任何替代实现（例如仅测试引用的 dependency-graph 执行体系、以及曾经的 LangGraph workflow executor 路径/feature flag）。

---

## 1. 背景与问题（冗余类型分类）

本次精简不是“删文件”，而是消除以下冗余源：

### 1.1 机制冗余（同一概念多套机制）
- **事件双轨**：EventBus 与 callback 并存（`WorkflowEngine.event_callback`、`ExecuteWorkflowUseCase.execute_streaming` 内重复事件队列逻辑）。
- **通道冗余**：SSE 已成为主链路，但仍保留 WebSocket（后端路由/画布同步/Agent 通信信道）。

### 1.2 语义冗余（同一业务多套实现）
- workflow chat 的两套 use case 并存，并在路由层做条件切换，导致行为与测试分裂。
- workflow 执行存在两套“拓扑与执行语义”（`WorkflowEngine` vs `workflow_dependency_graph`）。

### 1.3 认知冗余（文档/契约漂移）
- README 指向不存在的文档路径，导致新人/未来自己产生误判与错误入口。

### 1.4 产物冗余（运行产物误入仓库）
- `.coverage`、`htmlcov/`、`*_test.db`、`test_*.db`、`*_e2e.db`、`.pytest_cache/`、`.ruff_cache/`、`tmp/` 等常驻仓库（应删除并被 gitignore）。

---

## 2. 目标架构（最终态不可变约束）

### 2.1 通道与入口
- **唯一实时推送通道**：SSE（`/api/conversation/stream`、`/api/workflows/*/execute/stream`、`/api/workflows/chat-create/stream` 等）。
- **禁止运行时 WebSocket**：后端不得存在被挂载的 `@router.websocket`；前端不得实例化 `new WebSocket(...)`。

### 2.2 事件与审计
- **事件事实源**：EventBus（进程内）+ 事件持久化（RunEvents / 最小 event log）。
- **禁止 callback 事件语义**：任何事件不允许依赖“外部注入 callback 才能产生”，否则必然出现缺失事件与不可回放问题。

### 2.3 单一权威执行语义
- **执行语义 SoT**：`WorkflowEngine`。任何新增执行语义必须在其内部演进（而不是新建第二套引擎）。

### 2.4 单一 LLM 抽象
- **Domain 层唯一 LLM Port**：`src/domain/ports/llm_port.py:LLMPort`。
  Domain 内不得出现新的 LLM Protocol/Client 定义；基础设施适配器可自由实现该 Port。

---

## 3. 分阶段实施计划（每阶段必须审查与门禁）

说明：
- 每个阶段都必须满足“严格验收标准”后才能进入下一阶段。
- 不允许“先做完再统一修复测试”；测试与门禁是阶段交付的一部分。

### Phase 0：仓库卫生与文档契约修复（先清理，再动刀）

#### 目标
消除运行产物冗余与文档漂移，建立后续重构的稳定基线。

#### 工作项
1. 删除仓库内运行产物（若被 git 追踪则需 `git rm --cached` 后再删本地文件）：
   - `.coverage`
   - `htmlcov/`
   - `*_test.db`、`test_*.db`、`*_e2e.db`
   - `.pytest_cache/`、`.ruff_cache/`
   - `tmp/`
2. 更新 `.gitignore`：确保上述产物不会再次进入仓库。
3. 修复 README 文档指针漂移（二选一，推荐方案 A）：
   - 方案 A（兼容性优先）：补齐缺失的 `docs/README.md`、`docs/ARCHITECTURE_GUIDE.md`、`docs/DEVELOPMENT_GUIDE.md` 为“索引/转发文档”，并保持 README 链接稳定。
   - 方案 B（最少文件）：直接修改 `README.md` 指向现有文档（并确保文档索引完整）。

#### 严格验收标准（全部满足）
- `git status --porcelain` 无运行产物残留。
- `.gitignore` 覆盖所有产物类型；且 `git check-ignore -v <path>` 可验证生效。
- README 中所有 `docs/*.md` 链接均存在（文件真实存在）。
- 后端：`python -m compileall src` 通过。
- 测试基线：`pytest -q` 至少 unit+integration 全绿（若当前本就有红灯，必须先记录并冻结为“已知失败清单”，禁止在 Phase 0 之后才承认）。

#### 阶段审查清单
- 是否引入任何新功能？（禁止）
- 是否只做 hygiene + 文档契约？（必须）
- 是否有任何运行产物仍被跟踪？（禁止）

---

### Phase 1：彻底移除 WebSocket 运行时链路（删掉第二套通道）

#### 目标
删除 WebSocket 相关后端/领域通信链路与配套测试，确保运行时入口只有 SSE。

#### 工作项
1. 后端路由与服务删除/下线：
   - `src/interfaces/api/routes/agent_websocket.py`
   - `src/infrastructure/websocket/canvas_sync.py`
   - 相关 `__init__.py` 与依赖模块（例如 `src/domain/agents/agent_channel.py`）按引用关系清理。
2. 删除/重写相关测试：
   - `tests/**/test_agent_websocket_*`
   - `tests/**/test_websocket_canvas_sync_*`
   - `tests/**/test_agent_channel_*`
3. 前端门禁保持并加固：
   - 保留并强化 “不实例化 WebSocket” 的测试（已有 `WorkflowEditorNoWebSocket`）。

#### 严格验收标准（全部满足）
- 后端源码中 `@router.websocket` 为 **0**：`rg -n \"@router\\.websocket\" src/interfaces` 无匹配。
- 后端运行入口（FastAPI include_router）不再引用任何 WebSocket 路由。
- 前端：`rg -n \"new WebSocket\\(\" web/src` 为 **0**。
- `pytest -q` 全绿；`web` 侧 `pnpm test`（或最小 vitest 子集）全绿。

#### 阶段审查清单（红队）
- 是否存在“删了路由但保留了领域通信信道”导致新同学误用？（禁止，必须同步删除或隔离到 experiments）
- 是否存在文档仍宣称 `ws://...`？（必须修复）

---

### Phase 2：移除 workflow_dependency_graph（测试引擎冗余清理）

#### 目标
只保留 `WorkflowEngine` 作为执行语义 SoT；删除 dependency-graph 引擎与其测试依赖。

#### 工作项
1. 删除 `src/domain/services/workflow_dependency_graph.py`。
2. 将相关测试迁移为 `WorkflowEngine`/`topological_sort_ids` 的测试（保证覆盖“拓扑排序+条件边+跳过语义”的核心行为）。

#### 严格验收标准（全部满足）
- `rg -n \"workflow_dependency_graph\" src tests` 为 **0**。
- 对应能力在 `WorkflowEngine` 测试中有等价覆盖（覆盖率以关键路径为准，不以行数为准）。
- `pytest -q` 全绿。

#### 阶段审查清单
- 是否出现“删掉依赖图引擎后，仍有第二套拓扑语义存在”？（禁止）

---

### Phase 3：workflow chat 用例单轨化（唯一权威 UseCase）

#### 目标
统一 `/chat`、`/chat-stream`、`/chat-create/stream` 相关路径，消除两套用例并存与条件切换。

#### 工作项
1. 保留 `UpdateWorkflowByChatUseCase` 为唯一权威；移除 `EnhancedChatWorkflowUseCase` 及其依赖注入。
2. 删除路由层“依据 dependency override 切换用例”的逻辑，保持行为稳定可预测。
3. 对“chat-history/search/clear”功能进行归位：
   - 若属于业务必需，则收敛到同一 UseCase/Service 的明确 API；
   - 若属于实验性能力，迁移到 `experiments/` 或直接删除（需明确边界）。

#### 严格验收标准（全部满足）
- `src/application/use_cases/enhanced_chat_workflow.py` 不再存在或不再被引用（以 `rg` 为准）。
- 路由层不存在“同一 endpoint 两套实现切换”。
- 所有 chat 相关 e2e/integration 测试通过（至少覆盖：创建、修改、streaming、权限门禁/Coordinator 拒绝路径）。

#### 阶段审查清单（红队）
- coordinator 审计/门禁是否在所有 chat 修改路径生效？（必须 fail-closed）
- streaming 的事件类型是否混入 execution stream？（必须遵守 `workflow_event_contract`）

---

### Phase 4：事件系统单轨化（清零 callback 语义）

#### 目标
将“节点执行事件/工作流执行事件”的产生，从 callback 迁移到 EventBus 单一路径，彻底解决“事件缺失/不可回放/测试不稳定”。

#### 推荐实施策略（KISS，优先可落地）
1. 定义并启用统一的 Domain 事件（已存在但脱节）：
   - `src/domain/events/workflow_execution_events.py` 的 `NodeExecutionEvent`（`status=running/completed/failed/skipped`）必须进入主链路。
2. 执行器发布事件（模板方法/基类包装）：
   - 让节点执行器在执行前后发布事件，而不是依赖 `WorkflowEngine.event_callback`。
3. SSE/落库订阅同一事件流：
   - `WorkflowRunExecutionEntry` 负责落库与验收环（acceptance loop）触发；
   - SSE 只负责“把事件序列化并推送”，不得再生成第二套事件语义。
4. 清零 `event_callback`：
   - 逐步删除 `WorkflowEngine.event_callback` 参数与 `ExecuteWorkflowUseCase.execute_streaming` 内的事件队列逻辑。

#### 严格验收标准（全部满足）
- `rg -n \"event_callback\" src` 为 **0**（或仅允许出现在明确标记的兼容层，且必须在本阶段结束时清零）。
- `NodeExecution*Event` 在真实执行路径中可观测（RunEvents execution channel 中完整出现 node_start/node_complete/node_error 对应事件）。
- 关键事件同步落库策略不回退（confirm/terminal 事件必须可被 acceptance loop 立即读取）。
- `pytest -q` 全绿；关键 e2e（UX-WF-007/008）恢复验证并通过（参考 `docs/planning/EVENT_SYSTEM_FIX_PLAN.md` 的验收口径）。

#### 阶段审查清单（红队）
- 是否仍存在“只有 streaming 才有事件”的路径？（禁止）
- 是否存在“事件由 UI/LLM 文本重放”冒充真实执行？（禁止）

---

### Phase 5：LLM 协议统一（删掉重复 Protocol）

#### 目标
Domain 层统一只依赖 `LLMPort`，消除多处重复的 `LLMClientProtocol`/自定义 client 口径。

#### 工作项
1. 逐文件替换 Domain 层重复协议定义，统一引用 `src/domain/ports/llm_port.py:LLMPort`。
2. 基础设施层提供适配器（OpenAI/Anthropic/LangChain），保持 Domain 不感知具体实现。
3. 增加门禁脚本（可选但推荐）：检查 Domain 层是否出现新的 LLM Protocol 定义。

#### 严格验收标准（全部满足）
- `rg -n \"class LLMClientProtocol|Protocol\\):\\s*$\" src/domain` 无新增重复协议（保留 `LLMPort` 作为唯一例外）。
- `pytest -q` 全绿。

---

### Phase 6：防复发门禁（CI/Pre-commit/脚本）

#### 目标
把“绝后患”固化为自动化门禁：以后任何人（包括未来的你）只要试图再引入第二套机制，就会被 CI 拦截。

#### 工作项（推荐）
1. 增加脚本门禁（示例）：
   - 禁止 WebSocket 运行时：扫描 `@router.websocket`、`new WebSocket(`。
   - 禁止 callback：扫描 `event_callback`。
   - 禁止旧用例回流：扫描 `EnhancedChatWorkflowUseCase` 等标记符号。
   - 禁止 workflow 执行内核双轨回流：扫描 `langgraph_workflow_executor`（仅限 workflow 语义，不影响 task executor）。
2. 将脚本挂入 pre-commit 或 CI（若有）。

#### 严格验收标准（全部满足）
- 所有门禁脚本可在本地一键运行且稳定通过。
- 新增/修改代码触发违规时能稳定失败并给出可理解的错误信息。

---

## 4. 总体验收（最终 DoD）

满足以下全部条件，视为“精简完成且不再复发”：
1. 运行时入口：SSE 为唯一实时通道；无 WebSocket 路由挂载；前端无 `new WebSocket(`。
2. 事件：EventBus 单轨；`event_callback` 清零；节点级事件完整可观测且可回放（落库）。
3. workflow chat：单一权威 use case；无条件切换；行为一致可预测。
4. workflow execution：`WorkflowEngine` 为唯一执行语义；dependency-graph 引擎完全移除。
   - 以及 LangGraph workflow executor 路径完全移除（避免第二套执行语义）。
5. Domain LLM 抽象：仅 `LLMPort`；无重复协议定义。
6. 仓库卫生：运行产物不入库；README/文档索引无漂移；所有测试与门禁全绿。

---

## 5. 风险与回滚策略（红队视角）

### 5.1 主要风险
- “删 WebSocket 链路”可能删除了某些仍在用但未挂载的实验入口（当前以主链路为准，实验入口必须显式迁移到 experiments 或删除）。
- “清零 callback”是架构级变更，必须分阶段替换事件生产源，确保 SSE/落库/验收环不掉事件。

### 5.2 回滚策略
- 以 git 为回滚事实源：每个 Phase 单独提交，必要时可按 Phase 回退。
- 在 Phase 4 前必须保持可观测性：任何阶段不得降低对关键事件（confirm/terminal）的同步落库能力。
