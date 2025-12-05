"""ToolEngine 集成测试 - 阶段 2

测试目标：
1. 验证真实工具目录的加载
2. 验证热更新在真实场景下工作
3. 验证与 ToolConfigLoader 的集成
"""

import asyncio
import time
from pathlib import Path

import pytest

from src.domain.services.tool_engine import (
    ToolEngine,
    ToolEngineConfig,
    ToolEngineEvent,
    ToolEngineEventType,
)
from src.domain.value_objects.tool_category import ToolCategory

# =============================================================================
# 配置
# =============================================================================

# 项目根目录的 tools 目录
PROJECT_TOOLS_DIR = Path(__file__).parent.parent.parent / "tools"


# =============================================================================
# 真实工具目录测试
# =============================================================================


class TestToolEngineWithRealToolsDirectory:
    """使用真实 tools 目录的集成测试"""

    @pytest.mark.asyncio
    async def test_load_real_tools_directory(self):
        """测试：加载真实的 tools 目录"""
        config = ToolEngineConfig(tools_directory=str(PROJECT_TOOLS_DIR))
        engine = ToolEngine(config=config)

        await engine.load()

        assert engine.is_loaded is True
        assert engine.tool_count >= 5  # 至少有 5 个工具

        # 验证预期的工具存在
        expected_tools = [
            "http_request",
            "llm_call",
            "file_reader",
            "json_transformer",
            "text_analyzer",
        ]

        for name in expected_tools:
            tool = engine.get(name)
            assert tool is not None, f"工具 {name} 应该存在"

    @pytest.mark.asyncio
    async def test_find_http_tools(self):
        """测试：查找 HTTP 类别的工具"""
        config = ToolEngineConfig(tools_directory=str(PROJECT_TOOLS_DIR))
        engine = ToolEngine(config=config)
        await engine.load()

        http_tools = engine.find_by_category(ToolCategory.HTTP)

        assert len(http_tools) >= 1
        assert any(t.name == "http_request" for t in http_tools)

    @pytest.mark.asyncio
    async def test_find_ai_tools(self):
        """测试：查找 AI 类别的工具"""
        config = ToolEngineConfig(tools_directory=str(PROJECT_TOOLS_DIR))
        engine = ToolEngine(config=config)
        await engine.load()

        ai_tools = engine.find_by_category(ToolCategory.AI)

        assert len(ai_tools) >= 1
        assert any(t.name == "llm_call" for t in ai_tools)

    @pytest.mark.asyncio
    async def test_search_for_http(self):
        """测试：搜索包含 HTTP 的工具"""
        config = ToolEngineConfig(tools_directory=str(PROJECT_TOOLS_DIR))
        engine = ToolEngine(config=config)
        await engine.load()

        results = engine.search("HTTP")

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """测试：获取统计信息"""
        config = ToolEngineConfig(tools_directory=str(PROJECT_TOOLS_DIR))
        engine = ToolEngine(config=config)
        await engine.load()

        stats = engine.get_statistics()

        assert stats["total_tools"] >= 5
        assert stats["is_loaded"] is True
        assert stats["load_errors"] == 0
        assert "by_category" in stats


# =============================================================================
# 热更新真实场景测试
# =============================================================================


