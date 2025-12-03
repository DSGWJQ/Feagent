"""测试：子Agent调度器

测试目标：
1. SubAgent 接口定义和基类
2. SubAgentRegistry 注册和查找
3. SubAgent 生命周期状态
4. SubAgent 执行和结果返回

完成标准：
- SubAgent 接口清晰
- Registry 可以注册/获取/列出子Agent
- 子Agent 可以异步执行并返回结果
"""

from typing import Any

import pytest

# ==================== 测试1：SubAgent 基础定义 ====================


class TestSubAgentDefinition:
    """测试 SubAgent 基础定义"""

    def test_sub_agent_type_enum_exists(self):
        """SubAgentType 枚举应存在"""
        from src.domain.services.sub_agent_scheduler import SubAgentType

        # 验证基础类型
        assert SubAgentType.SEARCH is not None
        assert SubAgentType.MCP is not None
        assert SubAgentType.PYTHON_EXECUTOR is not None
        assert SubAgentType.DATA_PROCESSOR is not None

    def test_sub_agent_status_enum_exists(self):
        """SubAgentStatus 枚举应存在"""
        from src.domain.services.sub_agent_scheduler import SubAgentStatus

        assert SubAgentStatus.CREATED is not None
        assert SubAgentStatus.RUNNING is not None
        assert SubAgentStatus.COMPLETED is not None
        assert SubAgentStatus.FAILED is not None
        assert SubAgentStatus.CANCELLED is not None

    def test_sub_agent_result_structure(self):
        """SubAgentResult 数据结构应正确"""
        from src.domain.services.sub_agent_scheduler import SubAgentResult

        result = SubAgentResult(
            agent_id="agent_001",
            agent_type="search",
            success=True,
            output={"data": "search results"},
            error=None,
            execution_time=1.5,
        )

        assert result.agent_id == "agent_001"
        assert result.agent_type == "search"
        assert result.success is True
        assert result.output["data"] == "search results"
        assert result.error is None
        assert result.execution_time == 1.5

    def test_sub_agent_result_failure(self):
        """SubAgentResult 应支持失败状态"""
        from src.domain.services.sub_agent_scheduler import SubAgentResult

        result = SubAgentResult(
            agent_id="agent_002",
            agent_type="python_executor",
            success=False,
            output={},
            error="Execution timeout",
            execution_time=30.0,
        )

        assert result.success is False
        assert result.error == "Execution timeout"


# ==================== 测试2：SubAgent 接口 ====================


