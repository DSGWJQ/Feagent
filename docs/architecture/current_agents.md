# 多智能体协作（现状审计 / 实验链路说明）

本文件用于修复 README 的历史链接，并明确：**多智能体链路是实验/审计口径**，不作为 Workflow 主链路事实源。

## 1. 现状（基线）

- 主入口（运行时）：`src/interfaces/api/main.py`（FastAPI lifespan）
- 统一事件总线：`src/domain/services/event_bus.py`
- 对话编排（SSE）：`src/interfaces/api/routes/conversation_stream.py`
- Workflow 主链路（执行）：`/api/workflows/{id}/execute/stream` → `WorkflowRunExecutionEntry`

## 2. 实验链路边界

- 任何“第二套通道/第二套执行语义/第二套事件语义”都会被视为冗余，必须迁移到 experiments 或删除。
- WebSocket 链路已被明确弃用（项目精简决策），实时推送统一使用 SSE。

## 3. 权威规划

一次性精简与去冗余的阶段计划与严格验收标准见：
- `docs/planning/PROJECT_SIMPLIFICATION_DEDUP_PLAN.md`
