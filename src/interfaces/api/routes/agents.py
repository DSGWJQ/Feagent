"""Agents 路由

定义 Agent 相关的 API 端点：
- POST /api/agents - 创建 Agent
- GET /api/agents/{id} - 获取 Agent 详情
- GET /api/agents - 列出所有 Agents

设计原则：
1. 路由只负责 HTTP 层的事情：
   - 接收请求（Request）
   - 调用 Use Case
   - 返回响应（Response）
   - 处理异常（Exception Handling）

2. 不包含业务逻辑：
   - 业务逻辑在 Use Case 中
   - 路由只是薄薄的一层适配器

3. 依赖注入：
   - 使用 FastAPI 的 Depends 进行依赖注入
   - 每个请求创建新的 Repository 和 Use Case

为什么这样设计？
- 关注点分离：HTTP 层和业务逻辑分离
- 可测试性：可以 Mock Use Case 进行测试
- 灵活性：可以轻松切换不同的实现
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application import CreateAgentInput, CreateAgentUseCase
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories import SQLAlchemyAgentRepository
from src.interfaces.api.dto import AgentResponse, CreateAgentRequest

# 创建路由器
router = APIRouter()


def get_agent_repository(session: Session = Depends(get_db_session)) -> SQLAlchemyAgentRepository:
    """获取 Agent Repository

    这是依赖注入函数：
    - FastAPI 会自动调用这个函数
    - 为每个请求创建新的 Repository
    - 使用数据库会话（Session）

    为什么需要这个函数？
    1. 依赖注入：解耦路由和 Repository
    2. 生命周期管理：每个请求有独立的 Repository
    3. 可测试性：测试时可以 Mock 这个函数

    参数：
        session: 数据库会话（由 get_db_session 提供）

    返回：
        SQLAlchemyAgentRepository 实例
    """
    return SQLAlchemyAgentRepository(session)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    request: CreateAgentRequest,
    agent_repository: SQLAlchemyAgentRepository = Depends(get_agent_repository),
) -> AgentResponse:
    """创建 Agent

    业务场景：用户通过 API 创建 Agent

    请求体：
    - start: 任务起点描述（必填）
    - goal: 任务目的描述（必填）
    - name: Agent 名称（可选）

    响应：
    - 201 Created: 成功创建，返回 Agent 信息
    - 422 Unprocessable Entity: 请求数据验证失败
    - 500 Internal Server Error: 服务器内部错误

    为什么返回 201？
    - RESTful 规范：创建资源成功返回 201
    - 201 表示资源已创建，200 表示操作成功

    为什么使用 response_model？
    - FastAPI 自动序列化响应
    - 自动生成 OpenAPI 文档
    - 类型安全

    示例：
    >>> POST /api/agents
    >>> {
    ...     "start": "我有一个 CSV 文件",
    ...     "goal": "分析销售数据",
    ...     "name": "销售分析 Agent"
    ... }
    >>>
    >>> 201 Created
    >>> {
    ...     "id": "agent-123",
    ...     "start": "我有一个 CSV 文件",
    ...     "goal": "分析销售数据",
    ...     "name": "销售分析 Agent",
    ...     "status": "active",
    ...     "created_at": "2025-11-16T10:00:00"
    ... }
    """
    try:
        # 步骤 1: 创建 Use Case
        # 为什么每次都创建新的 Use Case？
        # - Use Case 是无状态的，可以每次创建
        # - 避免共享状态，防止并发问题
        # - 符合函数式编程思想
        use_case = CreateAgentUseCase(agent_repository=agent_repository)

        # 步骤 2: 转换 DTO → Use Case Input
        # 为什么需要转换？
        # - DTO 是 API 层的概念
        # - Use Case Input 是 Application 层的概念
        # - 关注点分离：不同层使用不同的数据结构
        input_data = CreateAgentInput(
            start=request.start,
            goal=request.goal,
            name=request.name,
        )

        # 步骤 3: 执行 Use Case
        # 为什么不捕获异常？
        # - 异常会被下面的 except 捕获
        # - 统一异常处理，避免重复代码
        agent = use_case.execute(input_data)

        # 步骤 4: 转换 Domain Entity → DTO
        # 为什么需要转换？
        # - Domain Entity 是业务概念
        # - DTO 是 API 响应格式
        # - 关注点分离：Domain 层不知道 API 的存在
        return AgentResponse.from_entity(agent)

    except DomainError as e:
        # 业务规则违反：返回 400 Bad Request
        # 例如：start 或 goal 为空
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        # 其他异常：返回 500 Internal Server Error
        # 例如：数据库连接失败
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建 Agent 失败: {str(e)}",
        ) from e


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: str,
    agent_repository: SQLAlchemyAgentRepository = Depends(get_agent_repository),
) -> AgentResponse:
    """获取 Agent 详情

    业务场景：用户查看 Agent 详情

    路径参数：
    - agent_id: Agent ID

    响应：
    - 200 OK: 成功获取，返回 Agent 信息
    - 404 Not Found: Agent 不存在
    - 500 Internal Server Error: 服务器内部错误

    为什么不使用 Use Case？
    - 这是简单的查询操作，不涉及业务逻辑
    - 直接调用 Repository 更简单
    - 符合 CQRS 模式：查询不需要经过 Use Case

    示例：
    >>> GET /api/agents/agent-123
    >>>
    >>> 200 OK
    >>> {
    ...     "id": "agent-123",
    ...     "start": "我有一个 CSV 文件",
    ...     "goal": "分析销售数据",
    ...     "name": "销售分析 Agent",
    ...     "status": "active",
    ...     "created_at": "2025-11-16T10:00:00"
    ... }
    """
    try:
        # 步骤 1: 查询 Agent
        # 使用 get_by_id()：不存在时抛出 NotFoundError
        agent = agent_repository.get_by_id(agent_id)

        # 步骤 2: 转换 Domain Entity → DTO
        return AgentResponse.from_entity(agent)

    except NotFoundError as e:
        # Agent 不存在：返回 404 Not Found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        # 其他异常：返回 500 Internal Server Error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 Agent 失败: {str(e)}",
        ) from e


@router.get("", response_model=list[AgentResponse])
def list_agents(
    agent_repository: SQLAlchemyAgentRepository = Depends(get_agent_repository),
) -> list[AgentResponse]:
    """列出所有 Agents

    业务场景：用户查看所有 Agents

    响应：
    - 200 OK: 成功获取，返回 Agent 列表（可能为空）
    - 500 Internal Server Error: 服务器内部错误

    为什么不使用 Use Case？
    - 这是简单的查询操作，不涉及业务逻辑
    - 直接调用 Repository 更简单
    - 符合 CQRS 模式：查询不需要经过 Use Case

    未来扩展：
    - 分页：limit、offset
    - 过滤：status、created_at
    - 排序：order_by

    示例：
    >>> GET /api/agents
    >>>
    >>> 200 OK
    >>> [
    ...     {
    ...         "id": "agent-123",
    ...         "start": "起点1",
    ...         "goal": "目的1",
    ...         "name": "Agent 1",
    ...         "status": "active",
    ...         "created_at": "2025-11-16T10:00:00"
    ...     },
    ...     {
    ...         "id": "agent-456",
    ...         "start": "起点2",
    ...         "goal": "目的2",
    ...         "name": "Agent 2",
    ...         "status": "active",
    ...         "created_at": "2025-11-16T11:00:00"
    ...     }
    ... ]
    """
    try:
        # 步骤 1: 查询所有 Agents
        agents = agent_repository.find_all()

        # 步骤 2: 转换 Domain Entity → DTO
        # 使用列表推导式批量转换
        return [AgentResponse.from_entity(agent) for agent in agents]

    except Exception as e:
        # 异常：返回 500 Internal Server Error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出 Agents 失败: {str(e)}",
        ) from e
