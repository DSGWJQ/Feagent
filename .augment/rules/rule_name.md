---
type: "manual"
---

## 项目规则（核心要求，防偏航）

### 1. 定位与范围
- 定位：企业内部 Agent 中台系统（对外宣传“高可用/稳定”，内部渐进式实现）。
- 目标：用户输入“起点 start + 目的 goal”即可创建 Agent；创建后可调整配置；以结果为导向。
- 非目标：默认不采用“对话式构造工作流”；不引入多 Agent 协作；MVP 不做复杂 DAG/可视化编排。

### 2. 技术栈锁定（遵循 develop_document.md 与 需求分析.md）
- 后端：Python 3.11+；FastAPI + Pydantic v2；SQLAlchemy 2.0；PostgreSQL（生产）/SQLite（开发）；Alembic。
- HTTP 客户端：httpx（异步可选 aiohttp）。
- 执行器：轻量执行器（asyncio + 队列/APScheduler）；Prefect 可选替换，不是默认依赖。
- 日志/稳定性：structlog JSON + trace_id；tenacity 重试/超时；限流；健康检查。
- 依赖与质量：uv ；Ruff/Black、Pyright、pytest、pre-commit。
- 前端：Vite + React + TypeScript；Ant Design；TanStack Query；SSE（EventSource）优先，WebSocket 可选。
- **开发模式**：**强制采用 TDD（测试驱动开发）**
  - 流程：先编写测试用例 → 实现功能 → 通过测试验证需求覆盖
  - TDD + DDD 互补：DDD 定义"设计什么"，TDD 定义"如何开发"
  - Domain 层纯逻辑易测试；Application 层通过 Ports 易 Mock

### 3. 架构与分层（DDD‑lite + 六边形 + 单体）
- 依赖方向：API/Infra → Application → Domain（Domain 不依赖任何框架）。
- Assembler：DTO(Pydantic) ⇄ Domain 显式转换；DTO 不进入 Domain。
- 事务边界：仅在 Application 层开启/提交/回滚；Domain 禁止感知事务。
- 命名语义：get_/find_/exists_/check_ 含义必须遵循规范文档。

### 4. 核心域模型与状态
- 聚合/实体：Agent、AgentConfig、Goal、Run、Task、TaskEvent（事件表，追加写）。
- 状态机（Run/Task）：PENDING → RUNNING → SUCCEEDED | FAILED | CANCELLED。

### 5. API 契约（强制）
- 统一错误结构：{code, message, detail?, trace_id}；DomainError→4xx，InfraError→5xx。
- 路由：
  - POST /agents（start+goal 创建 Agent）
  - PATCH /agents/{id}（部分更新 config）
  - POST /agents/{id}/runs（触发运行；返回 run_id, status）
  - GET  /agents/{id}/runs/{run_id}（查询运行状态）
  - GET  /agents/{id}/runs/{run_id}/stream（SSE 默认流式）
- 错误码基线：2000 OK；4001 参数错误；4004 不存在；4090 幂等冲突；5000 系统错误；5001 依赖异常。
- 幂等等价键：agent_id / run_id / step_no；触发运行支持 Idempotency-Key。

### 6. SSE 事件协议（最小可用）
- 事件：task_started | log | tool_called | tool_result | plan | clarification_needed | done | error。
- 规则：
  - 事件载荷包含 event、ts、run_id、seq；必要时附 task_id/level/payload。
  - 正常结束以 event: done 或 [DONE] 文本终止；错误以 event:error，并仍以 [DONE] 结束。
  - 客户端重连带 Last-Event-Id（seq），服务端最佳努力续传。

### 7. 工具最小集与安全
- 白名单：HTTP、SQL、脚本；禁止动态启用未审计工具。
- 参数 Schema 校验：字段白名单、长度/范围/枚举/正则约束必须生效。
- 最小权限与隔离：HTTP 允许域名/方法白名单；SQL 限定 schema；脚本沙箱目录与资源限额。
- 超时/重试/限流为必配；工具级日志需可追踪到 run_id/step_no。

### 8. 上下文与计划
- 历史消息构建必须实现；达到阈值时在“滑动窗口”和“摘要”间切换（阈值可配置且可测试）。
- 默认“自动计划 + 最小澄清（1–3 问）”；必要时“计划确认”（人在回路）。

### 9. 配置与安全
- 配置用 Pydantic Settings 管理；机密仅通过环境变量/密钥管理注入，禁止明文落库/代码库。
- 统一 CORS；请求大小/速率限制（如对外）；对话与关键操作需审计。

### 10. 数据与迁移
- SQLAlchemy 2.0；所有 DDL 变更必须通过 Alembic 迁移与评审，禁止绕过迁移脚本。

### 11. 可用性与可观测
- 健康检查：/healthz、/readiness。
- 指标：执行数、成功率、P95 时延。
- 日志：结构化 JSON；全链路 trace_id；敏感信息脱敏。

### 12. 测试与质量门禁（TDD 强制要求）
- **TDD 流程强制执行**：
  1. 先编写测试用例（描述需求与验收标准）
  2. 实现功能（最小代码使测试通过）
  3. 重构优化（测试保证不破坏逻辑）
- **测试金字塔**：Domain 单元 > Application 集成 > API/E2E。
- **覆盖率要求**：
  - Domain 层 ≥ 80%（核心业务逻辑必须覆盖）
  - Application 层 ≥ 70%（用例编排）
  - Infrastructure 层 ≥ 60%（适配器）
  - API 层核心路径 100%（创建 Agent、触发运行、SSE 流）
- **CI 门禁**：ruff → pyright → pytest；未通过不得合入。
- **必须提供的测试用例**：
  - SSE 事件序列与终止信号测试
  - 执行器状态机测试（PENDING → RUNNING → SUCCEEDED/FAILED）
  - 幂等性测试（相同 run_id 重复触发）
  - Domain 实体不变式测试（如 Agent 必须有 start+goal）

### 13. 里程碑与范围控制
- P0（MVP）：POST/PATCH/POST runs/GET run/GET stream、轻量执行器、工具最小集、上下文滑动窗口。
- P1：Clarifier、验收标准、人在回路、统一错误码、限流、余额检查、配置界面。
- P2：Model HA Gateway、计费/配额/多租户、MCP Gateway、RAG 流水线。
- 未到对应阶段不得提前实现 P2 能力；如需提前，必须提交 ADR 并获批准。

### 14. 变更控制（防偏航）
- 任何违反本规则的技术选型/架构/接口变更，必须走“变更申请 + 评审（含影响评估/回滚方案）”。
- 本文件为单一事实来源；与其他文档冲突时，以本文件为准（审批后同步更新其他文档）。
