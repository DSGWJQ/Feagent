"""Application 层用例 - 业务逻辑编排

为什么需要 Use Case？
1. 业务逻辑编排：协调 Domain 实体、Repository、Domain Service
2. 事务边界：定义事务的开始和结束
3. 输入输出转换：接收输入参数，返回结果
4. 权限校验：检查用户权限（未来扩展）

设计原则：
- 单一职责：每个 Use Case 只做一件事
- 依赖倒置：依赖 Port 接口，不依赖具体实现
- 可测试性：使用 Mock Repository 进行单元测试
"""

from src.application.use_cases.create_agent import CreateAgentInput, CreateAgentUseCase
from src.application.use_cases.execute_run import ExecuteRunInput, ExecuteRunUseCase

__all__ = [
    "CreateAgentUseCase",
    "CreateAgentInput",
    "ExecuteRunUseCase",
    "ExecuteRunInput",
]
