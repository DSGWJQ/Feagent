# 四层架构快速指南（Interface → Application → Domain → Infrastructure）

目的：用最短时间建立一致的心智模型，避免“写一点想一点”导致重复机制与边界坍塌。

本指南描述的是**当前主链路**与**强制约束**（以 2026-02-05 现状为基线）。如与旧文档冲突，以代码与 `docs/planning/*.md` 为准。

---

## 1. 四层职责（必须遵守）

### Interface（接口层）
- 位置：`src/interfaces/`
- 职责：协议适配（HTTP/SSE）、DTO、鉴权注入、错误映射（HTTPException）。
- 禁止：业务编排、落库、跨层调用 Domain 的具体实现细节。

### Application（应用层）
- 位置：`src/application/`
- 职责：用例编排、事务边界、门禁（coordinator/audit）、幂等、事件落库与回放入口。
- 特征：对外提供可测试的 UseCase/Service，组合 Domain 能力，避免 Interface “长函数”。

### Domain（领域层）
- 位置：`src/domain/`
- 职责：实体/值对象/领域服务/领域事件/端口（Ports）。这里是业务语义的事实源（SoT）。
- 禁止：依赖 FastAPI、SQLAlchemy、LangChain 等基础设施细节；不得引入“第二套语义实现”。

### Infrastructure（基础设施层）
- 位置：`src/infrastructure/`
- 职责：数据库、外部 API/LLM 适配器、工具执行器、文件/HTTP 等 I/O，实现 Domain Ports。
- 禁止：把业务规则写进基础设施；不得绕过 Application 的用例门禁直连 Domain 核心流程。

---

## 2. 当前主链路（你必须先理解的两条）

### 2.1 Conversation（澄清对话，SSE）
- 入口：`/api/conversation/stream`（`src/interfaces/api/routes/conversation_stream.py`）
- 流程：Interface → Application orchestrator → Domain `ConversationAgent` → SSE 输出（thinking/tool/result/final）
- 约束：默认入口只做澄清对话，不创建 workflow（前端路由契约也要求如此）。

### 2.2 Workflow Execution（执行，SSE + RunEvents）
- 入口：`/api/workflows/{workflow_id}/execute/stream`（`src/interfaces/api/routes/workflows.py`）
- 流程：Interface → Application `WorkflowRunExecutionEntry`（门禁/落库/验收环）→ 执行 kernel → Domain `WorkflowEngine`
- 事件契约：执行流只允许 `node_*` 与 `workflow_*`（见 `src/application/services/workflow_event_contract.py`）

---

## 3. 强制约束（用于“绝后患”）

1. **唯一实时通道：SSE（禁止 WebSocket 运行时链路）**
   如果需要实时推送：优先 SSE；客户端交互走 HTTP 请求。

2. **事件系统单轨：EventBus 为事实源（逐步清零 callback 语义）**
   不允许“只有某条路径注入了 callback 才有事件”，这是事件缺失的根因。

3. **单一权威实现**
   - workflow 执行语义：`WorkflowEngine` 为 SoT
   - workflow chat 更新：`UpdateWorkflowByChatUseCase` 为 SoT
   - Domain LLM 抽象：`LLMPort` 为 SoT

上述约束的具体落地与验收门禁见：`docs/planning/PROJECT_SIMPLIFICATION_DEDUP_PLAN.md`。
