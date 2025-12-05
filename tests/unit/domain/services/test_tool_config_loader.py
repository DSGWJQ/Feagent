"""工具配置加载器测试 - 阶段 1

测试目标：
1. 验证 YAML Schema 定义正确性
2. 验证工具配置文件解析能力
3. 验证配置到 Tool 实体的转换
4. 验证配置验证规则
"""

import pytest
import yaml

from src.domain.entities.tool import Tool, ToolParameter
from src.domain.services.tool_config_loader import (
    ShareableScope,
    ToolConfigLoader,
    ToolConfigSchema,
    ToolConfigValidationError,
    ToolParameterSchema,
)
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus

# =============================================================================
# 第一部分：Schema 数据结构测试
# =============================================================================


class TestToolParameterSchema:
    """工具参数 Schema 测试"""

    def test_create_basic_parameter_schema(self):
        """测试：创建基本参数 Schema"""
        param = ToolParameterSchema(
            name="url",
            type="string",
            description="请求URL",
            required=True,
        )

        assert param.name == "url"
        assert param.type == "string"
        assert param.description == "请求URL"
        assert param.required is True
        assert param.default is None
        assert param.enum is None

    def test_parameter_schema_with_enum(self):
        """测试：带枚举的参数 Schema"""
        param = ToolParameterSchema(
            name="method",
            type="string",
            description="HTTP方法",
            required=True,
            enum=["GET", "POST", "PUT", "DELETE"],
        )

        assert param.enum == ["GET", "POST", "PUT", "DELETE"]

    def test_parameter_schema_with_default(self):
        """测试：带默认值的参数 Schema"""
        param = ToolParameterSchema(
            name="timeout",
            type="number",
            description="超时时间",
            required=False,
            default=30,
        )

        assert param.default == 30
        assert param.required is False


class TestToolConfigSchema:
    """工具配置 Schema 测试"""

    def test_create_minimal_config_schema(self):
        """测试：创建最小化配置 Schema"""
        config = ToolConfigSchema(
            name="http_request",
            description="发送HTTP请求",
            category="http",
            entry={"type": "builtin", "handler": "http_request"},
        )

        assert config.name == "http_request"
        assert config.description == "发送HTTP请求"
        assert config.category == "http"
        assert config.version == "1.0.0"  # 默认版本
        assert config.shareable_scope == ShareableScope.PRIVATE  # 默认私有
        assert config.parameters == []
        assert config.returns == {}

    def test_create_full_config_schema(self):
        """测试：创建完整配置 Schema"""
        config = ToolConfigSchema(
            name="llm_call",
            description="调用大语言模型",
            category="ai",
            version="2.0.0",
            author="system",
            tags=["ai", "llm", "chat"],
            icon="🤖",
            shareable_scope=ShareableScope.PUBLIC,
            entry={
                "type": "http",
                "url": "https://api.openai.com/v1/chat/completions",
                "method": "POST",
            },
            parameters=[
                ToolParameterSchema(
                    name="messages",
                    type="array",
                    description="对话消息",
                    required=True,
                )
            ],
            returns={"content": "string", "usage": "object"},
        )

        assert config.version == "2.0.0"
        assert config.author == "system"
        assert config.tags == ["ai", "llm", "chat"]
        assert config.icon == "🤖"
        assert config.shareable_scope == ShareableScope.PUBLIC
        assert len(config.parameters) == 1
        assert config.returns == {"content": "string", "usage": "object"}


class TestShareableScope:
    """可共享范围枚举测试"""

    def test_shareable_scope_values(self):
        """测试：可共享范围枚举值"""
        assert ShareableScope.PRIVATE.value == "private"
        assert ShareableScope.TEAM.value == "team"
        assert ShareableScope.PUBLIC.value == "public"


# =============================================================================
# 第二部分：YAML 解析测试
# =============================================================================


