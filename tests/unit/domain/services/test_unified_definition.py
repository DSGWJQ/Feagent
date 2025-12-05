"""统一定义系统测试 - ToolEngine 与 NodeRegistry 打通

测试目标：
1. 统一 Schema 格式 (UnifiedDefinition)
2. 统一注册中心 (UnifiedDefinitionRegistry)
3. 统一验证器 (UnifiedValidator)
4. 统一执行路径 (UnifiedExecutor)
5. 节点/工具定义迁移

设计原则：
- TDD 驱动开发
- 向后兼容现有 NodeRegistry 和 ToolEngine
- 共享 Schema、验证逻辑、执行器
"""

import pytest

# =============================================================================
# 第一部分：统一定义 Schema 测试
# =============================================================================


class TestUnifiedDefinitionSchema:
    """统一定义 Schema 测试"""

    def test_create_unified_definition_from_node_type(self):
        """测试：从节点类型创建统一定义"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
        )

        # 创建 LLM 节点的统一定义
        definition = UnifiedDefinition(
            name="llm",
            kind=DefinitionKind.NODE,
            description="大语言模型调用节点",
            version="1.0.0",
            parameters=[
                {
                    "name": "model",
                    "type": "string",
                    "description": "模型名称",
                    "required": False,
                    "default": "gpt-4",
                },
                {
                    "name": "temperature",
                    "type": "number",
                    "description": "温度参数",
                    "required": False,
                    "default": 0.7,
                },
                {
                    "name": "user_prompt",
                    "type": "string",
                    "description": "用户提示词",
                    "required": True,
                },
            ],
            returns={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "tokens_used": {"type": "integer"},
                },
            },
            executor_type="llm",
        )

        assert definition.name == "llm"
        assert definition.kind == DefinitionKind.NODE
        assert len(definition.parameters) == 3
        assert definition.executor_type == "llm"

    def test_create_unified_definition_from_tool(self):
        """测试：从工具创建统一定义"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
        )

        # 创建 HTTP 工具的统一定义
        definition = UnifiedDefinition(
            name="http_request",
            kind=DefinitionKind.TOOL,
            description="HTTP 请求工具",
            version="1.0.0",
            category="http",
            parameters=[
                {
                    "name": "url",
                    "type": "string",
                    "description": "请求 URL",
                    "required": True,
                },
                {
                    "name": "method",
                    "type": "string",
                    "description": "HTTP 方法",
                    "required": False,
                    "default": "GET",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                },
            ],
            returns={
                "type": "object",
                "properties": {
                    "status_code": {"type": "integer"},
                    "body": {"type": "object"},
                },
            },
            executor_type="http",
            tags=["http", "api"],
        )

        assert definition.name == "http_request"
        assert definition.kind == DefinitionKind.TOOL
        assert definition.category == "http"
        assert "http" in definition.tags

    def test_unified_definition_to_dict(self):
        """测试：统一定义序列化为字典"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
        )

        definition = UnifiedDefinition(
            name="test_def",
            kind=DefinitionKind.NODE,
            description="测试定义",
            version="1.0.0",
            parameters=[],
            executor_type="test",
        )

        data = definition.to_dict()

        assert data["name"] == "test_def"
        assert data["kind"] == "node"
        assert data["version"] == "1.0.0"

    def test_unified_definition_from_dict(self):
        """测试：从字典反序列化统一定义"""
        from src.domain.services.unified_definition import UnifiedDefinition

        data = {
            "name": "test_def",
            "kind": "tool",
            "description": "测试定义",
            "version": "2.0.0",
            "parameters": [
                {"name": "input", "type": "string", "required": True, "description": "输入"}
            ],
            "executor_type": "test",
        }

        definition = UnifiedDefinition.from_dict(data)

        assert definition.name == "test_def"
        assert definition.version == "2.0.0"
        assert len(definition.parameters) == 1

    def test_unified_parameter_with_constraints(self):
        """测试：带约束的统一参数"""
        from src.domain.services.unified_definition import UnifiedParameter

        param = UnifiedParameter(
            name="temperature",
            type="number",
            description="温度参数",
            required=False,
            default=0.7,
            constraints={"min": 0.0, "max": 2.0},
        )

        assert param.name == "temperature"
        assert param.constraints["min"] == 0.0
        assert param.constraints["max"] == 2.0

    def test_unified_parameter_with_enum(self):
        """测试：带枚举的统一参数"""
        from src.domain.services.unified_definition import UnifiedParameter

        param = UnifiedParameter(
            name="method",
            type="string",
            description="HTTP 方法",
            required=False,
            default="GET",
            enum=["GET", "POST", "PUT", "DELETE"],
        )

        assert param.enum == ["GET", "POST", "PUT", "DELETE"]


# =============================================================================
# 第二部分：统一注册中心测试
# =============================================================================


class TestUnifiedDefinitionRegistry:
    """统一注册中心测试"""

    def test_register_definition(self):
        """测试：注册定义"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
        )

        registry = UnifiedDefinitionRegistry()

        definition = UnifiedDefinition(
            name="test_node",
            kind=DefinitionKind.NODE,
            description="测试节点",
            version="1.0.0",
            parameters=[],
            executor_type="test",
        )

        registry.register(definition)

        assert registry.has("test_node")
        assert registry.get("test_node") == definition

    def test_register_duplicate_raises_error(self):
        """测试：重复注册抛出错误"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
        )

        registry = UnifiedDefinitionRegistry()

        definition = UnifiedDefinition(
            name="duplicate",
            kind=DefinitionKind.NODE,
            description="重复定义",
            version="1.0.0",
            parameters=[],
            executor_type="test",
        )

        registry.register(definition)

        with pytest.raises(ValueError, match="已存在"):
            registry.register(definition)

    def test_register_with_overwrite(self):
        """测试：覆盖注册"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
        )

        registry = UnifiedDefinitionRegistry()

        definition_v1 = UnifiedDefinition(
            name="versioned",
            kind=DefinitionKind.NODE,
            description="版本1",
            version="1.0.0",
            parameters=[],
            executor_type="test",
        )

        definition_v2 = UnifiedDefinition(
            name="versioned",
            kind=DefinitionKind.NODE,
            description="版本2",
            version="2.0.0",
            parameters=[],
            executor_type="test",
        )

        registry.register(definition_v1)
        registry.register(definition_v2, overwrite=True)

        assert registry.get("versioned").version == "2.0.0"

    def test_list_by_kind(self):
        """测试：按类型列出定义"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
        )

        registry = UnifiedDefinitionRegistry()

        node_def = UnifiedDefinition(
            name="node1",
            kind=DefinitionKind.NODE,
            description="节点",
            version="1.0.0",
            parameters=[],
            executor_type="test",
        )

        tool_def = UnifiedDefinition(
            name="tool1",
            kind=DefinitionKind.TOOL,
            description="工具",
            version="1.0.0",
            parameters=[],
            executor_type="test",
        )

        registry.register(node_def)
        registry.register(tool_def)

        nodes = registry.list_by_kind(DefinitionKind.NODE)
        tools = registry.list_by_kind(DefinitionKind.TOOL)

        assert len(nodes) == 1
        assert len(tools) == 1
        assert nodes[0].name == "node1"
        assert tools[0].name == "tool1"

    def test_list_by_category(self):
        """测试：按分类列出定义"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
        )

        registry = UnifiedDefinitionRegistry()

        http_tool = UnifiedDefinition(
            name="http_request",
            kind=DefinitionKind.TOOL,
            description="HTTP 工具",
            version="1.0.0",
            category="http",
            parameters=[],
            executor_type="http",
        )

        ai_tool = UnifiedDefinition(
            name="llm_call",
            kind=DefinitionKind.TOOL,
            description="LLM 工具",
            version="1.0.0",
            category="ai",
            parameters=[],
            executor_type="llm",
        )

        registry.register(http_tool)
        registry.register(ai_tool)

        http_tools = registry.list_by_category("http")
        ai_tools = registry.list_by_category("ai")

        assert len(http_tools) == 1
        assert len(ai_tools) == 1

    def test_search_by_tag(self):
        """测试：按标签搜索"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
        )

        registry = UnifiedDefinitionRegistry()

        definition = UnifiedDefinition(
            name="tagged_tool",
            kind=DefinitionKind.TOOL,
            description="带标签的工具",
            version="1.0.0",
            parameters=[],
            executor_type="test",
            tags=["api", "http", "rest"],
        )

        registry.register(definition)

        results = registry.search_by_tag("api")
        assert len(results) == 1
        assert results[0].name == "tagged_tool"

    def test_get_nonexistent_returns_none(self):
        """测试：获取不存在的定义返回 None"""
        from src.domain.services.unified_definition import UnifiedDefinitionRegistry

        registry = UnifiedDefinitionRegistry()
        assert registry.get("nonexistent") is None


# =============================================================================
# 第三部分：统一验证器测试
# =============================================================================


class TestUnifiedValidator:
    """统一验证器测试"""

    def test_validate_required_parameter(self):
        """测试：验证必填参数"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedValidator,
        )

        definition = UnifiedDefinition(
            name="test",
            kind=DefinitionKind.NODE,
            description="测试",
            version="1.0.0",
            parameters=[
                {
                    "name": "required_param",
                    "type": "string",
                    "required": True,
                    "description": "必填",
                }
            ],
            executor_type="test",
        )

        validator = UnifiedValidator()

        # 缺少必填参数
        result = validator.validate(definition, {})
        assert result.is_valid is False
        assert any("required_param" in str(e) for e in result.errors)

        # 提供必填参数
        result = validator.validate(definition, {"required_param": "value"})
        assert result.is_valid is True

    def test_validate_type_mismatch(self):
        """测试：验证类型不匹配"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedValidator,
        )

        definition = UnifiedDefinition(
            name="test",
            kind=DefinitionKind.NODE,
            description="测试",
            version="1.0.0",
            parameters=[
                {"name": "number_param", "type": "number", "required": True, "description": "数字"}
            ],
            executor_type="test",
        )

        validator = UnifiedValidator()

        # 类型错误
        result = validator.validate(definition, {"number_param": "not_a_number"})
        assert result.is_valid is False
        assert any("类型" in str(e) or "type" in str(e).lower() for e in result.errors)

        # 类型正确
        result = validator.validate(definition, {"number_param": 42})
        assert result.is_valid is True

    def test_validate_enum_constraint(self):
        """测试：验证枚举约束"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedValidator,
        )

        definition = UnifiedDefinition(
            name="test",
            kind=DefinitionKind.NODE,
            description="测试",
            version="1.0.0",
            parameters=[
                {
                    "name": "method",
                    "type": "string",
                    "required": True,
                    "description": "方法",
                    "enum": ["GET", "POST"],
                }
            ],
            executor_type="test",
        )

        validator = UnifiedValidator()

        # 枚举值无效
        result = validator.validate(definition, {"method": "INVALID"})
        assert result.is_valid is False

        # 枚举值有效
        result = validator.validate(definition, {"method": "GET"})
        assert result.is_valid is True

    def test_validate_range_constraint(self):
        """测试：验证范围约束"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedValidator,
        )

        definition = UnifiedDefinition(
            name="test",
            kind=DefinitionKind.NODE,
            description="测试",
            version="1.0.0",
            parameters=[
                {
                    "name": "temperature",
                    "type": "number",
                    "required": True,
                    "description": "温度",
                    "constraints": {"min": 0.0, "max": 2.0},
                }
            ],
            executor_type="test",
        )

        validator = UnifiedValidator()

        # 超出范围
        result = validator.validate(definition, {"temperature": 3.0})
        assert result.is_valid is False

        # 在范围内
        result = validator.validate(definition, {"temperature": 0.7})
        assert result.is_valid is True

    def test_validate_fills_default_values(self):
        """测试：验证时填充默认值"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedValidator,
        )

        definition = UnifiedDefinition(
            name="test",
            kind=DefinitionKind.NODE,
            description="测试",
            version="1.0.0",
            parameters=[
                {
                    "name": "with_default",
                    "type": "string",
                    "required": False,
                    "description": "有默认值",
                    "default": "default_value",
                }
            ],
            executor_type="test",
        )

        validator = UnifiedValidator()

        result = validator.validate(definition, {})
        assert result.is_valid is True
        assert result.validated_params["with_default"] == "default_value"

    def test_validate_strict_mode_extra_params(self):
        """测试：严格模式检测多余参数"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedValidator,
        )

        definition = UnifiedDefinition(
            name="test",
            kind=DefinitionKind.NODE,
            description="测试",
            version="1.0.0",
            parameters=[
                {"name": "known_param", "type": "string", "required": False, "description": "已知"}
            ],
            executor_type="test",
        )

        validator = UnifiedValidator(strict_mode=True)

        result = validator.validate(definition, {"known_param": "value", "extra_param": "extra"})
        assert result.is_valid is False
        assert any("extra_param" in str(e) for e in result.errors)


# =============================================================================
# 第四部分：从现有系统转换测试
# =============================================================================


class TestConversionFromExistingSystems:
    """从现有系统转换测试"""

    def test_convert_from_node_registry_schema(self):
        """测试：从 NodeRegistry Schema 转换"""
        from src.domain.services.node_registry import PREDEFINED_SCHEMAS, NodeType
        from src.domain.services.unified_definition import (
            convert_node_schema_to_unified,
        )

        # 转换 LLM 节点
        llm_schema = PREDEFINED_SCHEMAS[NodeType.LLM]
        definition = convert_node_schema_to_unified(
            node_type=NodeType.LLM,
            schema=llm_schema,
            description="大语言模型调用节点",
        )

        assert definition.name == "llm"
        assert definition.kind.value == "node"
        assert any(p["name"] == "user_prompt" for p in definition.parameters)

    def test_convert_from_tool_entity(self):
        """测试：从 Tool 实体转换"""
        from src.domain.entities.tool import Tool, ToolParameter
        from src.domain.services.unified_definition import (
            convert_tool_to_unified,
        )
        from src.domain.value_objects.tool_category import ToolCategory

        tool = Tool(
            id="tool_123",
            name="http_request",
            description="HTTP 请求工具",
            category=ToolCategory.HTTP,
            status="active",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="请求 URL",
                    required=True,
                ),
                ToolParameter(
                    name="method",
                    type="string",
                    description="HTTP 方法",
                    required=False,
                    default="GET",
                    enum=["GET", "POST", "PUT", "DELETE"],
                ),
            ],
            implementation_type="http",
            implementation_config={"timeout": 30},
        )

        definition = convert_tool_to_unified(tool)

        assert definition.name == "http_request"
        assert definition.kind.value == "tool"
        assert definition.category == "http"
        assert len(definition.parameters) == 2

    def test_convert_from_node_schema_registry(self):
        """测试：从 NodeSchemaRegistry 转换"""
        from src.domain.services.node_schema import NodeSchemaRegistry
        from src.domain.services.unified_definition import (
            convert_node_schema_registry_to_unified,
        )

        node_registry = NodeSchemaRegistry()
        definitions = convert_node_schema_registry_to_unified(node_registry)

        # 应该有 13 个预定义节点
        assert len(definitions) >= 13

        # 验证 LLM 节点存在
        llm_def = next((d for d in definitions if d.name == "llm"), None)
        assert llm_def is not None


# =============================================================================
# 第五部分：统一执行器适配器测试
# =============================================================================


class TestUnifiedExecutorAdapter:
    """统一执行器适配器测试"""

    @pytest.mark.asyncio
    async def test_execute_node_via_unified_executor(self):
        """测试：通过统一执行器执行节点"""
        from unittest.mock import AsyncMock

        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedExecutorAdapter,
        )

        # 创建定义
        definition = UnifiedDefinition(
            name="test_node",
            kind=DefinitionKind.NODE,
            description="测试节点",
            version="1.0.0",
            parameters=[
                {"name": "input", "type": "string", "required": True, "description": "输入"}
            ],
            executor_type="test",
        )

        # 创建 mock 执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"result": "success"}

        # 创建适配器
        adapter = UnifiedExecutorAdapter()
        adapter.register_executor("test", mock_executor)

        # 执行
        result = await adapter.execute(
            definition=definition,
            params={"input": "test_value"},
            context={},
        )

        assert result["result"] == "success"
        mock_executor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_via_unified_executor(self):
        """测试：通过统一执行器执行工具"""
        from unittest.mock import AsyncMock

        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedExecutorAdapter,
        )

        # 创建定义
        definition = UnifiedDefinition(
            name="http_request",
            kind=DefinitionKind.TOOL,
            description="HTTP 请求",
            version="1.0.0",
            category="http",
            parameters=[{"name": "url", "type": "string", "required": True, "description": "URL"}],
            executor_type="http",
        )

        # 创建 mock 执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"status_code": 200, "body": {}}

        # 创建适配器
        adapter = UnifiedExecutorAdapter()
        adapter.register_executor("http", mock_executor)

        # 执行
        result = await adapter.execute(
            definition=definition,
            params={"url": "https://api.example.com"},
            context={},
        )

        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_executor_not_found_raises_error(self):
        """测试：执行器未找到抛出错误"""
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedExecutorAdapter,
        )

        definition = UnifiedDefinition(
            name="unknown",
            kind=DefinitionKind.NODE,
            description="未知",
            version="1.0.0",
            parameters=[],
            executor_type="nonexistent",
        )

        adapter = UnifiedExecutorAdapter()

        with pytest.raises(ValueError, match="执行器"):
            await adapter.execute(definition=definition, params={}, context={})


# =============================================================================
# 第六部分：向后兼容性测试
# =============================================================================


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_node_registry_still_works(self):
        """测试：NodeRegistry 仍然正常工作"""
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 创建节点
        node = factory.create(NodeType.LLM, {"user_prompt": "测试"})

        assert node.type == NodeType.LLM
        assert node.config["user_prompt"] == "测试"
        assert node.config["model"] == "gpt-4"  # 默认值

    def test_tool_engine_still_works(self):
        """测试：ToolEngine 仍然正常工作"""
        import tempfile
        from pathlib import Path

        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig

        # 创建临时工具目录
        with tempfile.TemporaryDirectory() as tmp_dir:
            tool_yaml = """
