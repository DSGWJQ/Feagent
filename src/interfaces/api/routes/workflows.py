"""Workflow API 路由

定义 Workflow 相关的 API 端点
"""

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from langchain_openai import ChatOpenAI

from src.application.use_cases.execute_workflow import (
    ExecuteWorkflowInput,
    ExecuteWorkflowUseCase,
)
from src.application.use_cases.update_workflow_by_chat import (
    UpdateWorkflowByChatInput,
    UpdateWorkflowByChatUseCase,
)
from src.application.use_cases.update_workflow_by_drag import (
    UpdateWorkflowByDragInput,
    UpdateWorkflowByDragUseCase,
)
from src.config import settings
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.services.workflow_chat_service import WorkflowChatService
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry
from src.interfaces.api.dto.workflow_dto import (
    ChatRequest,
    ChatResponse,
    UpdateWorkflowRequest,
    WorkflowResponse,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


# 创建全局执行器注册表
_executor_registry = create_executor_registry(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db_session),
) -> WorkflowResponse:
    """获取工作流详情

    参数：
        workflow_id: 工作流 ID

    返回：
        工作流详情

    错误：
        404: Workflow 不存在
    """
    try:
        # 1. 创建 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)

        # 2. 获取工作流
        workflow = workflow_repository.get_by_id(workflow_id)

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # 3. 转换为 DTO
        return WorkflowResponse.from_entity(workflow)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: str,
    request: UpdateWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> WorkflowResponse:
    """更新工作流（拖拽调整）

    业务场景：
    - 用户在前端拖拽编辑器中调整工作流
    - 添加/删除/更新节点
    - 添加/删除边

    请求参数：
    - workflow_id: 工作流 ID（路径参数）
    - request: 更新请求（包含节点和边列表）

    返回：
    - 更新后的工作流

    错误：
    - 404: Workflow 不存在
    - 422: 请求参数验证失败
    - 400: 业务规则验证失败（如边引用的节点不存在）
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"[PATCH] 开始更新工作流: workflow_id={workflow_id!r} (type={type(workflow_id).__name__})")
        logger.info(f"[PATCH] 请求数据: nodes={len(request.nodes)}, edges={len(request.edges)}")

        # 1. 创建 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)
        logger.info(f"[PATCH] Repository 创建成功")

        # 2. 先测试能否找到工作流
        test_find = workflow_repository.find_by_id(workflow_id)
        logger.info(f"[PATCH] find_by_id 结果: {test_find is not None}")
        if test_find:
            logger.info(f"[PATCH] 找到工作流: id={test_find.id}, name={test_find.name}")

        # 3. 转换 DTO → Entity
        nodes = [node_dto.to_entity() for node_dto in request.nodes]
        edges = [edge_dto.to_entity() for edge_dto in request.edges]
        logger.info(f"[PATCH] DTO 转换完成: nodes={len(nodes)}, edges={len(edges)}")

        # 4. 创建 Use Case
        use_case = UpdateWorkflowByDragUseCase(workflow_repository=workflow_repository)
        logger.info(f"[PATCH] Use Case 创建成功")

        # 5. 执行 Use Case
        input_data = UpdateWorkflowByDragInput(
            workflow_id=workflow_id,
            nodes=nodes,
            edges=edges,
        )
        logger.info(f"[PATCH] 开始执行 Use Case...")
        workflow = use_case.execute(input_data)
        logger.info(f"[PATCH] Use Case 执行成功: workflow_id={workflow.id}")

        # 5. 提交事务
        db.commit()

        # 6. 转换 Entity → DTO
        return WorkflowResponse.from_entity(workflow)

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{e.entity_type} 不存在: {e.entity_id}",
        )
    except DomainError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


class ExecuteWorkflowRequest(BaseModel):
    """执行工作流请求

    字段：
    - initial_input: 初始输入（传递给 Start 节点）
    """

    initial_input: Any = None


class ExecuteWorkflowResponse(BaseModel):
    """执行工作流响应

    字段：
    - execution_log: 执行日志（每个节点的执行记录）
    - final_result: 最终结果（End 节点的输出）
    """

    execution_log: list[dict[str, Any]]
    final_result: Any


@router.post("/{workflow_id}/execute", response_model=ExecuteWorkflowResponse)
async def execute_workflow(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> ExecuteWorkflowResponse:
    """执行工作流（非流式）

    业务场景：
    - 用户触发工作流执行
    - 按拓扑顺序执行节点
    - 返回执行结果

    请求参数：
    - workflow_id: 工作流 ID（路径参数）
    - request: 执行请求（包含初始输入）

    返回：
    - 执行日志和最终结果

    错误：
    - 404: Workflow 不存在
    - 400: 工作流执行失败（如包含环）
    """
    try:
        # 1. 创建 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)

        # 2. 创建 Use Case
        use_case = ExecuteWorkflowUseCase(
            workflow_repository=workflow_repository,
            executor_registry=_executor_registry,
        )

        # 3. 执行 Use Case
        input_data = ExecuteWorkflowInput(
            workflow_id=workflow_id,
            initial_input=request.initial_input,
        )
        result = await use_case.execute(input_data)

        # 4. 返回结果
        return ExecuteWorkflowResponse(
            execution_log=result["execution_log"],
            final_result=result["final_result"],
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{e.entity_type} 不存在: {e.entity_id}",
        )
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )


@router.post("/{workflow_id}/execute/stream")
async def execute_workflow_streaming(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """执行工作流（流式返回 SSE）

    业务场景：
    - 用户触发工作流执行
    - 实时推送节点执行状态
    - 使用 Server-Sent Events (SSE) 协议

    请求参数：
    - workflow_id: 工作流 ID（路径参数）
    - request: 执行请求（包含初始输入）

    返回：
    - SSE 事件流（text/event-stream）

    事件类型：
    - node_start: 节点开始执行
    - node_complete: 节点执行完成
    - node_error: 节点执行失败
    - workflow_complete: 工作流执行完成
    - workflow_error: 工作流执行失败

    错误：
    - 404: Workflow 不存在
    """
    import json

    async def event_generator():
        """生成 SSE 事件"""
        try:
            # 1. 创建 Repository
            workflow_repository = SQLAlchemyWorkflowRepository(db)

            # 2. 创建 Use Case
            use_case = ExecuteWorkflowUseCase(
                workflow_repository=workflow_repository,
                executor_registry=_executor_registry,
            )

            # 3. 执行 Use Case（流式）
            input_data = ExecuteWorkflowInput(
                workflow_id=workflow_id,
                initial_input=request.initial_input,
            )

            # 4. 生成 SSE 事件
            async for event in use_case.execute_streaming(input_data):
                yield f"data: {json.dumps(event)}\n\n"

        except NotFoundError as e:
            # 生成错误事件
            error_event = {
                "type": "workflow_error",
                "error": f"{e.entity_type} 不存在: {e.entity_id}",
            }
            yield f"data: {json.dumps(error_event)}\n\n"

        except Exception as e:
            # 生成错误事件
            error_event = {
                "type": "workflow_error",
                "error": f"服务器内部错误: {str(e)}",
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/{workflow_id}/chat", response_model=ChatResponse)
def chat_with_workflow(
    workflow_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db_session),
) -> ChatResponse:
    """对话式修改工作流

    参数：
        workflow_id: 工作流 ID
        request: 对话请求（包含用户消息）

    返回：
        ChatResponse: 包含修改后的工作流和AI回复消息

    错误：
    - 404: Workflow 不存在
    - 400: 消息为空或处理失败
    - 500: 服务器内部错误
    """
    try:
        # 1. 创建 Repository
        workflow_repository = SQLAlchemyWorkflowRepository(db)

        # 2. 创建 LLM 实例
        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

        # 3. 创建 Domain Service
        chat_service = WorkflowChatService(llm=llm)

        # 4. 创建 Use Case
        use_case = UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=chat_service,
        )

        # 5. 执行 Use Case
        input_data = UpdateWorkflowByChatInput(
            workflow_id=workflow_id,
            user_message=request.message,
        )
        modified_workflow, ai_message = use_case.execute(input_data)

        # 6. 提交事务
        db.commit()

        # 7. 返回结果
        return ChatResponse(
            workflow=WorkflowResponse.from_entity(modified_workflow),
            ai_message=ai_message,
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{e.entity_type} 不存在: {e.entity_id}",
        )
    except DomainError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器内部错误: {str(e)}",
        )