class TestToolConfigLoaderParsing:
    """工具配置加载器解析测试"""

    def test_parse_yaml_string(self):
        """测试：从 YAML 字符串解析"""
        yaml_content = """
name: http_request
description: 发送HTTP请求获取数据
category: http
version: "1.0.0"
entry:
  type: builtin
  handler: http_request
parameters:
  - name: url
    type: string
    description: 请求URL
    required: true
  - name: method
    type: string
    description: HTTP方法
    required: true
    enum: [GET, POST, PUT, DELETE]
  - name: timeout
    type: number
    description: 超时时间（秒）
    required: false
    default: 30
returns:
  status_code: number
  headers: object
  body: any
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)

        assert config.name == "http_request"
        assert config.description == "发送HTTP请求获取数据"
        assert config.category == "http"
        assert len(config.parameters) == 3
        assert config.parameters[0].name == "url"
        assert config.parameters[0].required is True
        assert config.parameters[1].enum == ["GET", "POST", "PUT", "DELETE"]
        assert config.parameters[2].default == 30
        assert config.returns["status_code"] == "number"

    def test_parse_yaml_file(self, tmp_path):
        """测试：从文件解析 YAML"""
        yaml_content = """
name: file_reader
description: 读取文件内容
category: file
entry:
  type: python
  module: tools.file_reader
  function: read_file
parameters:
  - name: path
    type: string
    description: 文件路径
    required: true
returns:
  content: string
  size: number
"""
        yaml_file = tmp_path / "file_reader.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")

        loader = ToolConfigLoader()
        config = loader.load_from_file(str(yaml_file))

        assert config.name == "file_reader"
        assert config.entry["type"] == "python"
        assert config.entry["module"] == "tools.file_reader"

    def test_parse_yaml_with_shareable_scope(self):
        """测试：解析带可共享范围的配置"""
        yaml_content = """
name: public_tool
description: 公开工具
category: custom
shareable_scope: public
entry:
  type: builtin
  handler: public_handler
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)

        assert config.shareable_scope == ShareableScope.PUBLIC

    def test_parse_yaml_with_team_scope(self):
        """测试：解析团队范围配置"""
        yaml_content = """
name: team_tool
description: 团队工具
category: custom
shareable_scope: team
entry:
  type: builtin
  handler: team_handler
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)

        assert config.shareable_scope == ShareableScope.TEAM


# =============================================================================
# 第三部分：配置验证测试
# =============================================================================


class TestToolConfigValidation:
    """工具配置验证测试"""

    def test_validate_missing_name(self):
        """测试：缺少名称时应抛出验证错误"""
        yaml_content = """
description: 无名工具
category: custom
entry:
  type: builtin
  handler: test
"""
        loader = ToolConfigLoader()

        with pytest.raises(ToolConfigValidationError, match="name"):
            loader.parse_yaml(yaml_content)

    def test_validate_missing_description(self):
        """测试：缺少描述时应抛出验证错误"""
        yaml_content = """
name: no_desc_tool
category: custom
entry:
  type: builtin
  handler: test
"""
        loader = ToolConfigLoader()

        with pytest.raises(ToolConfigValidationError, match="description"):
            loader.parse_yaml(yaml_content)

    def test_validate_missing_category(self):
        """测试：缺少分类时应抛出验证错误"""
        yaml_content = """
name: no_category_tool
description: 无分类工具
entry:
  type: builtin
  handler: test
"""
        loader = ToolConfigLoader()

        with pytest.raises(ToolConfigValidationError, match="category"):
            loader.parse_yaml(yaml_content)

    def test_validate_missing_entry(self):
        """测试：缺少入口时应抛出验证错误"""
        yaml_content = """
name: no_entry_tool
description: 无入口工具
category: custom
"""
        loader = ToolConfigLoader()

        with pytest.raises(ToolConfigValidationError, match="entry"):
            loader.parse_yaml(yaml_content)

    def test_validate_invalid_category(self):
        """测试：无效分类应抛出验证错误"""
        yaml_content = """
