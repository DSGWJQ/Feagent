# 工具配置规范 (Tool Configuration Specification)

> **版本**: 1.0.0
> **更新日期**: 2025-01-22
> **适用项目**: Feagent

---

## 概述

本文档定义了 Feagent 平台中工具配置文件的 YAML Schema 规范。工具是 Agent 执行任务的基本单元，通过标准化的配置格式实现工具的定义、共享和复用。

### 设计目标

1. **标准化**: 统一工具配置格式，方便管理和共享
2. **可扩展**: 支持多种实现方式（内置、HTTP、JavaScript、Python）
3. **自描述**: 配置文件包含完整的工具信息，便于自动生成文档和 UI
4. **可验证**: 支持 CI 自动检查配置文件的有效性

---

## Schema 定义

### 完整结构

```yaml
# 必需字段
name: string          # 工具名称（唯一标识）
description: string   # 工具描述（支持多行）
category: string      # 工具分类
entry: object         # 入口配置

# 可选字段
version: string       # 版本号（默认 "1.0.0"）
author: string        # 作者
tags: string[]        # 标签列表
icon: string          # 图标（emoji 或 URL）
shareable_scope: string  # 可共享范围

# 输入/输出定义
parameters: array     # 参数列表
returns: object       # 返回值 Schema
```

### 字段详细说明

#### name (必需)

工具的唯一名称，用于引用和调用。

- **类型**: `string`
- **约束**: 非空，建议使用 snake_case 格式
- **示例**: `"http_request"`, `"llm_call"`, `"file_reader"`

#### description (必需)

工具的详细描述，说明工具的功能和使用场景。

- **类型**: `string`
- **支持**: 多行文本（使用 YAML `|` 语法）
- **示例**:
  ```yaml
  description: |
    发送 HTTP 请求获取数据。
    支持 GET、POST、PUT、DELETE 等方法。
  ```

#### category (必需)

工具的功能分类，用于过滤和组织。

- **类型**: `string`
- **有效值**:
  | 值 | 说明 |
  |------|------|
  | `http` | HTTP 请求工具 |
  | `database` | 数据库操作工具 |
  | `file` | 文件处理工具 |
  | `ai` | AI 相关工具（LLM、向量检索等） |
  | `notification` | 通知工具（邮件、短信等） |
  | `custom` | 用户自定义工具 |

#### entry (必需)

工具的入口配置，定义如何执行工具。

- **类型**: `object`
- **必需子字段**: `type`

##### 入口类型

| type | 说明 | 额外字段 |
|------|------|----------|
| `builtin` | 内置工具 | `handler`: 内置处理器名称 |
| `http` | HTTP 请求 | `url`, `method`, `headers` (可选) |
| `javascript` | JavaScript 代码 | `code`: JavaScript 代码字符串 |
| `python` | Python 模块 | `module`, `function` |

##### 示例

```yaml
# 内置工具
entry:
  type: builtin
  handler: http_request

# HTTP 请求
entry:
  type: http
  url: https://api.example.com/endpoint
  method: POST
  headers:
    Content-Type: application/json
    Authorization: Bearer ${API_KEY}

# JavaScript
entry:
  type: javascript
  code: |
    function execute(input) {
      return { result: input.value * 2 };
    }

# Python
entry:
  type: python
  module: tools.my_tool
  function: execute
```

#### version (可选)

工具版本号，遵循语义化版本规范。

- **类型**: `string`
- **默认值**: `"1.0.0"`
- **格式**: `MAJOR.MINOR.PATCH`
- **示例**: `"1.0.0"`, `"2.1.3"`

#### author (可选)

工具作者或维护者。

- **类型**: `string`
- **示例**: `"system"`, `"john@example.com"`

#### tags (可选)

工具标签列表，用于搜索和分类。

- **类型**: `string[]`
- **示例**:
  ```yaml
  tags:
    - http
    - api
    - network
  ```

#### icon (可选)

工具图标，支持 emoji 或图片 URL。

- **类型**: `string`
- **示例**: `"🌐"`, `"https://example.com/icon.png"`

#### shareable_scope (可选)

工具的可共享范围。

- **类型**: `string`
- **默认值**: `"private"`
- **有效值**:
  | 值 | 说明 |
  |------|------|
  | `private` | 仅创建者可见 |
  | `team` | 团队内可见 |
  | `public` | 所有人可见（工具市场） |

#### parameters (可选)

工具的输入参数列表。

- **类型**: `array`
- **元素结构**:

```yaml
parameters:
  - name: string        # 参数名称（必需）
    type: string        # 参数类型（必需）
    description: string # 参数描述（必需）
    required: boolean   # 是否必需（默认 false）
    default: any        # 默认值（可选）
    enum: string[]      # 枚举值列表（可选）
```

