"""Default Container Executor - Infrastructure Layer

提供带沙箱回退的默认容器执行器实现。

Architecture:
    Infrastructure Layer → Domain Layer (via Ports)

Author: Claude Code
Date: 2025-12-17 (P1-Cleanup: Move from Domain to Infrastructure)
"""

from __future__ import annotations

from typing import Any


class DefaultContainerExecutor:
    """默认容器执行器（带沙箱回退）

    如果 Docker 不可用，自动回退到沙箱执行。

    Architecture Note:
        此类位于 Infrastructure 层，因为它组装了具体的实现（InfraContainerExecutor + SandboxExecutor）。
        通过 Infrastructure 侧注册工厂注入到 Domain（见 src/infrastructure/executors/__init__.py）。

    使用示例：
        from src.infrastructure.executors.default_container_executor import DefaultContainerExecutor

        executor = DefaultContainerExecutor()
        result = await executor.execute_async(code, config, inputs)
    """

    def __init__(self) -> None:
        from src.domain.agents.container_executor import ContainerExecutor
        from src.infrastructure.executors.container_executor import (
            ContainerExecutor as InfraContainerExecutor,
        )

        self._container_executor = ContainerExecutor(InfraContainerExecutor())
        self._fallback_executor: Any = None

    def is_available(self) -> bool:
        """检查是否可用（总是返回 True，因为有回退）"""
        return True

    @property
    def fallback_executor(self) -> Any:
        """获取回退执行器"""
        if self._fallback_executor is None:
            from src.domain.services.sandbox_executor import SandboxExecutor

            self._fallback_executor = SandboxExecutor()
        return self._fallback_executor

    async def execute_async(
        self,
        code: str,
        config: Any = None,
        inputs: dict[str, Any] | None = None,
    ) -> Any:
        """异步执行代码

        参数：
            code: 要执行的代码
            config: 容器配置
            inputs: 输入数据

        返回：
            执行结果
        """
        from src.domain.agents.container_executor import ContainerExecutionResult

        # 尝试使用容器执行器
        if self._container_executor.is_available():
            return await self._container_executor.execute_async(code, config, inputs)

        # 回退到沙箱
        try:
            from src.domain.services.sandbox_executor import SandboxConfig

            sandbox_config = SandboxConfig(timeout_seconds=config.timeout if config else 30)
            result = self.fallback_executor.execute(
                code=code,
                config=sandbox_config,
                input_data=inputs or {},
            )
            return ContainerExecutionResult(
                success=result.success,
                stdout=result.stdout if hasattr(result, "stdout") else "",
                stderr=result.stderr if hasattr(result, "stderr") else "",
                exit_code=0 if result.success else 1,
                execution_time=result.execution_time if hasattr(result, "execution_time") else 0.0,
                output_data=result.output_data if hasattr(result, "output_data") else {},
            )
        except Exception as e:
            return ContainerExecutionResult(
                success=False,
                stderr=str(e),
                exit_code=1,
            )