name: invalid_category_tool
description: 无效分类工具
category: invalid_category_xyz
entry:
  type: builtin
  handler: test
"""
        loader = ToolConfigLoader()

        with pytest.raises(ToolConfigValidationError, match="category"):
            loader.parse_yaml(yaml_content)

    def test_validate_invalid_parameter_type(self):
        """测试：无效参数类型应抛出验证错误"""
        yaml_content = """
name: invalid_param_tool
description: 参数类型无效的工具
category: custom
entry:
  type: builtin
  handler: test
parameters:
  - name: bad_param
    type: invalid_type_xyz
    description: 无效类型的参数
    required: true
"""
        loader = ToolConfigLoader()

        with pytest.raises(ToolConfigValidationError, match="type"):
            loader.parse_yaml(yaml_content)

    def test_validate_invalid_entry_type(self):
        """测试：无效入口类型应抛出验证错误"""
        yaml_content = """
name: invalid_entry_tool
description: 入口类型无效的工具
category: custom
entry:
  type: invalid_entry_type
  handler: test
"""
        loader = ToolConfigLoader()

        with pytest.raises(ToolConfigValidationError, match="entry.*type"):
            loader.parse_yaml(yaml_content)

    def test_validate_empty_name(self):
        """测试：空名称应抛出验证错误"""
        yaml_content = """
name: ""
description: 空名称工具
category: custom
entry:
  type: builtin
  handler: test
"""
        loader = ToolConfigLoader()

        with pytest.raises(ToolConfigValidationError, match="name"):
            loader.parse_yaml(yaml_content)


# =============================================================================
# 第四部分：配置转换到实体测试
# =============================================================================


class TestToolConfigToEntity:
    """配置转换到 Tool 实体测试"""

    def test_convert_config_to_tool_entity(self):
        """测试：将配置转换为 Tool 实体"""
        yaml_content = """
name: http_request
description: 发送HTTP请求
category: http
version: "1.2.0"
author: system
tags:
  - http
  - network
  - api
icon: 🌐
entry:
  type: builtin
  handler: http_request
parameters:
  - name: url
    type: string
    description: 请求URL
    required: true
returns:
  status_code: number
  body: any
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)
        tool = loader.to_tool_entity(config)

        assert isinstance(tool, Tool)
        assert tool.name == "http_request"
        assert tool.description == "发送HTTP请求"
        assert tool.category == ToolCategory.HTTP
        assert tool.version == "1.2.0"
        assert tool.author == "system"
        assert tool.tags == ["http", "network", "api"]
        assert tool.icon == "🌐"
        assert tool.status == ToolStatus.DRAFT  # 新创建的工具默认是草稿
        assert len(tool.parameters) == 1
        assert tool.parameters[0].name == "url"
        assert tool.implementation_type == "builtin"
        assert tool.implementation_config == {"handler": "http_request"}

    def test_convert_http_entry_to_implementation(self):
        """测试：HTTP 入口转换为实现配置"""
        yaml_content = """
name: external_api
description: 调用外部API
category: http
entry:
  type: http
  url: https://api.example.com/endpoint
  method: POST
  headers:
    Content-Type: application/json
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)
        tool = loader.to_tool_entity(config)

        assert tool.implementation_type == "http"
        assert tool.implementation_config["url"] == "https://api.example.com/endpoint"
        assert tool.implementation_config["method"] == "POST"
        assert tool.implementation_config["headers"]["Content-Type"] == "application/json"

    def test_convert_javascript_entry_to_implementation(self):
        """测试：JavaScript 入口转换为实现配置"""
        yaml_content = """
