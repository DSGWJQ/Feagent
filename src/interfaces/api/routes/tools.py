"""Tools 路由

定义 Tool 相关的 API 端点：
- POST /api/tools - 创建工具
- GET /api/tools - 列出所有工具
- GET /api/tools/{tool_id} - 获取工具详情
- PUT /api/tools/{tool_id} - 更新工具
- DELETE /api/tools/{tool_id} - 删除工具
- POST /api/tools/{tool_id}/publish - 发布工具
- POST /api/tools/{tool_id}/deprecate - 废弃工具

设计原则：
1. 路由只负责 HTTP 层的事情
2. 不包含业务逻辑
3. 依赖注入
4. 异常处理
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.domain.exceptions import DomainError, NotFoundError
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.tool_repository import (
    SQLAlchemyToolRepository,
)
from src.interfaces.api.dto import (
    CreateToolRequest,
    DeprecateToolRequest,
    PublishToolRequest,
    ToolListResponse,
    ToolResponse,
    UpdateToolRequest,
)
from src.domain.entities.tool import Tool, ToolParameter

# 创建路由器
router = APIRouter(prefix="/tools", tags=["tools"])


def get_tool_repository(session: Session = Depends(get_db_session)) -> SQLAlchemyToolRepository:
    """获取 Tool Repository - 依赖注入函数"""
    return SQLAlchemyToolRepository(session)


def _tool_to_response(tool: Tool) -> ToolResponse:
    """将 Tool 实体转换为 Response DTO"""
    from src.interfaces.api.dto import ToolParameterDTO

    parameters = [
        ToolParameterDTO(
            name=p.name,
            type=p.type,
            description=p.description,
            required=p.required,
            default=p.default,
            enum=p.enum,
        )
        for p in tool.parameters
    ]

    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        category=tool.category.value,
        status=tool.status.value,
        version=tool.version,
        parameters=parameters,
        returns=tool.returns,
        implementation_type=tool.implementation_type,
        implementation_config=tool.implementation_config,
        author=tool.author,
        tags=tool.tags,
        icon=tool.icon,
        usage_count=tool.usage_count,
        last_used_at=tool.last_used_at,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
        published_at=tool.published_at,
    )


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
def create_tool(
    request: CreateToolRequest,
    tool_repository: SQLAlchemyToolRepository = Depends(get_tool_repository),
    session: Session = Depends(get_db_session),
) -> ToolResponse:
    """创建工具

    业务流程：
    1. 验证输入数据（Pydantic 自动验证）
    2. 创建 Tool 实体（验证业务规则）
    3. 保存到数据库
    4. 返回工具信息

    异常处理：
    - 400: 业务规则违反（name 为空等）
    - 500: 数据库错误
    """
    try:
        # 将请求转换为参数列表
        parameters = []
        if request.parameters:
            for param_dto in request.parameters:
                parameters.append(
                    ToolParameter(
                        name=param_dto.name,
                        type=param_dto.type,
                        description=param_dto.description,
                        required=param_dto.required,
                        default=param_dto.default,
                        enum=param_dto.enum,
                    )
                )

        # 创建 Tool 实体
        tool = Tool.create(
            name=request.name,
            description=request.description,
            category=ToolCategory(request.category),
            author=request.author,
            parameters=parameters,
            returns=request.returns or {},
            implementation_type=request.implementation_type or "builtin",
            implementation_config=request.implementation_config or {},
            tags=request.tags or [],
            icon=request.icon,
        )

        # 保存到数据库
        tool_repository.save(tool)
        session.commit()

        return _tool_to_response(tool)

    except DomainError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=ToolListResponse)
def list_tools(
    category: str | None = None,
    status: str | None = None,
    tool_repository: SQLAlchemyToolRepository = Depends(get_tool_repository),
) -> ToolListResponse:
    """列出所有工具

    查询参数：
    - category: 按分类过滤（可选）
    - status: 按状态过滤（可选，当前未实现）

    返回：
    - tools: 工具列表
    - total: 总数量
    """
    try:
        if category:
            tools = tool_repository.find_by_category(category)
        else:
            tools = tool_repository.find_all()

        return ToolListResponse(
            tools=[_tool_to_response(tool) for tool in tools],
            total=len(tools),
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{tool_id}", response_model=ToolResponse)
def get_tool(
    tool_id: str,
    tool_repository: SQLAlchemyToolRepository = Depends(get_tool_repository),
) -> ToolResponse:
    """获取工具详情"""
    try:
        tool = tool_repository.get_by_id(tool_id)
        return _tool_to_response(tool)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{tool_id}", response_model=ToolResponse)
def update_tool(
    tool_id: str,
    request: UpdateToolRequest,
    tool_repository: SQLAlchemyToolRepository = Depends(get_tool_repository),
    session: Session = Depends(get_db_session),
) -> ToolResponse:
    """更新工具"""
    try:
        tool = tool_repository.get_by_id(tool_id)

        # 更新字段
        if request.name is not None:
            tool.name = request.name
        if request.description is not None:
            tool.description = request.description
        if request.parameters is not None:
            tool.parameters = [
                ToolParameter(
                    name=p.name,
                    type=p.type,
                    description=p.description,
                    required=p.required,
                    default=p.default,
                    enum=p.enum,
                )
                for p in request.parameters
            ]
        if request.returns is not None:
            tool.returns = request.returns
        if request.implementation_type is not None:
            tool.implementation_type = request.implementation_type
        if request.implementation_config is not None:
            tool.implementation_config = request.implementation_config
        if request.tags is not None:
            tool.tags = request.tags
        if request.icon is not None:
            tool.icon = request.icon

        # 更新时间戳
        from datetime import UTC, datetime
        tool.updated_at = datetime.now(UTC)

        # 保存到数据库
        tool_repository.save(tool)
        session.commit()

        return _tool_to_response(tool)

    except NotFoundError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DomainError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(
    tool_id: str,
    tool_repository: SQLAlchemyToolRepository = Depends(get_tool_repository),
    session: Session = Depends(get_db_session),
) -> None:
    """删除工具"""
    try:
        # 验证工具存在
        tool_repository.get_by_id(tool_id)

        # 删除
        tool_repository.delete(tool_id)
        session.commit()

    except NotFoundError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{tool_id}/publish", response_model=ToolResponse)
def publish_tool(
    tool_id: str,
    request: PublishToolRequest,
    tool_repository: SQLAlchemyToolRepository = Depends(get_tool_repository),
    session: Session = Depends(get_db_session),
) -> ToolResponse:
    """发布工具

    业务规则：
    - 只有 TESTING 状态的工具才能发布
    - 发布后状态变为 PUBLISHED
    """
    try:
        tool = tool_repository.get_by_id(tool_id)

        # 验证状态
        if tool.status != ToolStatus.TESTING:
            raise DomainError("只有测试通过的工具才能发布")

        # 发布
        tool.publish()

        # 保存到数据库
        tool_repository.save(tool)
        session.commit()

        return _tool_to_response(tool)

    except NotFoundError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DomainError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{tool_id}/deprecate", response_model=ToolResponse)
def deprecate_tool(
    tool_id: str,
    request: DeprecateToolRequest,
    tool_repository: SQLAlchemyToolRepository = Depends(get_tool_repository),
    session: Session = Depends(get_db_session),
) -> ToolResponse:
    """废弃工具"""
    try:
        tool = tool_repository.get_by_id(tool_id)

        # 废弃
        tool.deprecate(request.reason)

        # 保存到数据库
        tool_repository.save(tool)
        session.commit()

        return _tool_to_response(tool)

    except NotFoundError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