name: test_tool
version: "1.0.0"
description: 测试工具
category: custom
parameters:
  - name: input
    type: string
    description: 输入
    required: true
entry:
  type: builtin
  handler: test
"""
            Path(tmp_dir, "test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

            config = ToolEngineConfig(tools_directory=tmp_dir)
            engine = ToolEngine(config)

            # 同步加载（测试用）
            import asyncio

            asyncio.get_event_loop().run_until_complete(engine.load())

            assert engine.tool_count == 1
            assert engine.get("test_tool") is not None

    def test_unified_registry_integrates_with_node_registry(self):
        """测试：统一注册中心与 NodeRegistry 集成"""
        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            UnifiedDefinitionRegistry,
            import_from_node_registry,
        )

        node_registry = NodeRegistry()
        unified_registry = UnifiedDefinitionRegistry()

        # 导入节点定义
        import_from_node_registry(node_registry, unified_registry)

        # 验证所有节点类型都被导入
        assert unified_registry.has("llm")
        assert unified_registry.has("api")
        assert unified_registry.has("code")
        assert unified_registry.has("condition")


# =============================================================================
# 第七部分：YAML 定义加载测试
# =============================================================================


class TestUnifiedYAMLLoader:
    """统一 YAML 加载器测试"""

    def test_load_unified_definition_from_yaml(self):
        """测试：从 YAML 加载统一定义"""
        from src.domain.services.unified_definition import UnifiedYAMLLoader

        yaml_content = """