name: js_tool
description: JavaScript工具
category: custom
entry:
  type: javascript
  code: |
    function execute(input) {
      return { result: input.value * 2 };
    }
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)
        tool = loader.to_tool_entity(config)

        assert tool.implementation_type == "javascript"
        assert "code" in tool.implementation_config
        assert "function execute" in tool.implementation_config["code"]

    def test_convert_python_entry_to_implementation(self):
        """测试：Python 入口转换为实现配置"""
        yaml_content = """
name: python_tool
description: Python工具
category: custom
entry:
  type: python
  module: tools.my_tool
  function: execute
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)
        tool = loader.to_tool_entity(config)

        assert tool.implementation_type == "python"
        assert tool.implementation_config["module"] == "tools.my_tool"
        assert tool.implementation_config["function"] == "execute"


# =============================================================================
# 第五部分：批量加载测试
# =============================================================================


class TestToolConfigBatchLoading:
    """工具配置批量加载测试"""

    def test_load_from_directory(self, tmp_path):
        """测试：从目录加载所有工具配置"""
        # 创建多个 YAML 文件
        tool1 = """
name: tool_1
description: 工具1
category: http
entry:
  type: builtin
  handler: handler1
"""
        tool2 = """
name: tool_2
description: 工具2
category: file
entry:
  type: builtin
  handler: handler2
"""
        (tmp_path / "tool_1.yaml").write_text(tool1, encoding="utf-8")
        (tmp_path / "tool_2.yaml").write_text(tool2, encoding="utf-8")
        (tmp_path / "not_yaml.txt").write_text("not a yaml file", encoding="utf-8")

        loader = ToolConfigLoader()
        configs = loader.load_from_directory(str(tmp_path))

        assert len(configs) == 2
        names = [c.name for c in configs]
        assert "tool_1" in names
        assert "tool_2" in names

    def test_load_from_directory_with_yml_extension(self, tmp_path):
        """测试：支持 .yml 和 .yaml 扩展名"""
        tool1 = """
name: yaml_tool
description: YAML工具
category: custom
entry:
  type: builtin
  handler: handler
"""
        tool2 = """
name: yml_tool
description: YML工具
category: custom
entry:
  type: builtin
  handler: handler
"""
        (tmp_path / "tool.yaml").write_text(tool1, encoding="utf-8")
        (tmp_path / "tool2.yml").write_text(tool2, encoding="utf-8")

        loader = ToolConfigLoader()
        configs = loader.load_from_directory(str(tmp_path))

        assert len(configs) == 2
        names = [c.name for c in configs]
        assert "yaml_tool" in names
        assert "yml_tool" in names

    def test_load_from_directory_skip_invalid(self, tmp_path):
        """测试：跳过无效配置文件"""
        valid = """
name: valid_tool
description: 有效工具
category: custom
entry:
  type: builtin
  handler: handler
"""
        invalid = """
name: invalid_tool
# 缺少 description, category, entry
"""
        (tmp_path / "valid.yaml").write_text(valid, encoding="utf-8")
        (tmp_path / "invalid.yaml").write_text(invalid, encoding="utf-8")

        loader = ToolConfigLoader()
        configs, errors = loader.load_from_directory_with_errors(str(tmp_path))

        assert len(configs) == 1
        assert configs[0].name == "valid_tool"
        assert len(errors) == 1
        assert "invalid.yaml" in errors[0][0]

    def test_load_empty_directory(self, tmp_path):
        """测试：加载空目录"""
        loader = ToolConfigLoader()
        configs = loader.load_from_directory(str(tmp_path))

        assert len(configs) == 0


# =============================================================================
# 第六部分：配置导出测试
# =============================================================================


class TestToolConfigExport:
    """工具配置导出测试"""

    def test_export_tool_to_yaml(self):
        """测试：将 Tool 实体导出为 YAML"""
        tool = Tool(
            id="tool_abc123",
            name="test_tool",
            description="测试工具",
            category=ToolCategory.HTTP,
            status=ToolStatus.DRAFT,
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="请求URL",
                    required=True,
                )
            ],
            returns={"status_code": "number"},
            implementation_type="builtin",
            implementation_config={"handler": "test_handler"},
            author="test_author",
            tags=["test", "demo"],
            icon="🔧",
        )

        loader = ToolConfigLoader()
        yaml_output = loader.export_to_yaml(tool)

        # 验证输出是有效的 YAML
        parsed = yaml.safe_load(yaml_output)
        assert parsed["name"] == "test_tool"
        assert parsed["description"] == "测试工具"
        assert parsed["category"] == "http"
        assert parsed["version"] == "1.0.0"
        assert parsed["author"] == "test_author"
        assert parsed["tags"] == ["test", "demo"]
        assert parsed["icon"] == "🔧"
        assert parsed["entry"]["type"] == "builtin"
        assert parsed["entry"]["handler"] == "test_handler"
        assert len(parsed["parameters"]) == 1

    def test_export_and_reimport_roundtrip(self):
        """测试：导出再导入保持一致"""
        original_yaml = """
