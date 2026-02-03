"""统一定义系统集成测试 - 真实场景验证

测试目标：
1. ToolEngine 和 NodeRegistry 共享统一定义
2. 统一验证逻辑在真实场景下工作
3. 统一执行路径正确桥接现有执行器
4. 迁移后的定义与原系统兼容
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

# =============================================================================
# 第一部分：真实场景 - NodeRegistry 与 UnifiedDefinitionRegistry 集成
# =============================================================================


class TestNodeRegistryIntegration:
    """NodeRegistry 集成测试"""

    def test_import_all_predefined_nodes(self):
        """测试：导入所有预定义节点到统一注册中心"""
        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinitionRegistry,
            import_from_node_registry,
        )

        node_registry = NodeRegistry()
        unified_registry = UnifiedDefinitionRegistry()

        # 导入所有节点
        import_from_node_registry(node_registry, unified_registry)

        # 验证所有 13 种节点类型都被导入
        expected_nodes = [
            "start",
            "end",
            "llm",
            "condition",
            "loop",
            "parallel",
            "api",
            "code",
            "mcp",
            "knowledge",
            "classify",
            "template",
            "generic",
        ]

        for node_name in expected_nodes:
            assert unified_registry.has(node_name), f"节点 {node_name} 应该被导入"
            definition = unified_registry.get(node_name)
            assert definition.kind == DefinitionKind.NODE

    def test_unified_definition_matches_node_registry_schema(self):
        """测试：统一定义与 NodeRegistry Schema 匹配"""
        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            UnifiedDefinitionRegistry,
            import_from_node_registry,
        )

        node_registry = NodeRegistry()
        unified_registry = UnifiedDefinitionRegistry()
        import_from_node_registry(node_registry, unified_registry)

        # 验证 LLM 节点参数
        llm_def = unified_registry.get("llm")
        assert llm_def is not None

        # 检查参数名称
        param_names = [p["name"] for p in llm_def.parameters]
        assert "model" in param_names
        assert "temperature" in param_names
        assert "user_prompt" in param_names

        # 检查默认值
        model_param = next(p for p in llm_def.parameters if p["name"] == "model")
        assert model_param.get("default") == "gpt-4"

    def test_validate_node_params_via_unified_validator(self):
        """测试：通过统一验证器验证节点参数"""
        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            UnifiedDefinitionRegistry,
            UnifiedValidator,
            import_from_node_registry,
        )

        node_registry = NodeRegistry()
        unified_registry = UnifiedDefinitionRegistry()
        import_from_node_registry(node_registry, unified_registry)

        validator = UnifiedValidator()
        llm_def = unified_registry.get("llm")

        # 有效参数
        result = validator.validate(llm_def, {"user_prompt": "分析这段代码"})
        assert result.is_valid is True
        assert result.validated_params["model"] == "gpt-4"  # 默认值填充

        # 无效参数（缺少必填）
        result = validator.validate(llm_def, {})
        assert result.is_valid is False

    def test_node_factory_and_unified_validator_consistency(self):
        """测试：NodeFactory 和 UnifiedValidator 验证结果一致"""
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType
        from src.domain.services.unified_definition import (
            UnifiedDefinitionRegistry,
            UnifiedValidator,
            import_from_node_registry,
        )

        node_registry = NodeRegistry()
        node_factory = NodeFactory(node_registry)
        unified_registry = UnifiedDefinitionRegistry()
        import_from_node_registry(node_registry, unified_registry)

        validator = UnifiedValidator()
        llm_def = unified_registry.get("llm")

        # 有效配置 - 两个系统都应该成功
        valid_config = {"user_prompt": "测试"}

        # NodeFactory 创建成功
        node = node_factory.create(NodeType.LLM, valid_config)
        assert node is not None

        # UnifiedValidator 验证成功
        result = validator.validate(llm_def, valid_config)
        assert result.is_valid is True


# =============================================================================
# 第二部分：真实场景 - ToolEngine 与 UnifiedDefinitionRegistry 集成
# =============================================================================


class TestToolEngineIntegration:
    """ToolEngine 集成测试"""

    def test_load_tools_and_convert_to_unified(self):
        """测试：加载工具并转换为统一定义"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinitionRegistry,
            convert_tool_to_unified,
        )

        # 使用真实的 tools 目录
        tools_dir = Path(__file__).parent.parent.parent / "tools"

        if not tools_dir.exists():
            pytest.skip("tools 目录不存在")

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        asyncio.get_event_loop().run_until_complete(engine.load())

        unified_registry = UnifiedDefinitionRegistry()

        # 转换所有工具
        for tool in engine.list_all():
            definition = convert_tool_to_unified(tool)
            unified_registry.register(definition)

        # 验证工具被导入
        assert unified_registry.has("http_request")
        assert unified_registry.has("llm_call")

        # 验证类型
        http_def = unified_registry.get("http_request")
        assert http_def.kind == DefinitionKind.TOOL
        assert http_def.category == "http"

    def test_validate_tool_params_via_unified_validator(self):
        """测试：通过统一验证器验证工具参数"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.unified_definition import (
            UnifiedDefinitionRegistry,
            UnifiedValidator,
            convert_tool_to_unified,
        )

        tools_dir = Path(__file__).parent.parent.parent / "tools"

        if not tools_dir.exists():
            pytest.skip("tools 目录不存在")

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        asyncio.get_event_loop().run_until_complete(engine.load())

        unified_registry = UnifiedDefinitionRegistry()
        for tool in engine.list_all():
            definition = convert_tool_to_unified(tool)
            unified_registry.register(definition)

        validator = UnifiedValidator()
        http_def = unified_registry.get("http_request")

        if http_def is None:
            pytest.skip("http_request 工具不存在")

        # 验证参数 - 提供所有必填参数
        result = validator.validate(http_def, {"url": "https://api.example.com", "method": "GET"})
        assert result.is_valid is True

    def test_tool_engine_validator_and_unified_validator_consistency(self):
        """测试：ToolEngine 验证器和 UnifiedValidator 结果一致"""
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.unified_definition import (
            UnifiedDefinitionRegistry,
            UnifiedValidator,
            convert_tool_to_unified,
        )

        tools_dir = Path(__file__).parent.parent.parent / "tools"

        if not tools_dir.exists():
            pytest.skip("tools 目录不存在")

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        asyncio.get_event_loop().run_until_complete(engine.load())

        unified_registry = UnifiedDefinitionRegistry()
        for tool in engine.list_all():
            definition = convert_tool_to_unified(tool)
            unified_registry.register(definition)

        # 测试 http_request 工具
        http_tool = engine.get("http_request")
        if http_tool is None:
            pytest.skip("http_request 工具不存在")

        http_def = unified_registry.get("http_request")
        validator = UnifiedValidator()

        # 有效参数
        valid_params = {"url": "https://api.example.com", "method": "GET"}

        # ToolEngine 验证
        engine_result = engine.validate_params("http_request", valid_params)

        # UnifiedValidator 验证
        unified_result = validator.validate(http_def, valid_params)

        # 两者结果应该一致
        assert engine_result.is_valid == unified_result.is_valid


# =============================================================================
# 第三部分：真实场景 - 统一执行路径
# =============================================================================


class TestUnifiedExecutionPath:
    """统一执行路径测试"""

    @pytest.mark.asyncio
    async def test_execute_node_via_unified_adapter(self):
        """测试：通过统一适配器执行节点"""
        from unittest.mock import AsyncMock

        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            UnifiedDefinitionRegistry,
            UnifiedExecutorAdapter,
            UnifiedValidator,
            import_from_node_registry,
        )

        # 设置注册中心
        node_registry = NodeRegistry()
        unified_registry = UnifiedDefinitionRegistry()
        import_from_node_registry(node_registry, unified_registry)

        # 创建执行器适配器
        adapter = UnifiedExecutorAdapter()

        # 注册 mock LLM 执行器
        mock_llm_executor = AsyncMock()
        mock_llm_executor.execute.return_value = {
            "content": "这是 LLM 的回复",
            "tokens_used": 100,
        }
        adapter.register_executor("llm", mock_llm_executor)

        # 获取 LLM 定义
        llm_def = unified_registry.get("llm")

        # 验证参数
        validator = UnifiedValidator()
        params = {"user_prompt": "你好"}
        validation_result = validator.validate(llm_def, params)
        assert validation_result.is_valid is True

        # 执行
        result = await adapter.execute(
            definition=llm_def,
            params=validation_result.validated_params,
            context={},
        )

        assert result["content"] == "这是 LLM 的回复"
        mock_llm_executor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_via_unified_adapter(self):
        """测试：通过统一适配器执行工具"""
        from unittest.mock import AsyncMock

        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedExecutorAdapter,
            UnifiedValidator,
        )

        # 创建工具定义
        http_def = UnifiedDefinition(
            name="http_request",
            kind=DefinitionKind.TOOL,
            description="HTTP 请求",
            version="1.0.0",
            category="http",
            parameters=[
                {"name": "url", "type": "string", "required": True, "description": "URL"},
                {
                    "name": "method",
                    "type": "string",
                    "required": False,
                    "default": "GET",
                    "description": "方法",
                },
            ],
            executor_type="http",
        )

        # 创建执行器适配器
        adapter = UnifiedExecutorAdapter()

        # 注册 mock HTTP 执行器
        mock_http_executor = AsyncMock()
        mock_http_executor.execute.return_value = {
            "status_code": 200,
            "body": {"data": "response"},
        }
        adapter.register_executor("http", mock_http_executor)

        # 验证参数
        validator = UnifiedValidator()
        params = {"url": "https://api.example.com"}
        validation_result = validator.validate(http_def, params)
        assert validation_result.is_valid is True

        # 执行
        result = await adapter.execute(
            definition=http_def,
            params=validation_result.validated_params,
            context={},
        )

        assert result["status_code"] == 200
        mock_http_executor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_unified_execution_with_real_echo_executor(self):
        """测试：使用真实 Echo 执行器的统一执行"""
        from src.domain.services.tool_executor import EchoExecutor
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedExecutorAdapter,
            UnifiedValidator,
        )

        # 创建 echo 工具定义
        echo_def = UnifiedDefinition(
            name="echo",
            kind=DefinitionKind.TOOL,
            description="Echo 工具",
            version="1.0.0",
            parameters=[
                {"name": "message", "type": "string", "required": True, "description": "消息"},
            ],
            executor_type="echo",
        )

        # 创建适配器并注册真实执行器
        adapter = UnifiedExecutorAdapter()

        # 包装 EchoExecutor 以适配统一接口
        class EchoExecutorWrapper:
            def __init__(self):
                self._executor = EchoExecutor()

            async def execute(self, definition, params, context):
                return await self._executor.execute(None, params, context)

        adapter.register_executor("echo", EchoExecutorWrapper())

        # 验证并执行
        validator = UnifiedValidator()
        params = {"message": "Hello, World!"}
        validation_result = validator.validate(echo_def, params)
        assert validation_result.is_valid is True

        result = await adapter.execute(
            definition=echo_def,
            params=validation_result.validated_params,
            context={},
        )

        assert result["echoed"] == "Hello, World!"


# =============================================================================
# 第四部分：真实场景 - 混合节点和工具
# =============================================================================


class TestMixedNodeAndToolScenarios:
    """混合节点和工具场景测试"""

    def test_unified_registry_contains_both_nodes_and_tools(self):
        """测试：统一注册中心同时包含节点和工具"""
        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinitionRegistry,
            convert_tool_to_unified,
            import_from_node_registry,
        )

        unified_registry = UnifiedDefinitionRegistry()

        # 导入节点
        node_registry = NodeRegistry()
        import_from_node_registry(node_registry, unified_registry)

        # 导入工具
        tools_dir = Path(__file__).parent.parent.parent / "tools"
        if tools_dir.exists():
            config = ToolEngineConfig(tools_directory=str(tools_dir))
            engine = ToolEngine(config)
            asyncio.get_event_loop().run_until_complete(engine.load())

            for tool in engine.list_all():
                definition = convert_tool_to_unified(tool)
                # 避免名称冲突，工具名加前缀
                if unified_registry.has(definition.name):
                    definition.name = f"tool_{definition.name}"
                unified_registry.register(definition)

        # 验证两种类型都存在
        nodes = unified_registry.list_by_kind(DefinitionKind.NODE)

        assert len(nodes) >= 13  # 至少 13 个预定义节点
        # 工具数量取决于 tools 目录是否存在

    def test_search_across_nodes_and_tools(self):
        """测试：跨节点和工具搜索"""
        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
            import_from_node_registry,
        )

        unified_registry = UnifiedDefinitionRegistry()

        # 导入节点
        node_registry = NodeRegistry()
        import_from_node_registry(node_registry, unified_registry)

        # 添加带标签的工具
        http_tool = UnifiedDefinition(
            name="http_tool",
            kind=DefinitionKind.TOOL,
            description="HTTP 工具",
            version="1.0.0",
            category="http",
            parameters=[],
            executor_type="http",
            tags=["http", "api", "network"],
        )
        unified_registry.register(http_tool)

        # 按分类搜索
        http_items = unified_registry.list_by_category("http")
        assert len(http_items) >= 1

        # 按标签搜索
        api_items = unified_registry.search_by_tag("api")
        assert len(api_items) >= 1

    def test_validate_mixed_workflow_params(self):
        """测试：验证混合工作流参数"""
        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
            UnifiedValidator,
            import_from_node_registry,
        )

        unified_registry = UnifiedDefinitionRegistry()

        # 导入节点
        node_registry = NodeRegistry()
        import_from_node_registry(node_registry, unified_registry)

        # 添加工具
        http_tool = UnifiedDefinition(
            name="http_tool",
            kind=DefinitionKind.TOOL,
            description="HTTP 工具",
            version="1.0.0",
            parameters=[
                {"name": "url", "type": "string", "required": True, "description": "URL"},
            ],
            executor_type="http",
        )
        unified_registry.register(http_tool)

        validator = UnifiedValidator()

        # 模拟工作流：LLM 节点 -> HTTP 工具
        # 1. 验证 LLM 节点参数
        llm_def = unified_registry.get("llm")
        llm_result = validator.validate(llm_def, {"user_prompt": "生成 API 请求"})
        assert llm_result.is_valid is True

        # 2. 验证 HTTP 工具参数
        http_def = unified_registry.get("http_tool")
        http_result = validator.validate(http_def, {"url": "https://api.example.com"})
        assert http_result.is_valid is True


# =============================================================================
# 第五部分：真实场景 - YAML 定义加载
# =============================================================================


class TestYAMLDefinitionLoading:
    """YAML 定义加载测试"""

    def test_load_unified_definitions_from_yaml_directory(self):
        """测试：从 YAML 目录加载统一定义"""
        from src.domain.services.unified_definition import (
            UnifiedDefinitionRegistry,
            UnifiedYAMLLoader,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 创建节点定义
            node_yaml = """
