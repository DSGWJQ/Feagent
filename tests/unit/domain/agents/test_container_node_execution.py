"""测试：容器执行节点类型

测试目标：
1. 容器节点类型定义 (CONTAINER NodeType)
2. 容器执行器接口定义
3. 容器配置验证
4. 执行结果结构

完成标准：
- 有 CONTAINER 节点类型
- ContainerExecutor 接口完整
- 配置验证通过
- 执行结果包含日志和输出
"""

import pytest

# ==================== 测试1：CONTAINER 节点类型 ====================


class TestContainerNodeType:
    """测试 CONTAINER 节点类型"""

    def test_node_type_has_container(self):
        """NodeType 应有 CONTAINER 类型"""
        from src.domain.agents.node_definition import NodeType

        assert hasattr(NodeType, "CONTAINER")
        assert NodeType.CONTAINER.value == "container"

    def test_can_create_container_node_definition(self):
        """可以创建容器节点定义"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="Python容器执行",
            code="print('Hello from container')",
            is_container=True,
            container_config={
                "image": "python:3.11-slim",
                "timeout": 30,
                "memory_limit": "256m",
            },
        )

        assert node.node_type == NodeType.CONTAINER
        assert node.is_container is True
        assert node.container_config["image"] == "python:3.11-slim"

    def test_container_node_requires_code(self):
        """容器节点需要 code 字段"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="缺少代码的容器节点",
            is_container=True,
        )

        errors = node.validate()
        assert len(errors) > 0
        assert any("code" in e.lower() or "代码" in e for e in errors)


# ==================== 测试2：容器配置结构 ====================


class TestContainerConfig:
    """测试容器配置结构"""

    def test_default_container_config(self):
        """默认容器配置"""
        from src.domain.agents.container_executor import DEFAULT_CONTAINER_CONFIG

        assert "image" in DEFAULT_CONTAINER_CONFIG
        assert "timeout" in DEFAULT_CONTAINER_CONFIG
        assert "memory_limit" in DEFAULT_CONTAINER_CONFIG
        assert DEFAULT_CONTAINER_CONFIG["timeout"] == 60

    def test_container_config_has_image(self):
        """容器配置应有镜像"""
        from src.domain.agents.container_executor import ContainerConfig

        config = ContainerConfig(image="python:3.11")

        assert config.image == "python:3.11"

    def test_container_config_has_timeout(self):
        """容器配置应有超时"""
        from src.domain.agents.container_executor import ContainerConfig

        config = ContainerConfig(image="python:3.11", timeout=30)

        assert config.timeout == 30

    def test_container_config_has_memory_limit(self):
        """容器配置应有内存限制"""
        from src.domain.agents.container_executor import ContainerConfig

        config = ContainerConfig(image="python:3.11", memory_limit="512m")

        assert config.memory_limit == "512m"

    def test_container_config_has_environment(self):
        """容器配置应支持环境变量"""
        from src.domain.agents.container_executor import ContainerConfig

        config = ContainerConfig(
            image="python:3.11", environment={"API_KEY": "secret", "DEBUG": "true"}
        )

        assert config.environment["API_KEY"] == "secret"
        assert config.environment["DEBUG"] == "true"


# ==================== 测试3：容器执行器接口 ====================


class TestContainerExecutorInterface:
    """测试容器执行器接口"""

    def test_container_executor_has_execute_method(self):
        """ContainerExecutor 应有 execute 方法"""
        from unittest.mock import Mock

        from src.domain.agents.container_executor import ContainerExecutor

        mock_executor = Mock()
        executor = ContainerExecutor(mock_executor)
        assert hasattr(executor, "execute")
        assert callable(executor.execute)

    def test_container_executor_has_execute_async_method(self):
        """ContainerExecutor 应有异步执行方法"""
        from unittest.mock import Mock

        from src.domain.agents.container_executor import ContainerExecutor

        mock_executor = Mock()
        executor = ContainerExecutor(mock_executor)
        assert hasattr(executor, "execute_async")

    def test_container_executor_has_is_available_method(self):
        """ContainerExecutor 应有可用性检查方法"""
        from unittest.mock import Mock

        from src.domain.agents.container_executor import ContainerExecutor

        mock_executor = Mock()
        executor = ContainerExecutor(mock_executor)
        assert hasattr(executor, "is_available")

    def test_container_executor_requires_executor_argument(self):
        """ContainerExecutor 应要求传入 executor 参数（不允许 None）"""
        from src.domain.agents.container_executor import ContainerExecutor

        with pytest.raises(ValueError, match="executor cannot be None"):
            ContainerExecutor(None)


# ==================== 测试4：执行结果结构 ====================