name: roundtrip_tool
description: 往返测试工具
category: ai
version: "2.0.0"
author: tester
tags:
  - test
  - roundtrip
shareable_scope: team
entry:
  type: http
  url: https://api.example.com
  method: POST
parameters:
  - name: input
    type: string
    description: 输入数据
    required: true
    default: ""
returns:
  output: string
"""
        loader = ToolConfigLoader()

        # 导入
        config1 = loader.parse_yaml(original_yaml)
        tool = loader.to_tool_entity(config1)

        # 导出
        exported_yaml = loader.export_to_yaml(tool, shareable_scope=ShareableScope.TEAM)

        # 再导入
        config2 = loader.parse_yaml(exported_yaml)

        # 验证一致性
        assert config2.name == config1.name
        assert config2.description == config1.description
        assert config2.category == config1.category
        assert config2.version == config1.version
        assert config2.author == config1.author
        assert config2.shareable_scope == ShareableScope.TEAM
        assert len(config2.parameters) == len(config1.parameters)


# =============================================================================
# 第七部分：边界情况测试
# =============================================================================


class TestToolConfigEdgeCases:
    """边界情况测试"""

    def test_unicode_content(self):
        """测试：Unicode 内容处理"""
        yaml_content = """
name: unicode_工具
description: 这是一个中文描述的工具🔧
category: custom
author: 测试作者
tags:
  - 中文标签
  - emoji🎉
entry:
  type: builtin
  handler: unicode_handler
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)

        assert config.name == "unicode_工具"
        assert "中文描述" in config.description
        assert "🔧" in config.description
        assert config.author == "测试作者"
        assert "emoji🎉" in config.tags

    def test_multiline_description(self):
        """测试：多行描述"""
        yaml_content = """
name: multiline_tool
description: |
  这是一个多行描述。
  第二行描述内容。
  第三行描述内容。
category: custom
entry:
  type: builtin
  handler: handler
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)

        assert "多行描述" in config.description
        assert "第二行" in config.description

    def test_empty_parameters(self):
        """测试：空参数列表"""
        yaml_content = """
name: no_params_tool
description: 无参数工具
category: custom
entry:
  type: builtin
  handler: handler
parameters: []
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)

        assert config.parameters == []

    def test_complex_returns_schema(self):
        """测试：复杂返回值 Schema"""
        yaml_content = """
name: complex_return_tool
description: 复杂返回值工具
category: custom
entry:
  type: builtin
  handler: handler
returns:
  data:
    type: object
    properties:
      items:
        type: array
        items:
          type: string
      count:
        type: number
  metadata:
    type: object
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)

        assert "data" in config.returns
        assert "metadata" in config.returns

    def test_version_as_number(self):
        """测试：版本号为数字时自动转换为字符串"""
        yaml_content = """
name: version_test
description: 版本测试
category: custom
version: 1.0
entry:
  type: builtin
  handler: handler
"""
        loader = ToolConfigLoader()
        config = loader.parse_yaml(yaml_content)

        # 应该转换为字符串
        assert isinstance(config.version, str)