class TestToolEngineHotReloadIntegration:
    """热更新集成测试"""

    @pytest.mark.asyncio
    async def test_hot_reload_workflow(self, tmp_path):
        """测试：完整的热更新工作流"""
        # 1. 初始状态：创建一个工具
        initial_tool = """
name: workflow_tool
description: 工作流测试工具 v1
category: custom
version: "1.0.0"
entry:
  type: builtin
  handler: workflow_handler
tags:
  - workflow
  - test
"""
        (tmp_path / "workflow_tool.yaml").write_text(initial_tool, encoding="utf-8")

        # 2. 加载引擎
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)

        # 收集事件
        events: list[ToolEngineEvent] = []

        def on_event(event: ToolEngineEvent):
            events.append(event)

        engine.subscribe(on_event)

        await engine.load()

        # 验证初始状态
        assert engine.tool_count == 1
        tool = engine.get("workflow_tool")
        assert tool is not None
        assert tool.version == "1.0.0"

        # 3. 修改工具
        modified_tool = """
name: workflow_tool
description: 工作流测试工具 v2
category: custom
version: "2.0.0"
entry:
  type: builtin
  handler: workflow_handler_v2
tags:
  - workflow
  - test
  - updated
"""
        (tmp_path / "workflow_tool.yaml").write_text(modified_tool, encoding="utf-8")

        # 4. 添加新工具
        new_tool = """
name: new_workflow_tool
description: 新的工作流工具
category: ai
version: "1.0.0"
entry:
  type: builtin
  handler: new_handler
tags:
  - new
  - ai
"""
        (tmp_path / "new_workflow_tool.yaml").write_text(new_tool, encoding="utf-8")

        # 5. 重载
        changes = await engine.reload()

        # 验证变更
        assert "workflow_tool" in changes["modified"]
        assert "new_workflow_tool" in changes["added"]

        # 验证工具状态
        assert engine.tool_count == 2

        tool = engine.get("workflow_tool")
        assert tool.version == "2.0.0"
        assert "updated" in tool.tags

        new_tool_obj = engine.get("new_workflow_tool")
        assert new_tool_obj is not None
        assert new_tool_obj.category == ToolCategory.AI

        # 6. 删除工具
        (tmp_path / "new_workflow_tool.yaml").unlink()

        changes = await engine.reload()

        assert "new_workflow_tool" in changes["removed"]
        assert engine.tool_count == 1
        assert engine.get("new_workflow_tool") is None

        # 7. 验证事件
        event_types = [e.event_type for e in events]
        assert ToolEngineEventType.TOOL_LOADED in event_types
        assert ToolEngineEventType.TOOL_UPDATED in event_types
        assert ToolEngineEventType.TOOL_ADDED in event_types
        assert ToolEngineEventType.TOOL_REMOVED in event_types

    @pytest.mark.asyncio
    async def test_reload_without_changes(self, tmp_path):
        """测试：无变更时重载"""
        tool_yaml = """
name: stable_tool
description: 稳定的工具
category: custom
version: "1.0.0"
entry:
  type: builtin
  handler: handler
"""
        (tmp_path / "stable_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 重载（无变更）
        changes = await engine.reload()

        assert changes["added"] == []
        assert changes["modified"] == []
        assert changes["removed"] == []

    @pytest.mark.asyncio
    async def test_reload_with_invalid_file_added(self, tmp_path):
        """测试：添加无效文件后重载"""
        valid_tool = """
name: valid_tool
description: 有效工具
category: custom
entry:
  type: builtin
  handler: handler
"""
        (tmp_path / "valid_tool.yaml").write_text(valid_tool, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        assert engine.tool_count == 1

        # 添加无效文件
        invalid_tool = """
name: invalid_tool
# 缺少必需字段
"""
        (tmp_path / "invalid_tool.yaml").write_text(invalid_tool, encoding="utf-8")

        await engine.reload()

        # 有效工具仍然存在
        assert engine.tool_count == 1
        assert engine.get("valid_tool") is not None

        # 错误被记录
        assert len(engine.load_errors) == 1


# =============================================================================
# 并发访问测试
# =============================================================================


class TestToolEngineConcurrentAccess:
    """并发访问测试"""

    @pytest.mark.asyncio
    async def test_concurrent_reload_and_read(self, tmp_path):
        """测试：并发重载和读取"""
        # 创建初始工具
        for i in range(5):
            tool_yaml = f"""
name: tool_{i}
description: 工具{i}
category: custom
version: "1.0.0"
entry:
  type: builtin
  handler: handler_{i}
"""
            (tmp_path / f"tool_{i}.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        read_success = 0
        reload_count = 0

        async def reader():
            nonlocal read_success
            for _ in range(20):
                for i in range(5):
                    tool = engine.get(f"tool_{i}")
                    if tool:
                        read_success += 1
                await asyncio.sleep(0.01)

        async def reloader():
            nonlocal reload_count
            for _ in range(5):
                await engine.reload()
                reload_count += 1
                await asyncio.sleep(0.02)

        # 并发执行
        await asyncio.gather(reader(), reader(), reloader())

        assert read_success > 0
        assert reload_count == 5

    @pytest.mark.asyncio
    async def test_stress_test_many_tools(self, tmp_path):
        """测试：大量工具的压力测试"""
        # 创建 50 个工具
        for i in range(50):
            tool_yaml = f"""
name: stress_tool_{i}
description: 压力测试工具 {i}
category: custom
version: "1.0.0"
tags:
  - stress
  - test_{i % 5}
entry:
  type: builtin
  handler: handler_{i}
"""
            (tmp_path / f"stress_tool_{i}.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)

        start_time = time.perf_counter()
        await engine.load()
        load_time = time.perf_counter() - start_time

        print(f"\n加载 50 个工具耗时: {load_time:.3f}s")

        assert engine.tool_count == 50

        # 测试查找性能
        start_time = time.perf_counter()
        for _ in range(100):
            engine.find_by_tag("stress")
        find_time = time.perf_counter() - start_time

        print(f"100 次标签查找耗时: {find_time:.3f}s")

        # 测试重载性能
        start_time = time.perf_counter()
        await engine.reload()
        reload_time = time.perf_counter() - start_time

        print(f"重载耗时: {reload_time:.3f}s")

        # 性能断言
        assert load_time < 5.0  # 加载应在 5 秒内完成
        assert find_time < 1.0  # 查找应在 1 秒内完成
        assert reload_time < 5.0  # 重载应在 5 秒内完成


# =============================================================================
# 手动注册和注销测试
# =============================================================================


class TestToolEngineManualRegistration:
    """手动注册和注销测试"""

    @pytest.mark.asyncio
    async def test_manual_registration_persists_across_reload(self, tmp_path):
        """测试：手动注册的工具在重载后是否保留"""
        tool_yaml = """
name: file_tool
description: 文件工具
category: file
entry:
  type: builtin
  handler: file_handler
"""
        (tmp_path / "file_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 手动注册工具
        from src.domain.entities.tool import Tool

        manual_tool = Tool(
            id="tool_manual",
            name="manual_tool",
            description="手动注册的工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
        )
        engine.register(manual_tool)

        assert engine.tool_count == 2

        # 重载（手动注册的工具会被覆盖，因为它不在文件中）
        await engine.reload()

        # 只有文件中的工具存在
        assert engine.tool_count == 1
        assert engine.get("file_tool") is not None
        assert engine.get("manual_tool") is None  # 手动注册的工具被移除

    @pytest.mark.asyncio
    async def test_unregister_removes_from_all_indices(self, tmp_path):
        """测试：注销工具从所有索引中移除"""
        tool_yaml = """
name: indexed_tool
description: 索引测试工具
category: http
tags:
  - index
  - test
entry:
  type: builtin
  handler: handler
"""
        (tmp_path / "indexed_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 验证工具在各索引中
        assert engine.get("indexed_tool") is not None
        assert len(engine.find_by_tag("index")) == 1
        assert len(engine.find_by_category(ToolCategory.HTTP)) == 1

        # 注销
        engine.unregister("indexed_tool")

        # 验证从所有索引移除
        assert engine.get("indexed_tool") is None
        assert len(engine.find_by_tag("index")) == 0
        assert len(engine.find_by_category(ToolCategory.HTTP)) == 0


# =============================================================================
# 参数验证集成测试 - 阶段 3
# =============================================================================


class TestToolEngineParameterValidationIntegration:
    """参数验证集成测试

    测试目标：
    1. 验证真实工具的参数验证
    2. 验证结构化错误上报
    3. 验证验证错误事件
    """

    @pytest.mark.asyncio
    async def test_validate_real_http_request_tool(self):
        """测试：验证真实的 http_request 工具参数"""
        config = ToolEngineConfig(tools_directory=str(PROJECT_TOOLS_DIR))
        engine = ToolEngine(config=config)
        await engine.load()

        # 有效参数
        result = engine.validate_params(
            "http_request",
            {
                "url": "https://api.example.com/users",
                "method": "GET",
            },
        )

        assert result.is_valid is True
        assert "url" in result.validated_params

    @pytest.mark.asyncio
    async def test_validate_real_llm_call_tool(self):
        """测试：验证真实的 llm_call 工具参数"""
        config = ToolEngineConfig(tools_directory=str(PROJECT_TOOLS_DIR))
        engine = ToolEngine(config=config)
        await engine.load()

        # 有效参数（根据实际 llm_call.yaml 定义）
        result = engine.validate_params(
            "llm_call",
            {
                "provider": "openai",
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello!"}],
            },
        )

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validation_error_event_integration(self, tmp_path):
        """测试：验证错误事件集成"""
        tool_yaml = """
name: validation_test_tool
description: 验证测试工具
category: custom
version: "1.0.0"
parameters:
  - name: required_param
    type: string
    required: true
    description: 必填参数
  - name: number_param
    type: number
    required: false
    description: 数字参数
entry:
  type: builtin
  handler: test_handler
"""
        (tmp_path / "validation_test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 收集事件
        events: list[ToolEngineEvent] = []

        def on_event(event: ToolEngineEvent):
            events.append(event)

        engine.subscribe(on_event)

        # 触发验证错误
        result = engine.validate_params(
            "validation_test_tool",
            {"number_param": "not_a_number"},  # 缺少必填参数，类型错误
        )

        assert result.is_valid is False

        # 验证事件
        validation_events = [
            e for e in events if e.event_type == ToolEngineEventType.VALIDATION_ERROR
        ]
        assert len(validation_events) == 1
        assert validation_events[0].tool_name == "validation_test_tool"
        assert validation_events[0].validation_errors is not None
        assert len(validation_events[0].validation_errors) >= 1

    @pytest.mark.asyncio
    async def test_structured_error_reporting(self, tmp_path):
        """测试：结构化错误上报"""
        tool_yaml = """
name: error_test_tool
description: 错误测试工具
category: custom
version: "1.0.0"
parameters:
  - name: name
    type: string
    required: true
    description: 名称
  - name: age
    type: number
    required: true
    description: 年龄
  - name: status
    type: string
    required: false
    enum: [active, inactive, pending]
    description: 状态
entry:
  type: builtin
  handler: error_handler
"""
        (tmp_path / "error_test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(
            tools_directory=str(tmp_path),
            strict_validation=True,  # 启用严格模式
        )
        engine = ToolEngine(config=config)
        await engine.load()

        # 触发多种错误
        result = engine.validate_params(
            "error_test_tool",
            {
                # 缺少 name（必填）
                "age": "not_a_number",  # 类型错误
                "status": "invalid_status",  # 枚举错误
                "extra_field": "value",  # 多余参数（严格模式）
            },
        )

        assert result.is_valid is False
        assert len(result.errors) >= 3

        # 验证错误类型
        error_types = [e.error_type.value for e in result.errors]
        assert "missing_required" in error_types
        assert "type_mismatch" in error_types
        assert "invalid_enum" in error_types
        assert "extra_parameter" in error_types

        # 验证错误可以转换为字典
        for error in result.errors:
            error_dict = error.to_dict()
            assert "error_type" in error_dict
            assert "parameter_name" in error_dict
            assert "message" in error_dict

    @pytest.mark.asyncio
    async def test_validation_error_exception_integration(self, tmp_path):
        """测试：验证错误异常集成"""
        from src.domain.services.tool_parameter_validator import ToolValidationError

        tool_yaml = """
name: exception_test_tool
description: 异常测试工具
category: custom
version: "1.0.0"
parameters:
  - name: input
    type: string
    required: true
    description: 输入
entry:
  type: builtin
  handler: exception_handler
"""
        (tmp_path / "exception_test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 使用 validate_params_or_raise
        with pytest.raises(ToolValidationError) as exc_info:
            engine.validate_params_or_raise(
                "exception_test_tool",
                {},  # 缺少必填参数
            )

        # 验证异常内容
        assert exc_info.value.tool_name == "exception_test_tool"
        assert len(exc_info.value.errors) == 1

        # 验证可以转换为字典（用于 API 响应）
        error_dict = exc_info.value.to_dict()
        assert error_dict["tool_name"] == "exception_test_tool"
        assert error_dict["error_count"] == 1
        assert len(error_dict["errors"]) == 1

    @pytest.mark.asyncio
    async def test_validation_with_default_values_integration(self, tmp_path):
        """测试：验证时默认值填充集成"""
        tool_yaml = """
name: default_test_tool
description: 默认值测试工具
category: custom
version: "1.0.0"
parameters:
  - name: message
    type: string
    required: true
    description: 消息
  - name: priority
    type: string
    required: true
    default: normal
    enum: [low, normal, high]
    description: 优先级
  - name: retry_count
    type: number
    required: false
    default: 3
    description: 重试次数
entry:
  type: builtin
  handler: default_handler
"""
        (tmp_path / "default_test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 只提供必填参数（无默认值的）
        result = engine.validate_params(
            "default_test_tool",
            {"message": "Hello"},
        )

        assert result.is_valid is True
        assert result.validated_params["message"] == "Hello"
        assert result.validated_params["priority"] == "normal"  # 默认值
        assert result.validated_params["retry_count"] == 3  # 默认值

    @pytest.mark.asyncio
    async def test_coordinator_error_handling_simulation(self, tmp_path):
        """测试：模拟协调者处理验证错误"""
        tool_yaml = """
name: coordinator_test_tool
description: 协调者测试工具
category: custom
version: "1.0.0"
parameters:
  - name: task_id
    type: string
    required: true
    description: 任务ID
  - name: action
    type: string
    required: true
    enum: [start, stop, pause, resume]
    description: 操作类型
entry:
  type: builtin
  handler: coordinator_handler
"""
        (tmp_path / "coordinator_test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 模拟协调者收到的错误请求
        invalid_params = {
            "task_id": 12345,  # 类型错误，应该是字符串
            "action": "restart",  # 枚举错误
        }

        result = engine.validate_params("coordinator_test_tool", invalid_params)

        # 协调者可以从验证结果中提取错误信息
        if not result.is_valid:
            error_report = {
                "tool": "coordinator_test_tool",
                "errors": [
                    {
                        "param": e.parameter_name,
                        "type": e.error_type.value,
                        "message": e.message,
                    }
                    for e in result.errors
                ],
            }

            # 验证错误报告格式
            assert error_report["tool"] == "coordinator_test_tool"
            assert len(error_report["errors"]) == 2

            # 验证可以识别具体错误
            param_errors = {e["param"]: e["type"] for e in error_report["errors"]}
            assert param_errors.get("task_id") == "type_mismatch"
            assert param_errors.get("action") == "invalid_enum"


# =============================================================================
# 执行调度与子 Agent 协作集成测试 - 阶段 4
# =============================================================================


class TestToolEngineExecutionIntegration:
    """执行调度集成测试

    测试目标：
    1. ConversationAgent 触发工具 → 子 Agent 执行 → 结果返回
    2. Workflow 节点使用相同 ToolEngine
    3. 结果写入知识库
    4. 端到端流程验证
    """

    @pytest.mark.asyncio
    async def test_end_to_end_conversation_agent_tool_execution(self, tmp_path):
        """端到端测试：ConversationAgent 触发工具执行完整流程"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_executor import (
            ToolSubAgent,
        )

        # 1. 创建工具配置
        weather_tool_yaml = """
name: weather_query
description: 天气查询工具
category: http
version: "1.0.0"
parameters:
  - name: city
    type: string
    required: true
    description: 城市名称
  - name: days
    type: number
    required: false
    default: 1
    description: 预报天数
entry:
  type: builtin
  handler: weather
"""
        (tmp_path / "weather_query.yaml").write_text(weather_tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {
            "city": "北京",
            "weather": "晴",
            "temperature": 25,
            "humidity": 60,
        }
        engine.register_executor("weather", mock_executor)

        # 4. 注册知识库记录器
        knowledge_records = []

        class MockKnowledgeRecorder:
            async def record(self, data):
                knowledge_records.append(data)

        engine.set_knowledge_recorder(MockKnowledgeRecorder())

        # 5. 收集事件
        events = []

        def on_event(event):
            events.append(event)

        engine.subscribe(on_event)

        # 6. 模拟 ConversationAgent 创建子 Agent 执行工具
        sub_agent = ToolSubAgent(
            agent_id="tool_sub_weather_1",
            tool_engine=engine,
            parent_agent_id="conversation_agent_main",
        )

        # 7. 执行工具
        result = await sub_agent.execute(
            tool_name="weather_query",
            params={"city": "北京"},
        )

        # 8. 验证执行结果
        assert result.is_success is True
        assert result.output["city"] == "北京"
        assert result.output["weather"] == "晴"
        assert result.execution_time > 0

        # 9. 验证执行器被调用
        mock_executor.execute.assert_called_once()

        # 10. 验证知识库记录
        assert len(knowledge_records) == 1
        record = knowledge_records[0]
        assert record["tool_name"] == "weather_query"
        assert record["success"] is True
        assert record["output"]["city"] == "北京"

        # 11. 验证事件
        event_types = [e.event_type for e in events]
        assert ToolEngineEventType.EXECUTION_STARTED in event_types
        assert ToolEngineEventType.EXECUTION_COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_node_tool_execution(self, tmp_path):
        """端到端测试：Workflow 节点工具执行"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_executor import ToolExecutionContext

        # 1. 创建数据转换工具
        transform_tool_yaml = """
name: data_transform
description: 数据转换工具
category: custom
version: "1.0.0"
parameters:
  - name: input_data
    type: object
    required: true
    description: 输入数据
  - name: format
    type: string
    required: true
    enum: [json, xml, csv]
    description: 目标格式
entry:
  type: builtin
  handler: transform
"""
        (tmp_path / "data_transform.yaml").write_text(transform_tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {
            "transformed": True,
            "output_format": "json",
            "data": {"key": "value"},
        }
        engine.register_executor("transform", mock_executor)

        # 4. 模拟 Workflow 节点调用
        context = ToolExecutionContext.for_workflow(
            workflow_id="wf_data_pipeline",
            node_id="transform_node_1",
            inputs={"previous_node_output": {"raw_data": "value"}},
        )

        # 5. 执行工具
        result = await engine.execute(
            tool_name="data_transform",
            params={
                "input_data": {"key": "value"},
                "format": "json",
            },
            context=context,
        )

        # 6. 验证执行结果
        assert result.is_success is True
        assert result.output["transformed"] is True
        assert result.output["output_format"] == "json"

        # 7. 验证上下文包含工作流信息
        assert context.workflow_id == "wf_data_pipeline"
        assert context.variables["node_id"] == "transform_node_1"

        # 8. 验证结果可序列化（用于节点间传递）
        result_dict = result.to_dict()
        assert "output" in result_dict
        assert "is_success" in result_dict

    @pytest.mark.asyncio
    async def test_conversation_and_workflow_share_same_engine(self, tmp_path):
        """测试：ConversationAgent 和 Workflow 共享同一个 ToolEngine"""

        from src.domain.services.tool_executor import (
            ToolExecutionContext,
            ToolSubAgent,
        )

        # 1. 创建通用工具
        api_tool_yaml = """
name: api_call
description: API 调用工具
category: http
version: "1.0.0"
parameters:
  - name: endpoint
    type: string
    required: true
    description: API 端点
  - name: method
    type: string
    required: false
    default: GET
    enum: [GET, POST, PUT, DELETE]
    description: HTTP 方法
entry:
  type: builtin
  handler: api
"""
        (tmp_path / "api_call.yaml").write_text(api_tool_yaml, encoding="utf-8")

        # 2. 初始化共享的 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        shared_engine = ToolEngine(config=config)
        await shared_engine.load()

        # 3. 注册执行器
        call_count = 0

        class CountingExecutor:
            async def execute(self, tool, params, context):
                nonlocal call_count
                call_count += 1
                return {"status": "success", "call_number": call_count}

        shared_engine.register_executor("api", CountingExecutor())

        # 4. ConversationAgent 调用
        sub_agent = ToolSubAgent(
            agent_id="tool_sub_api",
            tool_engine=shared_engine,
            parent_agent_id="conversation_agent",
        )

        result1 = await sub_agent.execute(
            tool_name="api_call",
            params={"endpoint": "/api/users"},
        )

        assert result1.is_success is True
        assert result1.output["call_number"] == 1

        # 5. Workflow 节点调用（使用同一个 engine）
        context = ToolExecutionContext.for_workflow(
            workflow_id="wf_1",
            node_id="api_node",
            inputs={},
        )

        result2 = await shared_engine.execute(
            tool_name="api_call",
            params={"endpoint": "/api/products", "method": "POST"},
            context=context,
        )

        assert result2.is_success is True
        assert result2.output["call_number"] == 2  # 共享状态

        # 6. 验证共享同一个执行器
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_tool_execution_chain(self, tmp_path):
        """测试：工具链式执行（一个工具的输出作为下一个工具的输入）"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_executor import (
            ToolSubAgent,
        )

        # 1. 创建两个工具
        fetch_tool_yaml = """
name: data_fetch
description: 数据获取工具
category: http
version: "1.0.0"
parameters:
  - name: source
    type: string
    required: true
    description: 数据源
entry:
  type: builtin
  handler: fetch
"""
        process_tool_yaml = """
name: data_process
description: 数据处理工具
category: custom
version: "1.0.0"
parameters:
  - name: data
    type: array
    required: true
    description: 待处理数据
  - name: operation
    type: string
    required: true
    enum: [filter, sort, aggregate]
    description: 操作类型
entry:
  type: builtin
  handler: process
"""
        (tmp_path / "data_fetch.yaml").write_text(fetch_tool_yaml, encoding="utf-8")
        (tmp_path / "data_process.yaml").write_text(process_tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册执行器
        fetch_executor = AsyncMock()
        fetch_executor.execute.return_value = {
            "data": [{"id": 1, "value": 100}, {"id": 2, "value": 200}]
        }

        process_executor = AsyncMock()
        process_executor.execute.return_value = {
            "processed": True,
            "result": [{"id": 2, "value": 200}],  # 过滤后的结果
        }

        engine.register_executor("fetch", fetch_executor)
        engine.register_executor("process", process_executor)

        # 4. 创建子 Agent
        sub_agent = ToolSubAgent(
            agent_id="tool_chain_agent",
            tool_engine=engine,
            parent_agent_id="main_agent",
        )

        # 5. 执行工具链
        # Step 1: 获取数据
        fetch_result = await sub_agent.execute(
            tool_name="data_fetch",
            params={"source": "database"},
        )

        assert fetch_result.is_success is True

        # Step 2: 使用第一个工具的输出作为第二个工具的输入
        process_result = await sub_agent.execute(
            tool_name="data_process",
            params={
                "data": fetch_result.output["data"],  # 链式传递
                "operation": "filter",
            },
        )

        assert process_result.is_success is True
        assert process_result.output["processed"] is True

        # 6. 验证执行历史
        assert len(sub_agent.execution_history) == 2

    @pytest.mark.asyncio
    async def test_tool_execution_with_failure_handling(self, tmp_path):
        """测试：工具执行失败处理"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_executor import (
            ToolExecutionContext,
        )

        # 1. 创建工具
        tool_yaml = """
name: unreliable_tool
description: 不稳定的工具
category: custom
version: "1.0.0"
parameters:
  - name: action
    type: string
    required: true
    description: 操作
entry:
  type: builtin
  handler: unreliable
"""
        (tmp_path / "unreliable_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册知识库记录器
        knowledge_records = []

        class MockKnowledgeRecorder:
            async def record(self, data):
                knowledge_records.append(data)

        engine.set_knowledge_recorder(MockKnowledgeRecorder())

        # 4. 注册一个会失败的执行器
        fail_executor = AsyncMock()
        fail_executor.execute.side_effect = RuntimeError("服务不可用")
        engine.register_executor("unreliable", fail_executor)

        # 5. 执行工具
        context = ToolExecutionContext()
        result = await engine.execute(
            tool_name="unreliable_tool",
            params={"action": "test"},
            context=context,
        )

        # 6. 验证失败结果
        assert result.is_success is False
        assert result.error_type == "execution_error"
        assert "服务不可用" in result.error

        # 7. 验证失败也被记录到知识库
        assert len(knowledge_records) == 1
        record = knowledge_records[0]
        assert record["success"] is False
        assert "服务不可用" in record["error"]

    @pytest.mark.asyncio
    async def test_tool_execution_timeout_handling(self, tmp_path):
        """测试：工具执行超时处理"""
        from src.domain.services.tool_executor import ToolExecutionContext

        # 1. 创建工具
        tool_yaml = """
name: slow_tool
description: 慢速工具
category: custom
version: "1.0.0"
parameters:
  - name: delay
    type: number
    required: false
    default: 1
    description: 延迟时间
entry:
  type: builtin
  handler: slow
"""
        (tmp_path / "slow_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册一个慢执行器
        class SlowExecutor:
            async def execute(self, tool, params, context):
                await asyncio.sleep(5)  # 5秒延迟
                return {"status": "completed"}

        engine.register_executor("slow", SlowExecutor())

        # 4. 使用短超时执行
        context = ToolExecutionContext(timeout=0.1)  # 100ms 超时
        result = await engine.execute(
            tool_name="slow_tool",
            params={},
            context=context,
        )

        # 5. 验证超时结果
        assert result.is_success is False
        assert result.error_type == "timeout"

    @pytest.mark.asyncio
    async def test_sub_agent_result_callback(self, tmp_path):
        """测试：子 Agent 结果回调"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_executor import ToolSubAgent

        # 1. 创建工具
        tool_yaml = """
name: callback_test_tool
description: 回调测试工具
category: custom
version: "1.0.0"
parameters:
  - name: value
    type: string
    required: true
    description: 值
entry:
  type: builtin
  handler: callback_test
"""
        (tmp_path / "callback_test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"received": "test_value"}
        engine.register_executor("callback_test", mock_executor)

        # 4. 创建带回调的子 Agent
        callback_results = []

        def on_result(result):
            callback_results.append(result)

        sub_agent = ToolSubAgent(
            agent_id="callback_sub_agent",
            tool_engine=engine,
            parent_agent_id="parent_agent",
            on_result_callback=on_result,
        )

        # 5. 执行工具
        await sub_agent.execute(
            tool_name="callback_test_tool",
            params={"value": "test_value"},
        )

        # 6. 验证回调被调用
        assert len(callback_results) == 1
        assert callback_results[0].is_success is True
        assert callback_results[0].output["received"] == "test_value"

    @pytest.mark.asyncio
    async def test_sub_agent_batch_execution(self, tmp_path):
        """测试：子 Agent 批量执行"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_executor import ToolSubAgent

        # 1. 创建多个工具
        for i in range(3):
            tool_yaml = f"""
name: batch_tool_{i}
description: 批量测试工具 {i}
category: custom
version: "1.0.0"
parameters:
  - name: input
    type: string
    required: true
    description: 输入
entry:
  type: builtin
  handler: batch_{i}
"""
            (tmp_path / f"batch_tool_{i}.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册执行器
        for i in range(3):
            mock_executor = AsyncMock()
            mock_executor.execute.return_value = {"tool_index": i, "status": "done"}
            engine.register_executor(f"batch_{i}", mock_executor)

        # 4. 创建子 Agent 并批量执行
        sub_agent = ToolSubAgent(
            agent_id="batch_sub_agent",
            tool_engine=engine,
            parent_agent_id="parent_agent",
        )

        tool_calls = [
            ("batch_tool_0", {"input": "value_0"}),
            ("batch_tool_1", {"input": "value_1"}),
            ("batch_tool_2", {"input": "value_2"}),
        ]

        results = await sub_agent.execute_batch(tool_calls)

        # 5. 验证所有执行成功
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.is_success is True
            assert result.output["tool_index"] == i

        # 6. 验证执行历史
        assert len(sub_agent.execution_history) == 3

    @pytest.mark.asyncio
    async def test_real_tools_execution_with_mock_executors(self):
        """测试：使用真实工具配置但模拟执行器"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_executor import (
            ToolSubAgent,
        )

        # 1. 使用真实工具目录
        config = ToolEngineConfig(tools_directory=str(PROJECT_TOOLS_DIR))
        engine = ToolEngine(config=config)
        await engine.load()

        # 2. 验证工具加载
        assert engine.tool_count >= 5

        # 3. 为 http_request 工具注册模拟执行器
        http_executor = AsyncMock()
        http_executor.execute.return_value = {
            "status_code": 200,
            "body": {"users": [{"id": 1, "name": "Alice"}]},
        }
        engine.register_executor("http_request", http_executor)

        # 4. 创建子 Agent 并执行
        sub_agent = ToolSubAgent(
            agent_id="real_tool_agent",
            tool_engine=engine,
            parent_agent_id="test_parent",
        )

        result = await sub_agent.execute(
            tool_name="http_request",
            params={
                "url": "https://api.example.com/users",
                "method": "GET",
            },
        )

        # 5. 验证执行成功
        assert result.is_success is True
        assert result.output["status_code"] == 200


# =============================================================================
# 并发控制器集成测试 - 阶段 5
# =============================================================================


class TestToolConcurrencyControllerIntegration:
    """并发控制器集成测试

    测试目标：
    1. ToolConcurrencyController 与 ToolEngine 集成
    2. 并发限制在真实执行场景下生效
    3. 排队策略正确工作
    4. 负载均衡分桶正确工作
    """

    @pytest.mark.asyncio
    async def test_concurrency_controller_with_tool_engine(self, tmp_path):
        """测试：并发控制器与 ToolEngine 集成"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )
        from src.domain.services.tool_executor import ToolExecutionContext

        # 1. 创建工具
        tool_yaml = """
name: test_tool
description: 测试工具
category: custom
version: "1.0.0"
parameters:
  - name: value
    type: string
    required: true
    description: 值
entry:
  type: builtin
  handler: test
"""
        (tmp_path / "test_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册执行器（带延迟以模拟真实执行）
        async def slow_execute(tool, params, context):
            await asyncio.sleep(0.1)  # 模拟执行时间
            return {"result": "ok"}

        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = slow_execute
        engine.register_executor("test", mock_executor)

        # 4. 创建并发控制器
        concurrency_config = ConcurrencyConfig(max_concurrent=2, strategy="reject")
        controller = ToolConcurrencyController(concurrency_config)

        results = []
        results_lock = asyncio.Lock()

        # 5. 模拟并发执行
        async def execute_with_concurrency(agent_id: str):
            # 获取槽位
            slot = await controller.acquire_slot(
                tool_name="test_tool",
                caller_id=agent_id,
                caller_type="conversation_agent",
            )

            if slot is None:
                async with results_lock:
                    results.append({"status": "rejected"})
                return

            try:
                # 执行工具
                context = ToolExecutionContext(caller_id=agent_id)
                result = await engine.execute(
                    tool_name="test_tool",
                    params={"value": "test"},
                    context=context,
                )
                async with results_lock:
                    results.append({"status": "success", "result": result})
            finally:
                await controller.release_slot(slot.slot_id)

        # 6. 并发执行 5 个请求
        tasks = [execute_with_concurrency(f"agent_{i}") for i in range(5)]
        await asyncio.gather(*tasks)

        # 7. 验证结果
        success_count = sum(1 for r in results if r["status"] == "success")
        rejected_count = sum(1 for r in results if r["status"] == "rejected")

        # 由于执行有延迟，前两个会成功获取槽位，后面的会被拒绝
        # 但随着执行完成释放槽位，更多请求可能成功
        # 关键是同时活跃的并发数不超过限制
        assert success_count >= 2  # 至少有 2 个成功
        assert rejected_count <= 3  # 最多 3 个被拒绝
        # 验证总数
        assert success_count + rejected_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_execution_with_queuing(self, tmp_path):
        """测试：带排队的并发执行"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )
        from src.domain.services.tool_executor import ToolExecutionContext

        # 1. 创建工具
        tool_yaml = """
name: slow_tool
description: 慢速工具
category: custom
version: "1.0.0"
parameters:
  - name: delay
    type: number
    required: false
    default: 0.1
    description: 延迟
entry:
  type: builtin
  handler: slow
"""
        (tmp_path / "slow_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册模拟执行器
        async def slow_execute(tool, params, context):
            await asyncio.sleep(0.05)
            return {"executed": True}

        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = slow_execute
        engine.register_executor("slow", mock_executor)

        # 4. 创建并发控制器
        concurrency_config = ConcurrencyConfig(max_concurrent=2, queue_size=10, strategy="fifo")
        controller = ToolConcurrencyController(concurrency_config)

        execution_order = []

        # 5. 执行函数
        async def execute_or_queue(agent_id: str, order: int):
            slot = await controller.acquire_slot(
                tool_name="slow_tool",
                caller_id=agent_id,
                caller_type="conversation_agent",
            )

            if slot:
                context = ToolExecutionContext(caller_id=agent_id)
                await engine.execute(
                    tool_name="slow_tool",
                    params={},
                    context=context,
                )
                execution_order.append(order)
                await controller.release_slot(slot.slot_id)
            else:
                # 排队
                await controller.enqueue(
                    tool_name="slow_tool",
                    caller_id=agent_id,
                    caller_type="conversation_agent",
                    params={},
                )

        # 6. 启动多个任务
        tasks = [execute_or_queue(f"agent_{i}", i) for i in range(5)]
        await asyncio.gather(*tasks)

        # 7. 处理队列中的任务
        while controller.queue_length > 0:
            queued = await controller.dequeue()
            if queued:
                slot = await controller.acquire_slot(
                    tool_name=queued.tool_name,
                    caller_id=queued.caller_id,
                    caller_type=queued.caller_type,
                )
                if slot:
                    context = ToolExecutionContext(caller_id=queued.caller_id)
                    await engine.execute(
                        tool_name=queued.tool_name,
                        params=queued.params,
                        context=context,
                    )
                    await controller.release_slot(slot.slot_id)

        # 8. 验证执行完成
        assert len(execution_order) == 2  # 前两个直接执行

    @pytest.mark.asyncio
    async def test_bucket_load_balancing_with_real_tools(self, tmp_path):
        """测试：使用真实工具的分桶负载均衡"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        # 1. 创建 HTTP 工具
        http_tool_yaml = """
name: http_tool
description: HTTP 工具
category: http
version: "1.0.0"
parameters:
  - name: url
    type: string
    required: true
    description: URL
entry:
  type: builtin
  handler: http
"""
        (tmp_path / "http_tool.yaml").write_text(http_tool_yaml, encoding="utf-8")

        # 2. 创建 AI 工具
        ai_tool_yaml = """
name: ai_tool
description: AI 工具
category: ai
version: "1.0.0"
parameters:
  - name: prompt
    type: string
    required: true
    description: 提示词
entry:
  type: builtin
  handler: ai
"""
        (tmp_path / "ai_tool.yaml").write_text(ai_tool_yaml, encoding="utf-8")

        # 3. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 4. 注册执行器
        http_executor = AsyncMock()
        http_executor.execute.return_value = {"status": 200}
        ai_executor = AsyncMock()
        ai_executor.execute.return_value = {"response": "Hello"}

        engine.register_executor("http", http_executor)
        engine.register_executor("ai", ai_executor)

        # 5. 创建带分桶限制的并发控制器
        concurrency_config = ConcurrencyConfig(
            max_concurrent=10,
            bucket_limits={
                "http": 2,  # HTTP 最多 2 并发
                "ai": 1,  # AI 最多 1 并发
            },
            strategy="reject",
        )
        controller = ToolConcurrencyController(concurrency_config)

        # 6. 测试 HTTP 分桶限制
        http_slots = []
        for i in range(3):
            slot = await controller.acquire_slot(
                tool_name="http_tool",
                caller_id=f"agent_{i}",
                caller_type="conversation_agent",
                bucket="http",
            )
            http_slots.append(slot)

        # 前两个成功，第三个失败
        assert http_slots[0] is not None
        assert http_slots[1] is not None
        assert http_slots[2] is None

        # 7. AI 分桶独立于 HTTP
        ai_slot = await controller.acquire_slot(
            tool_name="ai_tool",
            caller_id="agent_ai",
            caller_type="conversation_agent",
            bucket="ai",
        )
        assert ai_slot is not None

        # 8. 验证分桶指标
        bucket_metrics = controller.get_bucket_metrics()
        assert bucket_metrics["http"]["current"] == 2
        assert bucket_metrics["http"]["limit"] == 2
        assert bucket_metrics["ai"]["current"] == 1
        assert bucket_metrics["ai"]["limit"] == 1

    @pytest.mark.asyncio
    async def test_stress_concurrent_tool_execution(self, tmp_path):
        """压力测试：并发工具执行"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )
        from src.domain.services.tool_executor import ToolExecutionContext

        # 1. 创建工具
        tool_yaml = """
name: stress_tool
description: 压力测试工具
category: custom
version: "1.0.0"
parameters:
  - name: id
    type: number
    required: true
    description: ID
entry:
  type: builtin
  handler: stress
"""
        (tmp_path / "stress_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册快速执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"ok": True}
        engine.register_executor("stress", mock_executor)

        # 4. 创建并发控制器
        max_concurrent = 10
        concurrency_config = ConcurrencyConfig(max_concurrent=max_concurrent, strategy="reject")
        controller = ToolConcurrencyController(concurrency_config)

        # 5. 记录最大观察到的并发数
        max_observed = 0

        async def execute_task(task_id: int):
            nonlocal max_observed
            slot = await controller.acquire_slot(
                tool_name="stress_tool",
                caller_id=f"agent_{task_id}",
                caller_type="conversation_agent",
            )

            if slot:
                current = controller.current_concurrent
                max_observed = max(max_observed, current)

                context = ToolExecutionContext(caller_id=f"agent_{task_id}")
                await engine.execute(
                    tool_name="stress_tool",
                    params={"id": task_id},
                    context=context,
                )
                await asyncio.sleep(0.01)  # 模拟执行时间
                await controller.release_slot(slot.slot_id)
                return True
            return False

        # 6. 并发执行 100 个任务
        tasks = [execute_task(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        # 7. 验证并发限制
        assert max_observed <= max_concurrent
        print(f"\n最大观察并发数: {max_observed}")
        print(f"成功执行: {sum(results)}")
        print(f"被拒绝: {100 - sum(results)}")

        # 8. 验证指标
        metrics = controller.get_metrics()
        assert metrics.max_concurrent_observed <= max_concurrent

    @pytest.mark.asyncio
    async def test_timeout_cancellation_with_tool_engine(self, tmp_path):
        """测试：超时取消与 ToolEngine 集成"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )

        # 1. 创建工具
        tool_yaml = """
name: timeout_tool
description: 超时测试工具
category: custom
version: "1.0.0"
parameters:
  - name: value
    type: string
    required: true
    description: 值
entry:
  type: builtin
  handler: timeout_test
"""
        (tmp_path / "timeout_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"result": "done"}
        engine.register_executor("timeout_test", mock_executor)

        # 4. 创建并发控制器（短超时）
        concurrency_config = ConcurrencyConfig(
            max_concurrent=2, default_timeout=0.05, strategy="reject"
        )
        controller = ToolConcurrencyController(concurrency_config)

        # 5. 获取槽位但不释放
        await controller.acquire_slot(
            tool_name="timeout_tool",
            caller_id="agent_1",
            caller_type="conversation_agent",
        )
        await controller.acquire_slot(
            tool_name="timeout_tool",
            caller_id="agent_2",
            caller_type="conversation_agent",
        )

        # 6. 并发数已满
        slot3 = await controller.acquire_slot(
            tool_name="timeout_tool",
            caller_id="agent_3",
            caller_type="conversation_agent",
        )
        assert slot3 is None

        # 7. 等待超时
        await asyncio.sleep(0.1)

        # 8. 取消超时槽位
        cancelled = await controller.cancel_timeout_slots()
        assert len(cancelled) == 2

        # 9. 现在可以获取新槽位
        slot4 = await controller.acquire_slot(
            tool_name="timeout_tool",
            caller_id="agent_4",
            caller_type="conversation_agent",
        )
        assert slot4 is not None

        # 10. 验证指标
        metrics = controller.get_metrics()
        assert metrics.total_timeout == 2

    @pytest.mark.asyncio
    async def test_workflow_bypass_concurrency_limit(self, tmp_path):
        """测试：Workflow 节点绕过并发限制"""
        from unittest.mock import AsyncMock

        from src.domain.services.tool_concurrency_controller import (
            ConcurrencyConfig,
            ToolConcurrencyController,
        )
        from src.domain.services.tool_executor import ToolExecutionContext

        # 1. 创建工具
        tool_yaml = """
name: shared_tool
description: 共享工具
category: custom
version: "1.0.0"
parameters:
  - name: input
    type: string
    required: true
    description: 输入
entry:
  type: builtin
  handler: shared
"""
        (tmp_path / "shared_tool.yaml").write_text(tool_yaml, encoding="utf-8")

        # 2. 初始化 ToolEngine
        config = ToolEngineConfig(tools_directory=str(tmp_path))
        engine = ToolEngine(config=config)
        await engine.load()

        # 3. 注册执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"processed": True}
        engine.register_executor("shared", mock_executor)

        # 4. 创建并发控制器（仅 2 个对话 Agent 并发）
        concurrency_config = ConcurrencyConfig(max_concurrent=2, strategy="reject")
        controller = ToolConcurrencyController(concurrency_config)

        # 5. 对话 Agent 占满并发槽位
        await controller.acquire_slot(
            tool_name="shared_tool",
            caller_id="conv_1",
            caller_type="conversation_agent",
        )
        await controller.acquire_slot(
            tool_name="shared_tool",
            caller_id="conv_2",
            caller_type="conversation_agent",
        )

        # 对话 Agent 被拒绝
        conv_slot3 = await controller.acquire_slot(
            tool_name="shared_tool",
            caller_id="conv_3",
            caller_type="conversation_agent",
        )
        assert conv_slot3 is None

        # 6. Workflow 节点不受限制
        wf_slots = []
        for i in range(5):
            slot = await controller.acquire_slot(
                tool_name="shared_tool",
                caller_id=f"workflow_{i}",
                caller_type="workflow_node",
            )
            if slot:
                # 执行工具
                context = ToolExecutionContext.for_workflow(
                    workflow_id=f"wf_{i}",
                    node_id=f"node_{i}",
                    inputs={},
                )
                await engine.execute(
                    tool_name="shared_tool",
                    params={"input": f"value_{i}"},
                    context=context,
                )
                wf_slots.append(slot)

        # 所有 Workflow 槽位都成功
        assert len(wf_slots) == 5

        # 7. 验证并发数仅计算对话 Agent
        assert controller.current_concurrent == 2