class TestSubAgentProtocol:
    """测试 SubAgent 协议接口"""

    def test_sub_agent_protocol_has_required_methods(self):
        """SubAgent 协议应定义必需方法"""
        from src.domain.services.sub_agent_scheduler import SubAgentProtocol

        # 检查协议方法
        assert hasattr(SubAgentProtocol, "execute")
        assert hasattr(SubAgentProtocol, "get_capabilities")
        assert hasattr(SubAgentProtocol, "get_status")

    @pytest.mark.asyncio
    async def test_sub_agent_can_be_implemented(self):
        """SubAgent 协议可以被实现"""
        from src.domain.services.sub_agent_scheduler import (
            SubAgentResult,
            SubAgentStatus,
        )

        class MockSubAgent:
            def __init__(self):
                self._status = SubAgentStatus.CREATED

            async def execute(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> SubAgentResult:
                self._status = SubAgentStatus.RUNNING
                # 模拟执行
                self._status = SubAgentStatus.COMPLETED
                return SubAgentResult(
                    agent_id="mock_001",
                    agent_type="mock",
                    success=True,
                    output={"result": "mock result"},
                )

            def get_capabilities(self) -> dict[str, Any]:
                return {"can_search": True}

            def get_status(self) -> SubAgentStatus:
                return self._status

        agent = MockSubAgent()
        result = await agent.execute({"query": "test"}, {})

        assert result.success is True
        assert agent.get_status() == SubAgentStatus.COMPLETED


# ==================== 测试3：SubAgent 注册表 ====================


class TestSubAgentRegistry:
    """测试 SubAgent 注册表"""

    def test_registry_can_register_agent_class(self):
        """注册表可以注册 Agent 类"""
        from src.domain.services.sub_agent_scheduler import (
            SubAgentRegistry,
            SubAgentType,
        )

        registry = SubAgentRegistry()

        # 创建 Mock Agent 类
        class MockSearchAgent:
            pass

        registry.register(SubAgentType.SEARCH, MockSearchAgent)

        assert registry.has(SubAgentType.SEARCH)

    def test_registry_can_get_agent_class(self):
        """注册表可以获取已注册的 Agent 类"""
        from src.domain.services.sub_agent_scheduler import (
            SubAgentRegistry,
            SubAgentType,
        )

        registry = SubAgentRegistry()

        class MockSearchAgent:
            pass

        registry.register(SubAgentType.SEARCH, MockSearchAgent)

        agent_class = registry.get(SubAgentType.SEARCH)
        assert agent_class == MockSearchAgent

    def test_registry_returns_none_for_unregistered(self):
        """获取未注册的 Agent 应返回 None"""
        from src.domain.services.sub_agent_scheduler import (
            SubAgentRegistry,
            SubAgentType,
        )

        registry = SubAgentRegistry()

        agent_class = registry.get(SubAgentType.SEARCH)
        assert agent_class is None

    def test_registry_can_list_all_types(self):
        """注册表可以列出所有已注册类型"""
        from src.domain.services.sub_agent_scheduler import (
            SubAgentRegistry,
            SubAgentType,
        )

        registry = SubAgentRegistry()

        class MockSearchAgent:
            pass

        class MockMCPAgent:
            pass

        registry.register(SubAgentType.SEARCH, MockSearchAgent)
        registry.register(SubAgentType.MCP, MockMCPAgent)

        types = registry.list_types()
        assert SubAgentType.SEARCH in types
        assert SubAgentType.MCP in types
        assert len(types) == 2

    def test_registry_can_unregister_agent(self):
        """注册表可以取消注册 Agent"""
        from src.domain.services.sub_agent_scheduler import (
            SubAgentRegistry,
            SubAgentType,
        )

        registry = SubAgentRegistry()

        class MockSearchAgent:
            pass

        registry.register(SubAgentType.SEARCH, MockSearchAgent)
        assert registry.has(SubAgentType.SEARCH)

        registry.unregister(SubAgentType.SEARCH)
        assert not registry.has(SubAgentType.SEARCH)


# ==================== 测试4：子Agent 实例管理 ====================


class TestSubAgentInstanceManagement:
    """测试子Agent实例管理"""

    def test_registry_can_create_instance(self):
        """注册表可以创建 Agent 实例"""
        from src.domain.services.sub_agent_scheduler import (
            SubAgentRegistry,
            SubAgentType,
        )

        registry = SubAgentRegistry()

        class MockSearchAgent:
            def __init__(self, config: dict[str, Any] | None = None):
                self.config = config or {}

        registry.register(SubAgentType.SEARCH, MockSearchAgent)

        instance = registry.create_instance(SubAgentType.SEARCH, config={"api_key": "test"})

        assert instance is not None
        assert instance.config["api_key"] == "test"

    def test_registry_returns_none_for_unregistered_create(self):
        """创建未注册类型的实例应返回 None"""
        from src.domain.services.sub_agent_scheduler import (
            SubAgentRegistry,
            SubAgentType,
        )

        registry = SubAgentRegistry()

        instance = registry.create_instance(SubAgentType.SEARCH)
        assert instance is None


# ==================== 测试5：内置子Agent类型 ====================


class TestBuiltinSubAgents:
    """测试内置子Agent类型"""

    def test_search_agent_interface(self):
        """搜索Agent应实现正确接口"""
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        class SearchSubAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                return {"results": []}

            def get_capabilities(self) -> dict[str, Any]:
                return {"can_search_web": True, "can_search_docs": True}

        agent = SearchSubAgent(agent_id="search_001")
        assert agent.agent_type == SubAgentType.SEARCH
        caps = agent.get_capabilities()
        assert caps["can_search_web"] is True

    def test_python_executor_agent_interface(self):
        """Python执行器Agent应实现正确接口"""
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        class PythonExecutorSubAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.PYTHON_EXECUTOR

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                code = task.get("code", "")
                return {"stdout": "", "stderr": "", "return_value": None}

            def get_capabilities(self) -> dict[str, Any]:
                return {
                    "can_execute_python": True,
                    "max_execution_time": 30,
                    "sandboxed": True,
                }

        agent = PythonExecutorSubAgent(agent_id="python_001")
        assert agent.agent_type == SubAgentType.PYTHON_EXECUTOR


# ==================== 测试6：BaseSubAgent 基类 ====================


class TestBaseSubAgent:
    """测试 BaseSubAgent 基类"""

    def test_base_agent_has_id(self):
        """基类应有 agent_id"""
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        class TestAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                return {}

            def get_capabilities(self) -> dict[str, Any]:
                return {}

        agent = TestAgent(agent_id="test_001")
        assert agent.agent_id == "test_001"

    def test_base_agent_auto_generates_id(self):
        """基类可以自动生成 ID"""
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        class TestAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                return {}

            def get_capabilities(self) -> dict[str, Any]:
                return {}

        agent = TestAgent()
        assert agent.agent_id is not None
        assert agent.agent_id.startswith("subagent_")

    def test_base_agent_tracks_status(self):
        """基类应跟踪状态"""
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentStatus,
            SubAgentType,
        )

        class TestAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                return {"result": "done"}

            def get_capabilities(self) -> dict[str, Any]:
                return {}

        agent = TestAgent()
        assert agent.get_status() == SubAgentStatus.CREATED

    @pytest.mark.asyncio
    async def test_base_agent_execute_updates_status(self):
        """执行时应更新状态"""
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentStatus,
            SubAgentType,
        )

        class TestAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                return {"result": "done"}

            def get_capabilities(self) -> dict[str, Any]:
                return {}

        agent = TestAgent()
        result = await agent.execute({"query": "test"}, {})

        assert result.success is True
        assert agent.get_status() == SubAgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_base_agent_execute_handles_error(self):
        """执行失败应正确处理"""
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentStatus,
            SubAgentType,
        )

        class FailingAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.PYTHON_EXECUTOR

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                raise ValueError("Execution failed")

            def get_capabilities(self) -> dict[str, Any]:
                return {}

        agent = FailingAgent()
        result = await agent.execute({"code": "raise Exception()"}, {})

        assert result.success is False
        assert "Execution failed" in result.error
        assert agent.get_status() == SubAgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_base_agent_tracks_execution_time(self):
        """应跟踪执行时间"""
        import asyncio

        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        class SlowAgent(BaseSubAgent):
            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.SEARCH

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)  # 模拟耗时操作
                return {"result": "done"}

            def get_capabilities(self) -> dict[str, Any]:
                return {}

        agent = SlowAgent()
        result = await agent.execute({}, {})

        assert result.execution_time >= 0.1