name: custom_tool
kind: tool
description: 自定义工具
version: "1.0.0"
category: custom
parameters:
  - name: input
    type: string
    description: 输入参数
    required: true
  - name: option
    type: string
    description: 可选参数
    required: false
    default: "default"
    enum: ["option1", "option2", "default"]
returns:
  type: object
  properties:
    result:
      type: string
executor_type: custom
tags:
  - custom
  - test
"""
        loader = UnifiedYAMLLoader()
        definition = loader.parse(yaml_content)

        assert definition.name == "custom_tool"
        assert definition.kind.value == "tool"
        assert len(definition.parameters) == 2
        assert definition.tags == ["custom", "test"]

    def test_load_node_definition_from_yaml(self):
        """测试：从 YAML 加载节点定义"""
        from src.domain.services.unified_definition import UnifiedYAMLLoader

        yaml_content = """
name: custom_node
kind: node
description: 自定义节点
version: "1.0.0"
parameters:
  - name: config
    type: object
    description: 配置
    required: true
returns:
  type: object
  properties:
    output:
      type: string
executor_type: custom_node
allowed_child_types:
  - llm
  - api
"""
        loader = UnifiedYAMLLoader()
        definition = loader.parse(yaml_content)

        assert definition.name == "custom_node"
        assert definition.kind.value == "node"
        assert definition.allowed_child_types == ["llm", "api"]

    def test_load_from_directory(self):
        """测试：从目录加载所有定义"""
        import tempfile
        from pathlib import Path

        from src.domain.services.unified_definition import UnifiedYAMLLoader

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 创建多个定义文件
            tool1 = """
name: tool1
kind: tool
description: 工具1
version: "1.0.0"
parameters: []
executor_type: test
"""
            tool2 = """
name: tool2
kind: tool
description: 工具2
version: "1.0.0"
parameters: []
executor_type: test
"""
            Path(tmp_dir, "tool1.yaml").write_text(tool1, encoding="utf-8")
            Path(tmp_dir, "tool2.yaml").write_text(tool2, encoding="utf-8")

            loader = UnifiedYAMLLoader()
            definitions = loader.load_from_directory(tmp_dir)

            assert len(definitions) == 2
            names = [d.name for d in definitions]
            assert "tool1" in names
            assert "tool2" in names