class TestContainerExecutionResult:
    """测试容器执行结果结构"""

    def test_result_has_success_flag(self):
        """执行结果应有成功标志"""
        from src.domain.agents.container_executor import ContainerExecutionResult

        result = ContainerExecutionResult(success=True)

        assert result.success is True

    def test_result_has_stdout(self):
        """执行结果应有标准输出"""
        from src.domain.agents.container_executor import ContainerExecutionResult

        result = ContainerExecutionResult(success=True, stdout="Hello World")

        assert result.stdout == "Hello World"

    def test_result_has_stderr(self):
        """执行结果应有标准错误"""
        from src.domain.agents.container_executor import ContainerExecutionResult

        result = ContainerExecutionResult(success=False, stderr="Error occurred")

        assert result.stderr == "Error occurred"

    def test_result_has_exit_code(self):
        """执行结果应有退出码"""
        from src.domain.agents.container_executor import ContainerExecutionResult

        result = ContainerExecutionResult(success=True, exit_code=0)

        assert result.exit_code == 0

    def test_result_has_execution_time(self):
        """执行结果应有执行时间"""
        from src.domain.agents.container_executor import ContainerExecutionResult

        result = ContainerExecutionResult(success=True, execution_time=1.5)

        assert result.execution_time == 1.5

    def test_result_has_logs(self):
        """执行结果应有日志列表"""
        from src.domain.agents.container_executor import ContainerExecutionResult

        result = ContainerExecutionResult(
            success=True,
            logs=[
                {"timestamp": "2025-01-01T00:00:00", "level": "INFO", "message": "Started"},
                {"timestamp": "2025-01-01T00:00:01", "level": "INFO", "message": "Completed"},
            ],
        )

        assert len(result.logs) == 2
        assert result.logs[0]["level"] == "INFO"

    def test_result_to_dict(self):
        """执行结果可序列化为字典"""
        from src.domain.agents.container_executor import ContainerExecutionResult

        result = ContainerExecutionResult(
            success=True,
            stdout="output",
            stderr="",
            exit_code=0,
            execution_time=1.0,
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["stdout"] == "output"
        assert data["exit_code"] == 0


# ==================== 测试5：Mock 容器执行 ====================


class TestMockContainerExecution:
    """测试 Mock 容器执行（不依赖真实 Docker）"""

    @pytest.mark.asyncio
    async def test_mock_executor_returns_result(self):
        """Mock 执行器返回结果"""
        from src.domain.agents.container_executor import (
            ContainerConfig,
            ContainerExecutionResult,
            MockContainerExecutor,
        )

        executor = MockContainerExecutor()
        config = ContainerConfig(image="python:3.11")

        result = await executor.execute_async(
            code="print('Hello')",
            config=config,
            inputs={"data": "test"},
        )

        assert isinstance(result, ContainerExecutionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_mock_executor_captures_output(self):
        """Mock 执行器捕获输出"""
        from src.domain.agents.container_executor import (
            ContainerConfig,
            MockContainerExecutor,
        )

        executor = MockContainerExecutor()
        config = ContainerConfig(image="python:3.11")

        result = await executor.execute_async(
            code="print('Test Output')",
            config=config,
        )

        # Mock 执行器应返回模拟的输出
        assert result.stdout is not None

    @pytest.mark.asyncio
    async def test_mock_executor_handles_error(self):
        """Mock 执行器处理错误"""
        from src.domain.agents.container_executor import (
            ContainerConfig,
            MockContainerExecutor,
        )

        executor = MockContainerExecutor(simulate_error=True)
        config = ContainerConfig(image="python:3.11")

        result = await executor.execute_async(
            code="raise Exception('Test Error')",
            config=config,
        )

        assert result.success is False
        assert result.exit_code != 0


# ==================== 测试6：容器节点工厂方法 ====================


class TestContainerNodeFactory:
    """测试容器节点工厂方法"""

    def test_factory_creates_container_node(self):
        """工厂方法创建容器节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_container_node(
            name="数据处理",
            code="import pandas; print('处理完成')",
            image="python:3.11-slim",
            timeout=60,
        )

        assert node.name == "数据处理"
        assert node.is_container is True
        assert node.container_config["image"] == "python:3.11-slim"

    def test_factory_creates_container_node_with_dependencies(self):
        """工厂方法创建带依赖的容器节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_container_node(
            name="ML处理",
            code="import sklearn; print('ML ready')",
            image="python:3.11-slim",
            pip_packages=["scikit-learn", "pandas", "numpy"],
        )

        assert "pip_packages" in node.container_config
        assert "scikit-learn" in node.container_config["pip_packages"]


# 导出
__all__ = [
    "TestContainerNodeType",
    "TestContainerConfig",
    "TestContainerExecutorInterface",
    "TestContainerExecutionResult",
    "TestMockContainerExecution",
    "TestContainerNodeFactory",
]
