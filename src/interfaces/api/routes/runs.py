"""Runs 路由

定义 Run 相关的 API 端点：
- POST /api/agents/{agent_id}/runs - 触发 Run
- GET /api/runs/{id} - 获取 Run 详情

设计原则：
1. 路由只负责 HTTP 层的事情
2. 不包含业务逻辑
3. 依赖注入

为什么这样设计？
- 关注点分离：HTTP 层和业务逻辑分离
- 可测试性：可以 Mock Use Case 进行测试
- 灵活性：可以轻松切换不同的实现
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application import ExecuteRunInput, ExecuteRunUseCase
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyRunRepository,
)
from src.interfaces.api.dto import RunResponse

# 创建路由器
router = APIRouter()


def get_agent_repository(session: Session = Depends(get_db_session)) -> SQLAlchemyAgentRepository:
    """获取 Agent Repository

    依赖注入函数：为每个请求创建新的 Repository
    """
    return SQLAlchemyAgentRepository(session)


def get_run_repository(session: Session = Depends(get_db_session)) -> SQLAlchemyRunRepository:
    """获取 Run Repository

    依赖注入函数：为每个请求创建新的 Repository
    """
    return SQLAlchemyRunRepository(session)


@router.post("/{agent_id}/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def execute_run(
    agent_id: str,
    agent_repository: SQLAlchemyAgentRepository = Depends(get_agent_repository),
    run_repository: SQLAlchemyRunRepository = Depends(get_run_repository),
) -> RunResponse:
    """触发 Run

    业务场景：用户触发 Agent 执行

    路径参数：
    - agent_id: Agent ID

    请求体：
    - 当前为空（未来可能添加 input_data）

    响应：
    - 201 Created: 成功触发，返回 Run 信息
    - 404 Not Found: Agent 不存在
    - 500 Internal Server Error: 服务器内部错误

    为什么返回 201？
    - RESTful 规范：创建资源成功返回 201
    - Run 是新创建的资源

    为什么需要两个 Repository？
    - ExecuteRunUseCase 需要 AgentRepository 和 RunRepository
    - AgentRepository：验证 Agent 是否存在
    - RunRepository：保存 Run

    示例：
    >>> POST /api/agents/agent-123/runs
    >>> {}
    >>>
    >>> 201 Created
    >>> {
    ...     "id": "run-456",
    ...     "agent_id": "agent-123",
    ...     "status": "succeeded",
    ...     "created_at": "2025-11-16T10:00:00",
    ...     "started_at": "2025-11-16T10:00:01",
    ...     "finished_at": "2025-11-16T10:00:02",
    ...     "error": null
    ... }
    """
    try:
        # 步骤 1: 创建 Use Case
        # 为什么需要两个 Repository？
        # - ExecuteRunUseCase 需要验证 Agent 存在
        # - ExecuteRunUseCase 需要保存 Run
        use_case = ExecuteRunUseCase(
            agent_repository=agent_repository,
            run_repository=run_repository,
        )

        # 步骤 2: 转换 DTO → Use Case Input
        # agent_id 从路径参数获取
        input_data = ExecuteRunInput(agent_id=agent_id)

        # 步骤 3: 执行 Use Case
        # Use Case 会：
        # 1. 验证 Agent 存在
        # 2. 创建 Run
        # 3. 启动 Run
        # 4. 执行业务逻辑（当前简化为直接成功）
        # 5. 完成 Run
        run = use_case.execute(input_data)

        # 步骤 4: 转换 Domain Entity → DTO
        return RunResponse.from_entity(run)

    except NotFoundError as e:
        # Agent 不存在：返回 404 Not Found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except DomainError as e:
        # 业务规则违反：返回 400 Bad Request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        # 其他异常：返回 500 Internal Server Error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行 Run 失败: {str(e)}",
        ) from e


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    run_repository: SQLAlchemyRunRepository = Depends(get_run_repository),
) -> RunResponse:
    """获取 Run 详情

    业务场景：用户查看 Run 详情

    路径参数：
    - run_id: Run ID

    响应：
    - 200 OK: 成功获取，返回 Run 信息
    - 404 Not Found: Run 不存在
    - 500 Internal Server Error: 服务器内部错误

    为什么不使用 Use Case？
    - 这是简单的查询操作，不涉及业务逻辑
    - 直接调用 Repository 更简单
    - 符合 CQRS 模式：查询不需要经过 Use Case

    示例：
    >>> GET /api/runs/run-456
    >>>
    >>> 200 OK
    >>> {
    ...     "id": "run-456",
    ...     "agent_id": "agent-123",
    ...     "status": "succeeded",
    ...     "created_at": "2025-11-16T10:00:00",
    ...     "started_at": "2025-11-16T10:00:01",
    ...     "finished_at": "2025-11-16T10:00:02",
    ...     "error": null
    ... }
    """
    try:
        # 步骤 1: 查询 Run
        # 使用 get_by_id()：不存在时抛出 NotFoundError
        run = run_repository.get_by_id(run_id)

        # 步骤 2: 转换 Domain Entity → DTO
        return RunResponse.from_entity(run)

    except NotFoundError as e:
        # Run 不存在：返回 404 Not Found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        # 其他异常：返回 500 Internal Server Error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 Run 失败: {str(e)}",
        ) from e
