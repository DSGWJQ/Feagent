"""Test Seeds 路由 - E2E 测试数据管理 API

端点：
- POST /api/test/workflows/seed - 创建测试 Workflow
- DELETE /api/test/workflows/cleanup - 清理测试 Workflow
- GET /api/test/workflows/fixture-types - 列出可用的 fixture 类型

安全控制：
- 必须携带 X-Test-Mode: true 请求头
- 仅在 enable_test_seed_api=True 时启用（main.py 控制）
- 所有测试数据都标记 test_seed=True

设计原则：
1. 路由只负责 HTTP 层的事情（参数解析、认证、响应格式化）
2. 业务逻辑在 UseCase 层
3. 依赖注入
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.application.use_cases.seed_test_workflow import (
    CleanupTestWorkflowsInput,
    CleanupTestWorkflowsUseCase,
    SeedTestWorkflowInput,
    SeedTestWorkflowUseCase,
)
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_fixtures import WorkflowFixtureFactory
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container

router = APIRouter(prefix="/test", tags=["Test Seeds"])


# ==================== DTO ====================


class SeedWorkflowRequest(BaseModel):
    """创建测试 Workflow 请求"""

    fixture_type: str = Field(..., description="Fixture 类型")
    project_id: str = Field(default="e2e_test_project", description="项目 ID")
    custom_metadata: dict[str, Any] | None = Field(default=None, description="自定义元数据")
    custom_nodes: list[dict[str, Any]] | None = Field(default=None, description="自定义节点覆盖")


class SeedWorkflowResponse(BaseModel):
    """创建测试 Workflow 响应"""

    workflow_id: str
    project_id: str
    fixture_type: str
    metadata: dict[str, Any]
    cleanup_token: str


class CleanupWorkflowsRequest(BaseModel):
    """清理测试 Workflow 请求"""

    cleanup_tokens: list[str] = Field(default_factory=list, description="清理 token 列表")
    delete_by_source: bool = Field(
        default=False, description="是否删除所有 source='e2e_test' 的 workflow"
    )


class CleanupWorkflowsResponse(BaseModel):
    """清理测试 Workflow 响应"""

    deleted_count: int
    failed: list[str]


class FixtureTypesResponse(BaseModel):
    """Fixture 类型列表响应"""

    fixture_types: list[str]


class ErrorResponse(BaseModel):
    """错误响应"""

    code: str
    message: str
    valid_types: list[str] | None = None


# ==================== 依赖注入 ====================


def get_workflow_repository(
    container: ApiContainer = Depends(get_container),
    session: Session = Depends(get_db_session),
) -> WorkflowRepository:
    """获取 Workflow Repository"""
    return container.workflow_repository(session)


def verify_test_mode(
    x_test_mode: str | None = Header(None, alias="X-Test-Mode"),
) -> None:
    """验证测试模式请求头

    安全控制：必须携带 X-Test-Mode: true
    """
    if x_test_mode != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TEST_MODE_REQUIRED",
                "message": "Seed API requires X-Test-Mode: true header",
            },
        )


# ==================== 端点 ====================


@router.post(
    "/workflows/seed",
    response_model=SeedWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid fixture type"},
        403: {"model": ErrorResponse, "description": "Test mode required"},
    },
)
def seed_test_workflow(
    request: SeedWorkflowRequest,
    _: None = Depends(verify_test_mode),
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
) -> SeedWorkflowResponse:
    """创建测试 Workflow（仅测试环境）

    安全控制：
    - 必须携带 X-Test-Mode: true 请求头
    - 仅在测试/开发环境启用（生产环境 404）

    Fixture 类型：
    - main_subgraph_only: 正常的主连通子图执行流程
    - with_isolated_nodes: 带孤立节点的工作流
    - side_effect_workflow: 包含副作用节点（HTTP）的工作流
    - invalid_config: 包含无效配置的工作流
    """
    use_case = SeedTestWorkflowUseCase(
        workflow_repository=workflow_repository,
        fixture_factory=WorkflowFixtureFactory(),
    )

    try:
        output = use_case.execute(
            SeedTestWorkflowInput(
                fixture_type=request.fixture_type,
                project_id=request.project_id,
                custom_metadata=request.custom_metadata,
                custom_nodes=request.custom_nodes,
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_FIXTURE_TYPE",
                "message": str(e),
                "valid_types": WorkflowFixtureFactory.list_fixture_types(),
            },
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "SEED_FAILED",
                "message": str(e),
            },
        ) from e

    return SeedWorkflowResponse(
        workflow_id=output.workflow_id,
        project_id=output.project_id,
        fixture_type=output.fixture_type,
        metadata=output.metadata,
        cleanup_token=output.cleanup_token,
    )


@router.delete(
    "/workflows/cleanup",
    response_model=CleanupWorkflowsResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Test mode required"},
    },
)
def cleanup_test_workflows(
    request: CleanupWorkflowsRequest,
    _: None = Depends(verify_test_mode),
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
) -> CleanupWorkflowsResponse:
    """清理测试 Workflow（仅测试环境）

    支持两种清理方式：
    1. 按 cleanup_tokens 批量删除
    2. 按 metadata 匹配删除（如 test_seed=True）
    """
    use_case = CleanupTestWorkflowsUseCase(workflow_repository=workflow_repository)

    output = use_case.execute(
        CleanupTestWorkflowsInput(
            cleanup_tokens=request.cleanup_tokens,
            delete_by_source=request.delete_by_source,
        )
    )

    return CleanupWorkflowsResponse(
        deleted_count=output.deleted_count,
        failed=output.failed,
    )


@router.get(
    "/workflows/fixture-types",
    response_model=FixtureTypesResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Test mode required"},
    },
)
def list_fixture_types(
    _: None = Depends(verify_test_mode),
) -> FixtureTypesResponse:
    """列出可用的 Fixture 类型

    返回所有已注册的 fixture 类型名称，用于客户端枚举。
    """
    return FixtureTypesResponse(
        fixture_types=WorkflowFixtureFactory.list_fixture_types(),
    )
