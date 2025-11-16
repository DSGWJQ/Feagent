"""应用层 - 用例编排、事务边界、UoW

Application 层职责：
1. 用例编排：协调 Domain 实体、Repository、Domain Service
2. 事务边界：定义事务的开始和结束（当前简化）
3. 输入输出转换：接收输入参数，返回结果
4. 权限校验：检查用户权限（未来扩展）

已实现的用例：
- CreateAgentUseCase: 创建 Agent
- ExecuteRunUseCase: 执行 Run

设计原则：
- 单一职责：每个 Use Case 只做一件事
- 依赖倒置：依赖 Port 接口，不依赖具体实现
- 可测试性：使用 Mock Repository 进行单元测试
- 无框架依赖：纯 Python 实现，不依赖 FastAPI 等框架

使用示例：
>>> from src.application import CreateAgentUseCase, CreateAgentInput
>>> from src.infrastructure.database.repositories import SQLAlchemyAgentRepository
>>>
>>> # 创建 Repository
>>> repo = SQLAlchemyAgentRepository(session)
>>>
>>> # 创建 Use Case
>>> use_case = CreateAgentUseCase(agent_repository=repo)
>>>
>>> # 执行用例
>>> input_data = CreateAgentInput(
...     start="我有一个 CSV 文件",
...     goal="分析销售数据",
...     name="销售分析 Agent"
... )
>>> agent = use_case.execute(input_data)
"""

from src.application.use_cases import (
    CreateAgentInput,
    CreateAgentUseCase,
    ExecuteRunInput,
    ExecuteRunUseCase,
)

__all__ = [
    "CreateAgentUseCase",
    "CreateAgentInput",
    "ExecuteRunUseCase",
    "ExecuteRunInput",
]
