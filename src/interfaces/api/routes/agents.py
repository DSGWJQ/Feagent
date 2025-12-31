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
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.task_repository import TaskRepository
from src.domain.ports.workflow_repository import WorkflowRepository
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
from src.interfaces.api.dto import AgentResponse, CreateAgentRequest

# 创建路由器
router = APIRouter()


def get_agent_repository(
    container: ApiContainer = Depends(get_container),
    session: Session = Depends(get_db_session),
) -> AgentRepository:
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
    return container.agent_repository(session)


def get_task_repository(
    container: ApiContainer = Depends(get_container),
    session: Session = Depends(get_db_session),
) -> TaskRepository:
    """获取 Task Repository

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
        SQLAlchemyTaskRepository 实例
    """
    return container.task_repository(session)


def get_workflow_repository(
    container: ApiContainer = Depends(get_container),
    session: Session = Depends(get_db_session),
) -> WorkflowRepository:
    """获取 Workflow Repository

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
        SQLAlchemyWorkflowRepository 实例
    """
    return container.workflow_repository(session)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    request: CreateAgentRequest,
    agent_repository: AgentRepository = Depends(get_agent_repository),
    task_repository: TaskRepository = Depends(get_task_repository),
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
    session: Session = Depends(get_db_session),
) -> AgentResponse:
    """创建 Agent

    业务场景：用户通过 API 创建 Agent，自动生成工作流（Tasks）

    请求体：
    - start: 任务起点描述（必填）
    - goal: 任务目的描述（必填）
    - name: Agent 名称（可选）

    响应：
    - 201 Created: 成功创建，返回 Agent 信息和生成的 Tasks
    - 422 Unprocessable Entity: 请求数据验证失败
    - 500 Internal Server Error: 服务器内部错误

    为什么返回 201？
    - RESTful 规范：创建资源成功返回 201
    - 201 表示资源已创建，200 表示操作成功

    为什么使用 response_model？
    - FastAPI 自动序列化响应
    - 自动生成 OpenAPI 文档
    - 类型安全

    MVP 功能：
    - 创建 Agent 时，自动调用 LLM 生成工作流（Tasks）
    - 前端可以立即看到生成的任务列表

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
    ...     "created_at": "2025-11-16T10:00:00",
    ...     "tasks": [
    ...         {
    ...             "id": "task-1",
    ...             "agent_id": "agent-123",
    ...             "name": "读取 CSV 文件",
    ...             "description": "使用 pandas 读取 CSV 文件到 DataFrame",
    ...             "status": "pending",
    ...             "created_at": "2025-11-16T10:00:01"
    ...         },
    ...         ...
    ...     ]
    ... }
    """
    try:
        # 步骤 1: 创建 Use Case（注入所有 Repository）
        # 为什么注入 TaskRepository 和 WorkflowRepository？
        # - MVP 功能：创建 Agent 时自动生成 Tasks 和 Workflow
        # - Use Case 需要 TaskRepository 来保存 Tasks
        # - Use Case 需要 WorkflowRepository 来保存 Workflow
        use_case = CreateAgentUseCase(
            agent_repository=agent_repository,
            task_repository=task_repository,
            workflow_repository=workflow_repository,  # 新增：注入 WorkflowRepository
        )

        # 步骤 2: 转换 DTO → Use Case Input
        input_data = CreateAgentInput(
            start=request.start,
            goal=request.goal,
            name=request.name,
        )

        # 步骤 3: 执行 Use Case（自动生成 Tasks 和 Workflow）
        # Use Case 现在返回 (Agent, workflow_id)
        agent, workflow_id = use_case.execute(input_data)

        # 步骤 4: 提交事务
        # 为什么需要 commit？
        # - Repository 的 save() 方法不会自动提交
        # - 需要手动提交事务才能持久化到数据库
        # - 包括 Agent、Tasks 和 Workflow 的保存
        session.commit()

        # 步骤 5: 查询生成的 Tasks
        # 为什么需要查询？
        # - Use Case 返回 workflow_id，但不返回 Tasks
        # - 需要查询数据库获取生成的 Tasks（用于响应）
        tasks = task_repository.find_by_agent_id(agent.id)

        # 步骤 6: 转换 Domain Entity → DTO（包含 Tasks 和 workflow_id）
        return AgentResponse.from_entity(agent, tasks=tasks, workflow_id=workflow_id)

    except DomainError as e:
        # 业务规则违反：回滚事务
        session.rollback()
        # 业务规则违反：返回 400 Bad Request
        # 例如：start 或 goal 为空
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        # 其他异常：回滚事务并返回 500 Internal Server Error
        # 例如：数据库连接失败、LLM 调用失败
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建 Agent 失败: {str(e)}",
        ) from e


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: str,
    agent_repository: AgentRepository = Depends(get_agent_repository),
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
    agent_repository: AgentRepository = Depends(get_agent_repository),
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
