# Workflow 可用性验收标准表（V0）

> 日期：2026-02-01
> 口径：以“编辑器工作流链路（体系 B）”为唯一验收口径：`NodeType + ExecutorRegistry + WorkflowSaveValidator + UI`。
> 本项目当前约束：**仅支持 sqlite**（`database_url` 必须以 `sqlite:///` 开头）。
> 模型类节点当前承诺范围：**仅支持 OpenAI provider**（`openai/*` 或不带 provider 前缀的 OpenAI 模型名）。
> Draft 行为：`workflow.status=draft` 时，SaveValidator 仅对 start->end 主连通子图做可执行性强校验；非主子图允许 in-progress（不阻断保存）。

## 0. 验收闭环（必须同时满足）

1) 可表达 → 2) 可生成 → 3) 可校验（前端表单 + `WorkflowSaveValidator`）→ 4) 可执行（deterministic 可回归）→ 5) 可解释（错误/事件可定位）。

## 1. Canonical 节点集合（以 UI 可拖拽为准）

`start/end/httpRequest/textModel/conditional/javascript/python/transform/prompt/imageGeneration/audio/tool/embeddingModel/structuredOutput/database/file/notification/loop`

> 说明：兼容别名（如 `http/llm/condition`）仅用于历史兼容/导入；新示例/新文档/新 prompt **禁止**使用别名。

## 2. 节点级验收要点（摘要表）

| node_type | 保存必需最小配置（概要） | deterministic 执行期望（概要） | 外部依赖/副作用（非 deterministic） | 备注（关键边界） |
| --- | --- | --- | --- | --- |
| start | 无 | 输出 `initial_input` | 无 | 工作流必须存在 start→end 路径 |
| end | 无 | 输出第一个输入 | 无 |  |
| httpRequest | `url` + `method`（建议 `mock_response`） | 返回 stub 或 `mock_response` | 外部 HTTP | headers/body/mock_response 支持 JSON string 或对象 |
| textModel | `model`（prompt 可选：有入边即可） | 返回 deterministic stub 文本/报告 | 外部 LLM | 仅支持 OpenAI provider；多入边且无 prompt 时必须配置 `promptSourceNodeId` |
| prompt | `content` | 返回渲染后的文本 | 无 | 支持 `{input1}` 占位符 |
| transform | `type` + type-specific 字段（如 field_mapping 需 `mapping`） | 返回转换后的数据 | 无 | `mapping` 允许引用 `input1` 等 |
| database | `sql`（`database_url` 缺省会被补为 sqlite） | 执行 SQLite 并返回 rows/rows_affected | 本地文件/SQLite | **仅 sqlite**（fail-closed） |
| conditional | `condition` | 返回 `{result, branch}` | 无 | condition 以 Python 表达式 eval（安全 builtins） |
| loop | `type`（range/for_each/while）+ 必需字段 | 返回迭代结果数组 | 无 | range: 必须 `end` + `code` |
| python | `code` | 返回 `result` | 无 | 禁止 import/危险关键字 |
| javascript | `code` | 返回 `result`（或默认回退） | 无 | 以 Python exec 近似执行（非真正 JS 引擎） |
| file | `operation` + `path` | 读写本地文件/目录 | 本地文件系统 | write/append 默认 content=""（可为空） |
| notification | `type` + `message` + type-specific 字段 | deterministic 下返回 stub（不外发） | 外部 HTTP/SMTP | webhook/slack/email 字段要求不同 |
| embeddingModel | `model`（输入可来自入边） | deterministic 下返回 stub embeddings | 外部 Embedding API | 仅支持 OpenAI provider |
| imageGeneration | `model`（prompt 可来自入边） | deterministic 下返回 stub image payload | 外部 Image API | 仅支持 OpenAI provider |
| audio | `model`（text 可来自入边） | deterministic 下返回 stub audio payload | 外部 TTS API | 仅支持 OpenAI provider |
| structuredOutput | `schemaName` + `schema`（prompt 可来自入边） | deterministic 下返回 stub JSON | 外部 LLM | schema 支持 JSON string 或对象 |
| tool | `tool_id`（必须存在且非 deprecated） | 依赖 DB 中存在可用 tool | 取决于 tool 实现 | 环境依赖：需注册 tool executor + tools 表数据 |

## 3. “start → node → end” 最小可执行配置示例（用于回归）

> 说明：以下仅列出每个节点的 **config** 示例；实际回归需组装成 `start → node → end` 的 DAG，并确保通过 `WorkflowSaveValidator.validate_or_raise()`。

### 3.1 httpRequest

```json
{
  "url": "https://example.test/api",
  "method": "GET",
  "mock_response": { "status": 200, "data": { "ok": true } }
}
```

### 3.2 textModel

```json
{
  "model": "openai/gpt-4",
  "prompt": "hello"
}
```

### 3.3 prompt

```json
{
  "content": "Hello {input1}"
}
```

### 3.4 transform（field_mapping）

```json
{
  "type": "field_mapping",
  "mapping": { "data": "input1" }
}
```

### 3.5 database（sqlite-only）

```json
{
  "database_url": "sqlite:///tmp/e2e/acceptance.db",
  "sql": "SELECT 1 as value",
  "params": {}
}
```

### 3.6 conditional

```json
{
  "condition": "True"
}
```

### 3.7 loop（range）

```json
{
  "type": "range",
  "start": 0,
  "end": 3,
  "step": 1,
  "code": "result = i"
}
```

### 3.8 python

```json
{
  "code": "result = 1"
}
```

### 3.9 javascript

```json
{
  "code": "result = 1"
}
```

### 3.10 file（write）

```json
{
  "operation": "write",
  "path": "tmp/e2e/acceptance.txt",
  "encoding": "utf-8",
  "content": "hello"
}
```

### 3.11 notification（webhook）

```json
{
  "type": "webhook",
  "url": "https://example.test/webhook",
  "message": "done",
  "headers": {}
}
```

### 3.12 embeddingModel（输入来自入边即可）

```json
{
  "model": "openai/text-embedding-3-small",
  "dimensions": 3
}
```

### 3.13 imageGeneration（prompt 来自入边即可）

```json
{
  "model": "openai/dall-e-3",
  "aspectRatio": "1:1",
  "outputFormat": "png"
}
```

### 3.14 audio（text 来自入边即可）

```json
{
  "model": "openai/tts-1",
  "voice": "alloy",
  "speed": 1.0
}
```

### 3.15 structuredOutput（prompt 来自入边即可）

```json
{
  "schemaName": "Ticket",
  "mode": "object",
  "schema": "{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"}},\"required\":[\"name\"]}"
}
```
