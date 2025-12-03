"""容器执行器 (ContainerExecutor) - Phase 4

业务定义：
- 容器执行器负责在隔离的容器环境中执行 Python 代码
- 支持配置镜像、超时、内存限制等参数
- 返回执行结果包含标准输出、错误和日志

设计原则：
- 隔离性：代码在独立容器中执行
- 安全性：限制资源使用和执行时间
- 可观测性：记录执行日志和指标
- 可替换性：支持 Mock 执行器用于测试

使用示例：
    config = ContainerConfig(image="python:3.11", timeout=60)
    executor = ContainerExecutor()
    result = await executor.execute_async(code="print('Hello')", config=config)
"""

from dataclasses import dataclass, field
from typing import Any

# 默认容器配置
DEFAULT_CONTAINER_CONFIG: dict[str, Any] = {
    "image": "python:3.11-slim",
    "timeout": 60,
    "memory_limit": "256m",
    "cpu_limit": "1.0",
    "working_dir": "/app",
}


@dataclass
class ContainerConfig:
    """容器配置

    属性：
        image: Docker 镜像名称
        timeout: 执行超时（秒）
        memory_limit: 内存限制（如 "256m", "1g"）
        cpu_limit: CPU 限制（如 "1.0", "0.5"）
        working_dir: 工作目录
        environment: 环境变量字典
        pip_packages: 需要安装的 pip 包列表
        volumes: 挂载卷配置
    """

    image: str = "python:3.11-slim"
    timeout: int = 60
    memory_limit: str = "256m"
    cpu_limit: str = "1.0"
    working_dir: str = "/app"
    environment: dict[str, str] = field(default_factory=dict)
    pip_packages: list[str] = field(default_factory=list)
    volumes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "image": self.image,
            "timeout": self.timeout,
            "memory_limit": self.memory_limit,
            "cpu_limit": self.cpu_limit,
            "working_dir": self.working_dir,
            "environment": self.environment,
            "pip_packages": self.pip_packages,
            "volumes": self.volumes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContainerConfig":
        """从字典反序列化"""
        return cls(
            image=data.get("image", "python:3.11-slim"),
            timeout=data.get("timeout", 60),
            memory_limit=data.get("memory_limit", "256m"),
            cpu_limit=data.get("cpu_limit", "1.0"),
            working_dir=data.get("working_dir", "/app"),
            environment=data.get("environment", {}),
            pip_packages=data.get("pip_packages", []),
            volumes=data.get("volumes", {}),
        )


@dataclass
class ContainerExecutionResult:
    """容器执行结果

    属性：
        success: 是否执行成功
        stdout: 标准输出
        stderr: 标准错误
        exit_code: 退出码
        execution_time: 执行时间（秒）
        logs: 执行日志列表
        output_data: 输出数据（如返回值）
    """

    success: bool = False
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    execution_time: float = 0.0
    logs: list[dict[str, Any]] = field(default_factory=list)
    output_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "logs": self.logs,
            "output_data": self.output_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContainerExecutionResult":
        """从字典反序列化"""
        return cls(
            success=data.get("success", False),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_code=data.get("exit_code", -1),
            execution_time=data.get("execution_time", 0.0),
            logs=data.get("logs", []),
            output_data=data.get("output_data", {}),
        )