name: custom_llm
kind: node
description: 自定义 LLM 节点
version: "1.0.0"
parameters:
  - name: prompt
    type: string
    description: 提示词
    required: true
  - name: model
    type: string
    description: 模型
    required: false
    default: "gpt-4"
executor_type: llm
"""
            Path(tmp_dir, "custom_llm.yaml").write_text(node_yaml, encoding="utf-8")

            # 创建工具定义
            tool_yaml = """
name: custom_http
kind: tool
description: 自定义 HTTP 工具
version: "1.0.0"
category: http
parameters:
  - name: url
    type: string
    description: URL
    required: true
  - name: method
    type: string
    description: 方法
    required: false
    default: "GET"
    enum: ["GET", "POST", "PUT", "DELETE"]
executor_type: http
tags:
  - http
  - api
"""
            Path(tmp_dir, "custom_http.yaml").write_text(tool_yaml, encoding="utf-8")

            # 加载定义
            loader = UnifiedYAMLLoader()
            definitions = loader.load_from_directory(tmp_dir)

            # 注册到统一注册中心
            registry = UnifiedDefinitionRegistry()
            for definition in definitions:
                registry.register(definition)

            # 验证
            assert registry.has("custom_llm")
            assert registry.has("custom_http")

            custom_llm = registry.get("custom_llm")
            assert custom_llm.kind.value == "node"

            custom_http = registry.get("custom_http")
            assert custom_http.kind.value == "tool"
            assert custom_http.category == "http"

    def test_yaml_definitions_work_with_validator(self):
        """测试：YAML 定义与验证器配合工作"""
        from src.domain.services.unified_definition import (
            UnifiedValidator,
            UnifiedYAMLLoader,
        )

        yaml_content = """
