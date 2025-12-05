# 统一定义目录

本目录存放统一格式的节点和工具定义文件。

## 目录结构

```
definitions/
├── nodes/          # 节点定义
│   ├── llm.yaml
│   ├── api.yaml
│   ├── code.yaml
│   └── ...
├── tools/          # 工具定义
│   ├── http_request.yaml
│   ├── llm_call.yaml
│   └── ...
└── README.md
```

## 统一定义格式

所有定义文件使用 YAML 格式，包含以下字段：

### 必需字段

- `name`: 定义名称（唯一标识）
- `kind`: 定义类型（`node` 或 `tool`）
- `description`: 描述
- `version`: 版本号
- `parameters`: 参数列表
- `executor_type`: 执行器类型

### 可选字段

- `category`: 分类（仅工具）
- `tags`: 标签列表
- `returns`: 返回值 Schema
- `allowed_child_types`: 允许的子节点类型（仅节点）
- `constraints`: 参数约束

## 参数定义格式

```yaml
parameters:
  - name: param_name
    type: string|number|boolean|object|array|any
    description: 参数描述
    required: true|false
    default: 默认值
    enum: [可选值列表]
    constraints:
      min: 最小值
      max: 最大值
```

## 使用示例

```python
from src.domain.services.unified_definition import (
    UnifiedYAMLLoader,
    UnifiedDefinitionRegistry,
    UnifiedValidator,
)

# 加载定义
loader = UnifiedYAMLLoader()
definitions = loader.load_from_directory("definitions/nodes")

# 注册到统一注册中心
registry = UnifiedDefinitionRegistry()
for definition in definitions:
    registry.register(definition)

# 验证参数
validator = UnifiedValidator()
llm_def = registry.get("llm")
result = validator.validate(llm_def, {"user_prompt": "Hello"})
```

## 与现有系统的兼容性

统一定义系统与现有的 `NodeRegistry` 和 `ToolEngine` 完全兼容：

- 可以从 `NodeRegistry` 导入节点定义
- 可以从 `ToolEngine` 导入工具定义
- 验证逻辑与原系统保持一致
- 执行器可以通过适配器桥接
