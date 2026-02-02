# Workflow 差异修复清单（P0/P1/P2）

> 日期：2026-02-01
> 主策略：以“体系 B 事实源”为权威（`NodeType + ExecutorRegistry + WorkflowSaveValidator + UI`），对外只承诺“可保存且可执行（或可解释失败）”的能力。
> 本轮约束：**仅支持 sqlite**；多模态/模型类节点当前版本 **仅承诺 OpenAI provider**（避免 Contract Drift）。

## 0. 背景：本清单解决什么问题

本项目当前存在典型的 Contract Drift：
- UI/文档暴露了节点或选项，但 runtime 不支持（导致“保存通过但执行必失败”或“可表达但不可生成”）。
- 对话 prompt 与 UI palette 节点集合不一致（导致对话侧生成不了 UI 能表达的能力）。

本清单的目标是：先用最小代价清掉 P0，再补齐 P1/P2。

## 1. P0（零容忍）

### P0-1 仅承诺 OpenAI provider：收敛 UI 模型选项（避免必败配置）

- 现状：
  - `web/src/features/workflows/components/NodeConfigPanel.tsx` 的 `textModel` 提供 `anthropic/*` 与 `google/*` 选项；
  - `textModel` 的 `google` provider 在 `LlmExecutor` 中明确未实现；
  - 工程内也没有 `anthropic_api_key` 的 Settings 字段，导致 Anthropic 运行时不可配置。
- 修复：
  - UI：移除/隐藏 `anthropic/*`、`google/*` 模型选项，仅保留 `openai/*`。
- 验收：
  - 用户无法在 UI 上保存一个“当前实现必然执行失败”的 textModel provider 配置。

### P0-2 imageGeneration 选项漂移：移除 Gemini（当前 runtime 仅支持 OpenAI）

- 现状：
  - UI 提供 `gemini-2.5-flash-image`（无 provider 前缀）。
  - `ImageGenerationExecutor` 仅支持 OpenAI provider；无前缀会被当作 OpenAI 模型名 → 真实执行大概率 400。
- 修复：
  - UI：移除 Gemini 选项，仅保留 OpenAI 图像模型（如 `openai/dall-e-3`）。
- 验收：
  - imageGeneration 节点在 fullreal 下不会因 UI 误导而落入必败配置。

### P0-3 SaveValidator fail-closed：禁止保存非 OpenAI provider 的模型类节点

- 现状：
  - embedding/image/audio/structuredOutput 等执行器在 runtime 仅支持 OpenAI，但 `WorkflowSaveValidator` 未校验 provider；
  - 导致“保存通过但执行必失败”（fullreal/hybrid 下发生）。
- 修复（后端兜底）：
  - `src/domain/services/workflow_save_validator.py`：对以下节点的 `model` 做 provider 校验（provider!=openai → structured error）：
    - `textModel`（并显式拒绝 `google/*` / `anthropic/*`）
    - `embeddingModel`
    - `imageGeneration`
    - `audio`
    - `structuredOutput`（如用户显式填写 `model`）
- 验收：
  - 任意非 OpenAI provider 的配置在保存阶段被拒绝，返回结构化错误（code/message/path）。

### P0-4 对话链路 supported node list 与 UI 对齐（可表达→可生成）

- 现状：
  - `src/domain/services/workflow_chat_service_enhanced.py` 的 prompt 节点清单未覆盖 UI 节点（缺 `javascript/embeddingModel/imageGeneration/audio/structuredOutput`）。
- 修复：
  - 更新对话 prompt：supported node list 与 UI 一致，并在规则中写明：
    - 模型类节点仅允许 OpenAI provider（当前版本承诺范围）
    - `tool` 仍保持“必须明确 tool_id，否则 ask_clarification”（避免生成保存必失败）
- 验收：
  - 对话侧可以生成 UI 支持的节点类型，且不会生成“保存必失败”的 provider 配置。

### P0-5 任务库/文档口径收敛到 Canonical NodeType（避免对外承诺漂移）

- 现状：`docs/planning/workflow-task-catalog.md` 同时列出 `http/httpRequest`、`llm/textModel`、`python/javascript` 等别名组合。
- 修复：
  - 文档：仅保留 canonical（V0）节点名；别名只作为“历史兼容”注释出现。
  - 文档：显式声明模型类节点当前仅承诺 OpenAI provider（与 SaveValidator/runtime 对齐）。
- 验收：
  - 任务库示例不会诱导用户生成/保存一个“当前实现必败”的节点类型或配置。

## 2. P1（重要但不阻塞基本闭环）

### P1-1 tool 节点的可用性提示/可见性策略

- 背景：tool 能力依赖 DB schema + tools 数据 + executor registry 注入（`session_factory`）。
- 建议：
  - UI 在 tools 列表为空时将 tool 节点标注为“不可用/需先创建 tool”，或从 palette 中隐藏（避免用户走入死路）。

### P1-2 textModel 多入边可用性（UX 防呆）

- 背景：SaveValidator 对多入边 textModel 有硬约束（需要 `promptSourceNodeId` 或通过 Prompt 合并输入）。
- 建议：
  - UI 提供 promptSourceNodeId 选择器或一键插入 Prompt 合并节点（详见 `docs/planning/workflow-capability-unification-milestones.md` M2）。

## 3. P2（结构性治理 / 长期）

### P2-1 能力事实源对外输出（capabilities endpoint）

- 目标：新增 `/api/workflows/capabilities`，让 UI 与对话 prompt 从同一份能力矩阵渲染，彻底消除硬编码漂移。
- 参考：`docs/planning/workflow-capability-unification-milestones.md` M1。