class ContainerExecutor:
    """容器执行器

    负责在 Docker 容器中执行 Python 代码。

    使用示例：
        executor = ContainerExecutor()
        if executor.is_available():
            result = await executor.execute_async(code, config)
    """

    def __init__(self, docker_client: Any = None):
        """初始化容器执行器

        参数：
            docker_client: Docker 客户端（可选，用于依赖注入）
        """
        self._docker_client = docker_client
        self._is_available: bool | None = None

    def is_available(self) -> bool:
        """检查容器执行环境是否可用

        返回：
            是否可用
        """
        if self._is_available is not None:
            return self._is_available

        try:
            import docker

            client = self._docker_client or docker.from_env()
            client.ping()
            self._is_available = True
        except Exception:
            self._is_available = False

        return self._is_available

    def execute(
        self,
        code: str,
        config: ContainerConfig | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> ContainerExecutionResult:
        """同步执行代码

        参数：
            code: 要执行的 Python 代码
            config: 容器配置
            inputs: 输入数据

        返回：
            执行结果
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果在异步环境中，创建新任务
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.execute_async(code, config, inputs),
                    )
                    return future.result()
            return loop.run_until_complete(self.execute_async(code, config, inputs))
        except RuntimeError:
            return asyncio.run(self.execute_async(code, config, inputs))

    async def execute_async(
        self,
        code: str,
        config: ContainerConfig | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> ContainerExecutionResult:
        """异步执行代码

        参数：
            code: 要执行的 Python 代码
            config: 容器配置
            inputs: 输入数据

        返回：
            执行结果
        """
        import time

        start_time = time.time()
        config = config or ContainerConfig()
        inputs = inputs or {}

        if not self.is_available():
            return ContainerExecutionResult(
                success=False,
                stderr="Docker is not available",
                exit_code=1,
                execution_time=time.time() - start_time,
            )

        try:
            import docker

            client = self._docker_client or docker.from_env()

            # 准备代码文件内容
            code_with_inputs = self._prepare_code(code, inputs)

            # 创建并运行容器
            container = client.containers.run(
                image=config.image,
                command=["python", "-c", code_with_inputs],
                detach=True,
                mem_limit=config.memory_limit,
                cpu_period=100000,
                cpu_quota=int(float(config.cpu_limit) * 100000),
                environment=config.environment,
                working_dir=config.working_dir,
            )

            # 等待容器完成
            try:
                result = container.wait(timeout=config.timeout)
                exit_code = result.get("StatusCode", -1)

                # 获取日志
                stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
                stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

            finally:
                # 清理容器
                container.remove(force=True)

            execution_time = time.time() - start_time

            return ContainerExecutionResult(
                success=(exit_code == 0),
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time=execution_time,
                logs=[
                    {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "level": "INFO",
                        "message": f"Container execution completed with exit code {exit_code}",
                    }
                ],
            )

        except Exception as e:
            return ContainerExecutionResult(
                success=False,
                stderr=str(e),
                exit_code=1,
                execution_time=time.time() - start_time,
            )

    def _prepare_code(self, code: str, inputs: dict[str, Any]) -> str:
        """准备要执行的代码

        将输入数据注入到代码中。

        参数：
            code: 原始代码
            inputs: 输入数据

        返回：
            准备好的代码
        """
        import json

        input_code = f"_inputs = {json.dumps(inputs)}\n"
        return input_code + code


class MockContainerExecutor(ContainerExecutor):
    """Mock 容器执行器

    用于测试，不依赖真实 Docker 环境。
    """

    def __init__(self, simulate_error: bool = False, mock_output: str = "Mock output"):
        """初始化 Mock 执行器

        参数：
            simulate_error: 是否模拟错误
            mock_output: 模拟的输出内容
        """
        super().__init__()
        self.simulate_error = simulate_error
        self.mock_output = mock_output
        self._is_available = True

    def is_available(self) -> bool:
        """Mock 始终可用"""
        return True

    async def execute_async(
        self,
        code: str,
        config: ContainerConfig | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> ContainerExecutionResult:
        """Mock 异步执行

        参数：
            code: 要执行的代码
            config: 容器配置
            inputs: 输入数据

        返回：
            模拟的执行结果
        """
        import time

        config = config or ContainerConfig()

        # 模拟执行时间
        execution_time = 0.1

        if self.simulate_error:
            return ContainerExecutionResult(
                success=False,
                stdout="",
                stderr="Simulated error",
                exit_code=1,
                execution_time=execution_time,
                logs=[
                    {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "level": "ERROR",
                        "message": "Simulated error occurred",
                    }
                ],
            )

        # 尝试从代码中提取 print 内容作为输出
        stdout = self.mock_output
        if "print(" in code:
            # 简单提取 print 内容
            import re

            match = re.search(r"print\(['\"](.+?)['\"]\)", code)
            if match:
                stdout = match.group(1)

        return ContainerExecutionResult(
            success=True,
            stdout=stdout,
            stderr="",
            exit_code=0,
            execution_time=execution_time,
            logs=[
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "level": "INFO",
                    "message": "Mock execution completed",
                }
            ],
        )

    async def execute_with_events(
        self,
        code: str,
        config: ContainerConfig | None = None,
        event_bus: Any = None,
        node_id: str = "",
        workflow_id: str = "",
        inputs: dict[str, Any] | None = None,
    ) -> ContainerExecutionResult:
        """带事件发布的异步执行

        执行代码并在开始和完成时发布事件到 EventBus。

        参数：
            code: 要执行的代码
            config: 容器配置
            event_bus: 事件总线
            node_id: 节点ID
            workflow_id: 工作流ID
            inputs: 输入数据

        返回：
            执行结果
        """
        import time
        from uuid import uuid4

        config = config or ContainerConfig()
        container_id = f"mock_container_{uuid4().hex[:8]}"

        # 发布开始事件
        if event_bus:
            from src.domain.agents.container_events import (
                ContainerExecutionStartedEvent,
            )

            start_event = ContainerExecutionStartedEvent(
                source="mock_container_executor",
                container_id=container_id,
                node_id=node_id,
                workflow_id=workflow_id,
                image=config.image,
                code_preview=code[:100] if len(code) > 100 else code,
            )
            await event_bus.publish(start_event)

        # 执行代码
        result = await self.execute_async(code, config, inputs)

        # 发布完成事件
        if event_bus:
            from src.domain.agents.container_events import (
                ContainerExecutionCompletedEvent,
            )

            completed_event = ContainerExecutionCompletedEvent(
                source="mock_container_executor",
                container_id=container_id,
                node_id=node_id,
                workflow_id=workflow_id,
                success=result.success,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                execution_time=result.execution_time,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            await event_bus.publish(completed_event)

        return result


# 导出
__all__ = [
    "DEFAULT_CONTAINER_CONFIG",
    "ContainerConfig",
    "ContainerExecutionResult",
    "ContainerExecutor",
    "MockContainerExecutor",
]