name: validated_tool
kind: tool
description: 需要验证的工具
version: "1.0.0"
parameters:
  - name: count
    type: number
    description: 数量
    required: true
    constraints:
      min: 1
      max: 100
  - name: status
    type: string
    description: 状态
    required: true
    enum: ["active", "inactive"]
executor_type: test
"""
        loader = UnifiedYAMLLoader()
        definition = loader.parse(yaml_content)

        validator = UnifiedValidator()

        # 有效参数
        result = validator.validate(definition, {"count": 50, "status": "active"})
        assert result.is_valid is True

        # 无效参数 - 超出范围
        result = validator.validate(definition, {"count": 200, "status": "active"})
        assert result.is_valid is False

        # 无效参数 - 枚举错误
        result = validator.validate(definition, {"count": 50, "status": "unknown"})
        assert result.is_valid is False


# =============================================================================
# 第六部分：端到端场景测试
# =============================================================================


class TestEndToEndScenarios:
    """端到端场景测试"""

    @pytest.mark.asyncio
    async def test_complete_workflow_with_unified_system(self):
        """测试：使用统一系统的完整工作流"""
        from unittest.mock import AsyncMock

        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
            UnifiedExecutorAdapter,
            UnifiedValidator,
            import_from_node_registry,
        )

        # 1. 设置统一注册中心
        unified_registry = UnifiedDefinitionRegistry()

        # 导入节点
        node_registry = NodeRegistry()
        import_from_node_registry(node_registry, unified_registry)

        # 添加自定义工具
        http_tool = UnifiedDefinition(
            name="api_call",
            kind=DefinitionKind.TOOL,
            description="API 调用工具",
            version="1.0.0",
            category="http",
            parameters=[
                {"name": "endpoint", "type": "string", "required": True, "description": "端点"},
            ],
            executor_type="http",
        )
        unified_registry.register(http_tool)

        # 2. 设置执行器
        adapter = UnifiedExecutorAdapter()

        mock_llm = AsyncMock()
        mock_llm.execute.return_value = {"content": "生成的内容", "tokens_used": 50}
        adapter.register_executor("llm", mock_llm)

        mock_http = AsyncMock()
        mock_http.execute.return_value = {"status_code": 200, "body": {"success": True}}
        adapter.register_executor("http", mock_http)

        # 3. 模拟工作流执行
        validator = UnifiedValidator()
        workflow_results = []

        # Step 1: LLM 节点
        llm_def = unified_registry.get("llm")
        llm_params = {"user_prompt": "生成 API 请求参数"}
        llm_validation = validator.validate(llm_def, llm_params)
        assert llm_validation.is_valid is True

        llm_result = await adapter.execute(llm_def, llm_validation.validated_params, {})
        workflow_results.append(("llm", llm_result))

        # Step 2: HTTP 工具
        http_def = unified_registry.get("api_call")
        http_params = {"endpoint": "/api/data"}
        http_validation = validator.validate(http_def, http_params)
        assert http_validation.is_valid is True

        http_result = await adapter.execute(http_def, http_validation.validated_params, {})
        workflow_results.append(("http", http_result))

        # 4. 验证结果
        assert len(workflow_results) == 2
        assert workflow_results[0][0] == "llm"
        assert workflow_results[0][1]["content"] == "生成的内容"
        assert workflow_results[1][0] == "http"
        assert workflow_results[1][1]["status_code"] == 200

    def test_unified_system_statistics(self):
        """测试：统一系统统计信息"""
        from src.domain.services.node_registry import NodeRegistry
        from src.domain.services.unified_definition import (
            DefinitionKind,
            UnifiedDefinition,
            UnifiedDefinitionRegistry,
            import_from_node_registry,
        )

        unified_registry = UnifiedDefinitionRegistry()

        # 导入节点
        node_registry = NodeRegistry()
        import_from_node_registry(node_registry, unified_registry)

        # 添加工具
        for i in range(5):
            tool = UnifiedDefinition(
                name=f"tool_{i}",
                kind=DefinitionKind.TOOL,
                description=f"工具 {i}",
                version="1.0.0",
                category="custom" if i % 2 == 0 else "http",
                parameters=[],
                executor_type="test",
                tags=["test", f"tag_{i}"],
            )
            unified_registry.register(tool)

        # 统计
        all_defs = unified_registry.list_all()
        nodes = unified_registry.list_by_kind(DefinitionKind.NODE)
        tools = unified_registry.list_by_kind(DefinitionKind.TOOL)
        custom_tools = unified_registry.list_by_category("custom")
        http_tools = unified_registry.list_by_category("http")

        # 节点数量以 NodeRegistry 对外暴露的类型为准（避免新增/隐藏节点类型导致测试脆弱）。
        expected_node_count = len(node_registry.get_all_types())
        assert len(all_defs) == expected_node_count + 5
        assert len(nodes) == expected_node_count
        assert len(tools) == 5
        assert len(custom_tools) == 3  # tool_0, tool_2, tool_4
        assert len(http_tools) == 2  # tool_1, tool_3
