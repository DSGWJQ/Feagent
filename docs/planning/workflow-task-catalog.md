# 可生成工作流任务库（基于已注册执行器）

## 1. 使用说明
本任务库基于当前系统已注册的可执行节点能力整理，确保“可拖拽节点=可执行节点”。
所有示例均以“对话提示词”形式给出，适用于工作流自动生成场景。

## 2. 可执行节点清单（执行边界）
- start
- end
- httpRequest
- textModel
- prompt
- transform
- database
- file
- notification
- conditional
- loop
- python
- javascript
- tool
- embeddingModel
- imageGeneration
- audio
- structuredOutput

> 说明：`http/llm/condition` 等别名仅用于历史兼容/导入，不进入新示例与新对话生成。

## 3. 任务场景清单（覆盖高频场景）

### 3.1 数据清洗 / ETL
- 节点思路：FILE/DB/HTTP → TRANSFORM/PYTHON → FILE/DB
- 提示词：
  “请生成一个工作流：从数据库读取原始数据，做去空值/去重/字段格式化，然后把清洗结果写回数据库。”

### 3.2 数据分析与报告
- 节点思路：DATABASE → TRANSFORM → PYTHON → LLM → FILE
- 提示词：
  “请生成一个工作流：查询最近30天销售数据，统计核心指标并生成 Markdown 报告，保存到文件。”

### 3.3 API 数据拉取与同步
- 节点思路：HTTP → TRANSFORM → DATABASE
- 提示词：
  “请生成一个工作流：调用外部订单 API，映射字段并入库。”

### 3.4 规则校验 / 异常检测
- 节点思路：PYTHON/TRANSFORM → CONDITIONAL → NOTIFICATION
- 提示词：
  “请生成一个工作流：检查订单金额是否异常，超过阈值就发通知，否则结束。”

### 3.5 批量处理（循环）
- 节点思路：DATABASE → LOOP → HTTP/LLM/TRANSFORM → END
- 提示词：
  “请生成一个工作流：遍历用户列表，逐个调用画像接口并汇总结果。”

### 3.6 内容生成（文本）
- 节点思路：PROMPT → LLM → FILE/NOTIFICATION
- 提示词：
  “请生成一个工作流：根据产品卖点生成营销文案，保存到文件并发送通知。”

### 3.7 结构化抽取（表单/工单）
- 节点思路：LLM → STRUCTURED_OUTPUT → DATABASE
- 提示词：
  “请生成一个工作流：输入用户对话文本，抽取 name/phone/issue/priority 并写入数据库。”

### 3.8 向量化 / 语义检索准备
- 节点思路：EMBEDDING → DATABASE/FILE
- 提示词：
  “请生成一个工作流：对 FAQ 文本生成向量并写入数据库。”

### 3.9 文本 + 图片生成
- 节点思路：LLM → IMAGE → FILE/NOTIFICATION
- 提示词：
  “请生成一个工作流：根据活动主题生成文案，再生成配图并保存。”

### 3.10 文本转语音
- 节点思路：LLM/INPUT → AUDIO → FILE/NOTIFICATION
- 提示词：
  “请生成一个工作流：把摘要内容生成语音并保存到文件。”

### 3.11 代码逻辑计算
- 节点思路：PYTHON/JAVASCRIPT → TRANSFORM → FILE/DB
- 提示词：
  “请生成一个工作流：根据输入数据计算评分并输出到文件。”

### 3.12 自动化通知与回执
- 节点思路：HTTP/DB → NOTIFICATION → END
- 提示词：
  “请生成一个工作流：当数据更新完成后通知指定 webhook。”

## 4. 通用提示词模板
- “请生成一个工作流，输入是：<输入类型>，输出是：<输出类型>，要求包含：<关键步骤/节点>，并输出可执行节点配置。”

## 5. 注意事项
- 上述任务均依赖真实执行器能力与有效配置（数据库连接、API 密钥等）。
- 结构化输出节点需提供 JSON Schema 才可通过校验并执行。
- database 节点当前仅支持 `sqlite:///`（非 sqlite 将在保存阶段 fail-closed）。
- 模型类节点（textModel/embeddingModel/imageGeneration/audio/structuredOutput）当前仅承诺 OpenAI provider（`openai/*` 或不带 provider 前缀的 OpenAI 模型名）。