##### 参数类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `string` | 字符串 | `"hello"` |
| `number` | 数字（整数或浮点数） | `42`, `3.14` |
| `boolean` | 布尔值 | `true`, `false` |
| `object` | JSON 对象 | `{"key": "value"}` |
| `array` | JSON 数组 | `[1, 2, 3]` |
| `any` | 任意类型 | - |

##### 示例

```yaml
parameters:
  - name: url
    type: string
    description: 请求 URL
    required: true

  - name: method
    type: string
    description: HTTP 方法
    required: true
    enum: [GET, POST, PUT, DELETE]

  - name: timeout
    type: number
    description: 超时时间（秒）
    required: false
    default: 30
```

#### returns (可选)

工具的返回值 Schema，描述输出数据结构。

- **类型**: `object`
- **格式**: 键为字段名，值可以是类型字符串或详细描述对象

```yaml
# 简单格式
returns:
  status_code: number
  body: any

# 详细格式
returns:
  status_code:
    type: number
    description: HTTP 状态码
  body:
    type: any
    description: 响应体
```

---

## 工具目录结构

```
tools/
├── http_request.yaml      # HTTP 请求工具
├── llm_call.yaml          # LLM 调用工具
├── file_reader.yaml       # 文件读取工具
├── json_transformer.yaml  # JSON 转换工具
└── text_analyzer.yaml     # 文本分析工具
```

### 命名规范

- 文件名使用 snake_case
- 文件扩展名支持 `.yaml` 或 `.yml`
- 文件名应与工具 `name` 字段一致

---

## 完整示例

### HTTP 请求工具

```yaml
name: http_request
description: |
  发送 HTTP 请求获取数据。
  支持 GET、POST、PUT、DELETE 等方法。
category: http
version: "1.0.0"
author: system
tags:
  - http
  - network
  - api
icon: "🌐"
shareable_scope: public

entry:
  type: builtin
  handler: http_request

parameters:
  - name: url
    type: string
    description: 请求 URL
    required: true

  - name: method
    type: string
    description: HTTP 方法
    required: true
    enum: [GET, POST, PUT, DELETE]

  - name: headers
    type: object
    description: 请求头
    required: false
    default: {}

  - name: body
    type: object
    description: 请求体
    required: false

  - name: timeout
    type: number
    description: 超时时间（秒）
    required: false
    default: 30

returns:
  status_code: number
  headers: object
  body: any
```

### JavaScript 自定义工具

```yaml
name: json_transformer
description: 使用 JavaScript 转换 JSON 数据
category: custom
version: "1.0.0"

entry:
  type: javascript
  code: |
    function execute(input) {
      const { data, mapping } = input;
      const result = {};
      for (const [key, path] of Object.entries(mapping)) {
        result[key] = data[path];
      }
      return { result };
    }

parameters:
  - name: data
    type: object
    description: 输入数据
    required: true

  - name: mapping
    type: object
    description: 字段映射规则
    required: true

returns:
  result: object
```

---

## API 使用

### 加载工具配置

```python
from src.domain.services.tool_config_loader import ToolConfigLoader

loader = ToolConfigLoader()

# 从 YAML 字符串解析
config = loader.parse_yaml(yaml_content)

# 从文件加载
config = loader.load_from_file("tools/http_request.yaml")

# 从目录批量加载
configs = loader.load_from_directory("tools/")

# 转换为 Tool 实体
tool = loader.to_tool_entity(config)

# 导出为 YAML
yaml_output = loader.export_to_yaml(tool)
```

### 验证配置

```python
from src.domain.services.tool_config_loader import (
    ToolConfigLoader,
    ToolConfigValidationError,
)

loader = ToolConfigLoader()

try:
    config = loader.parse_yaml(yaml_content)
except ToolConfigValidationError as e:
    print(f"验证错误: {e}")
    print(f"问题字段: {e.field}")
```

---

## CI 验证

项目包含 CI 检查脚本，确保所有工具配置文件有效：

```bash
# 运行配置验证
python -m scripts.validate_tool_configs

# 或使用 pytest
pytest tests/integration/test_tool_configs.py -v
```

### 验证规则

1. **必需字段检查**: name, description, category, entry
2. **类型验证**: 参数类型必须是有效值
3. **入口类型检查**: entry.type 必须是支持的类型
4. **分类验证**: category 必须是预定义值

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2025-01-22 | 初始版本，定义核心 Schema |

---

## 参考资料

- [技术方案：工具与模型管理系统](../技术方案/05-工具与模型管理系统.md)
- [Domain 层：Tool 实体](../../src/domain/entities/tool.py)
- [示例工具目录](../../tools/)
