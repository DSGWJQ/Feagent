# 开发规范（Development Guide）

本文件用于修复 README 的文档指针漂移，并提供**最小但可执行**的开发约定。
目标：减少重复实现、避免边界坍塌，确保“多智能体协作 + 事件驱动”主链路长期可维护。

> 权威规划与验收标准以 `docs/planning/PROJECT_SIMPLIFICATION_DEDUP_PLAN.md` 为准。

---

## 1. 必须遵守的工程红线

1. **单一路径**：同一业务能力不得存在两套并行实现（除非标记为 experiments 且默认禁用）。
2. **单一契约**：事件/流式输出/落库必须共享同一事件语义，不允许 callback 与 EventBus 双轨并存。
3. **单一权威实现（SoT）**：
   - workflow 执行语义：`WorkflowEngine`
   - workflow chat 更新：`UpdateWorkflowByChatUseCase`
   - Domain LLM 抽象：`LLMPort`
4. **禁止 WebSocket 运行时链路**：实时推送统一 SSE；前端不得实例化 `new WebSocket(...)`。

---

## 2. 分层开发规则（DDD-lite）

### Interface（`src/interfaces/`）
- 只做协议适配：HTTP/SSE、DTO、依赖注入、错误映射。
- 禁止在路由里编排复杂业务逻辑、直接落库、绕过 Application 门禁。

### Application（`src/application/`）
- 负责：用例编排、事务边界、门禁（Coordinator/Audit）、幂等、事件落库入口。
- 输出：稳定的 UseCase/Service，供 Interface 调用。

### Domain（`src/domain/`）
- 负责：实体/值对象/领域服务/领域事件/端口（Ports）。
- 禁止：引用 FastAPI、SQLAlchemy、LangChain 等基础设施细节。

### Infrastructure（`src/infrastructure/`）
- 负责：实现 Domain Ports（DB/外部 API/LLM/工具执行器）。
- 禁止：把业务规则写进适配器，或绕过 Application 的用例门禁。

---

## 3. 测试与验收（强制）

每个阶段改动都必须：
- **先修复/同步测试**，再合并代码；不允许把红灯留给下一阶段。
- 对关键主链路至少保留：
  - conversation SSE（澄清对话）
  - workflow chat-create SSE（显式创建）
  - workflow execute/stream（RunEvents 落库 + 终态/确认事件）

建议的基本命令：
```bash
pytest -q
```

前端（若本地依赖已安装）：
```bash
cd web
pnpm test
```

---

## 4. 变更流程（外科手术式）

1. 定位（rg/结构化搜索）
2. 切开（读文件，理解契约与调用方）
3. 修复（最小改动 + 防御性编程）
4. 缝合（跑测试 + 门禁扫描）
