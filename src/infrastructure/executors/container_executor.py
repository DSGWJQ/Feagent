"""容器执行器 (ContainerExecutor) - Infrastructure

基础设施实现：
- 使用 Docker 容器执行 Python 代码
- 支持镜像/超时/资源限制等参数
"""

from __future__ import annotations

import time
from typing import Any

from src.domain.agents.container_executor import ContainerConfig, ContainerExecutionResult
from src.domain.ports.container_executor_port import ContainerExecutorPort


class ContainerExecutor(ContainerExecutorPort):
    """Docker 容器执行器（Infrastructure Adapter）"""

    def __init__(self, docker_client: Any = None):
        """初始化容器执行器

        参数：
            docker_client: Docker 客户端（可选，用于依赖注入）
        """
        self._docker_client = docker_client
        self._is_available: bool | None = None

    def is_available(self) -> bool:
        """检查容器执行环境是否可用"""
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
        """同步执行代码"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
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
        """异步执行代码"""
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

            code_with_inputs = self._prepare_code(code, inputs)

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

            try:
                result = container.wait(timeout=config.timeout)
                exit_code = result.get("StatusCode", -1)

                stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
                stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

            finally:
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
        """准备要执行的代码（注入 inputs）"""
        import json

        input_code = f"_inputs = {json.dumps(inputs)}\n"
        return input_code + code


class MockContainerExecutor(ContainerExecutorPort):
    """Mock 容器执行器（用于测试，不依赖 Docker）"""

    def __init__(self, simulate_error: bool = False, mock_output: str = "Mock output"):
        self.simulate_error = simulate_error
        self.mock_output = mock_output

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        code: str,
        config: ContainerConfig | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> ContainerExecutionResult:
        import asyncio

        return asyncio.run(self.execute_async(code, config, inputs))

    async def execute_async(
        self,
        code: str,
        config: ContainerConfig | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> ContainerExecutionResult:
        config = config or ContainerConfig()
        _ = inputs or {}

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

        stdout = self.mock_output
        if "print(" in code:
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


__all__ = ["ContainerExecutor", "MockContainerExecutor"]
