# 前端节点可用性补齐方案（执行器补齐 / OpenAI）

## 1. 背景与问题
当前前端可拖拽节点集合包含 `embeddingModel` / `imageGeneration` / `audio` / `structuredOutput` 等类型，但后端执行器注册中缺失相应实现，导致这些节点在保存或执行时会失败。

## 2. 目标与完成标准
### 2.1 目标
- 前端可拖拽的全部节点都能真实执行
- UI 外观、交互与布局保持不变

### 2.2 完成标准
- 前端拖拽节点 100% 可保存、可执行
- workflow 保存校验无 `missing_executor`
- 每种节点至少 1 条真实执行用例通过
- UI 无改动

## 3. 范围（必须可执行的节点）
- embeddingModel
- imageGeneration
- audio
- structuredOutput

## 4. 决策与原则
- 供应商：OpenAI（统一配置与调用）
- structuredOutput：独立执行器实现，内部复用 LLM 调用链路
- 前端字段保持不变：后端执行器入口做字段映射与 normalize

## 5. 方案概述
### 5.1 执行器补齐
新增 4 个执行器并注册到 `NodeExecutorRegistry`：
- EmbeddingExecutor：向量生成
- ImageGenerationExecutor：图片生成
- AudioExecutor：语音生成
- StructuredOutputExecutor：结构化输出（JSON Schema / response_format）

### 5.2 Schema 与校验补齐
- NodeRegistry 增加 4 类节点 Schema 与默认模板
- workflow_save_validator 增加必填字段校验

### 5.3 字段兼容策略（UI 不变）
- 前端字段保持原样，如：
  - `maxTokens` / `schemaName` / `aspectRatio` / `outputFormat`
- 后端执行器入口做映射（camelCase → OpenAI 需要的字段）
- 兼容旧工作流字段，避免历史数据失效

## 6. 执行器设计概要
### 6.1 EmbeddingExecutor
- 输入：`model`, `dimensions`, `input/text`
- 输出：`embeddings`, `usage`

### 6.2 ImageGenerationExecutor
- 输入：`model`, `prompt`, `aspectRatio`, `outputFormat`
- 输出：`image_url` 或 `base64`

### 6.3 AudioExecutor
- 输入：`model`, `voice`, `text`, `speed`
- 输出：`audio_url` 或 `base64`

### 6.4 StructuredOutputExecutor
- 输入：`schemaName`, `mode`, `schema`, `prompt/inputs`
- 输出：结构化 JSON 数据
- 策略：严格 schema 校验 + 1 次重试

## 7. 依赖与配置
- 必须配置 `OPENAI_API_KEY`
- Key 缺失时硬失败（避免“假可用”）

## 8. 实施拆解（不含代码）
1) 盘点前端节点字段与默认值
2) 新增执行器实现 + OpenAI 调用
3) 注册执行器
4) 补齐 NodeRegistry Schema
5) 扩展保存校验
6) 编写最小执行用例
7) 回归验证 UI 不变

## 9. 验收用例（示例）
- embeddingModel：输入文本 → 输出向量数组
- imageGeneration：提示词 → 输出图片结果
- audio：文本 → 输出音频结果
- structuredOutput：给定 schema → 输出合法 JSON

## 10. 风险与缓解
- Key 缺失：执行时明确报错
- schema 不一致：严格校验 + 1 次重试
- 字段不一致：统一入口映射

## 11. 原则应用总结
- KISS：前端不改动，仅补齐后端执行能力
- SOLID：执行器职责单一、可独立测试
- DRY：structuredOutput 复用 LLM 调用链路
- YAGNI：不引入多余 UI 功能