# ==================== 测试7：SubAgent 任务定义 ====================


class TestSubAgentTask:
    """测试子Agent任务定义"""

    def test_sub_agent_task_structure(self):
        """SubAgentTask 数据结构应正确"""
        from src.domain.services.sub_agent_scheduler import SubAgentTask

        task = SubAgentTask(
            task_id="task_001",
            agent_type="search",
            payload={"query": "test query"},
            priority=1,
            timeout=30.0,
        )

        assert task.task_id == "task_001"
        assert task.agent_type == "search"
        assert task.payload["query"] == "test query"
        assert task.priority == 1
        assert task.timeout == 30.0

    def test_sub_agent_task_default_values(self):
        """SubAgentTask 应有默认值"""
        from src.domain.services.sub_agent_scheduler import SubAgentTask

        task = SubAgentTask(
            task_id="task_002",
            agent_type="python_executor",
            payload={"code": "print('hello')"},
        )

        assert task.priority == 0  # 默认优先级
        assert task.timeout == 60.0  # 默认超时


# ==================== 测试8：与工具系统集成 ====================


class TestToolIntegration:
    """测试与现有工具系统的集成"""

    def test_sub_agent_can_use_tool_config(self):
        """子Agent可以使用工具配置"""
        from src.domain.services.sub_agent_scheduler import (
            BaseSubAgent,
            SubAgentType,
        )

        class ToolBasedAgent(BaseSubAgent):
            def __init__(
                self,
                agent_id: str | None = None,
                tool_config: dict[str, Any] | None = None,
            ):
                super().__init__(agent_id=agent_id)
                self.tool_config = tool_config or {}

            @property
            def agent_type(self) -> SubAgentType:
                return SubAgentType.MCP

            async def _execute_internal(
                self, task: dict[str, Any], context: dict[str, Any]
            ) -> dict[str, Any]:
                # 使用工具配置
                endpoint = self.tool_config.get("endpoint", "")
                return {"endpoint_used": endpoint}

            def get_capabilities(self) -> dict[str, Any]:
                return {"tools": list(self.tool_config.keys())}

        agent = ToolBasedAgent(
            agent_id="mcp_001", tool_config={"endpoint": "http://localhost:8080"}
        )

        assert agent.tool_config["endpoint"] == "http://localhost:8080"


# 导出
__all__ = [
    "TestSubAgentDefinition",
    "TestSubAgentProtocol",
    "TestSubAgentRegistry",
    "TestSubAgentInstanceManagement",
    "TestBuiltinSubAgents",
    "TestBaseSubAgent",
    "TestSubAgentTask",
    "TestToolIntegration",
]
