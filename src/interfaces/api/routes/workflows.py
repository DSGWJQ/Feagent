"""Workflow API routes."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from src.application.use_cases.generate_workflow_from_form import (
    GenerateWorkflowFromFormUseCase,
    GenerateWorkflowInput,
)
from src.application.use_cases.import_workflow import (
    ImportWorkflowInput,
    ImportWorkflowUseCase,
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
from src.domain.exceptions import DomainError, DomainValidationError, NotFoundError
from src.domain.ports.chat_message_repository import ChatMessageRepository
from src.domain.ports.workflow_chat_llm import WorkflowChatLLM
from src.domain.ports.workflow_chat_service import WorkflowChatServicePort
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_chat_service_enhanced import EnhancedWorkflowChatService
from src.domain.services.workflow_save_validator import WorkflowSaveValidator
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.llm import LangChainWorkflowChatLLM
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
from src.interfaces.api.dependencies.current_user import get_current_user_optional
from src.interfaces.api.dependencies.rag import get_rag_service
from src.interfaces.api.dto.workflow_dto import (
    ChatCreateRequest,
    ChatRequest,
    ChatResponse,
    ImportWorkflowRequest,
    ImportWorkflowResponse,
    UpdateWorkflowRequest,
    WorkflowResponse,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])

logger = logging.getLogger(__name__)


class _ReactStepEvent(BaseModel):
    step_number: int = 0
    tool_id: str = ""
    thought: str = ""
    action: dict[str, Any] = {}
    observation: str = ""


def _normalize_react_step_event(raw_event: dict[str, Any]) -> _ReactStepEvent:
    step_data = raw_event.get("step")
    if isinstance(step_data, dict):
        step_number = (
            raw_event.get("step_number")
            or step_data.get("step")
            or step_data.get("step_number")
            or 0
        )
        tool_id = raw_event.get("tool_id") or step_data.get("tool_id") or ""
        thought = raw_event.get("thought") or step_data.get("thought") or ""
        action = (
            raw_event.get("action")
            if isinstance(raw_event.get("action"), dict)
            else step_data.get("action")
        )
        observation = raw_event.get("observation") or step_data.get("observation") or ""
    else:
        step_number = raw_event.get("step_number") or 0
        tool_id = raw_event.get("tool_id") or ""
        thought = raw_event.get("thought") or ""
        action = raw_event.get("action") if isinstance(raw_event.get("action"), dict) else {}
        observation = raw_event.get("observation") or ""

    if not tool_id:
        tool_id = f"react_{step_number or 0}"

    return _ReactStepEvent.model_validate(
        {
            "step_number": step_number,
            "tool_id": tool_id,
            "thought": thought,
            "action": action or {},
            "observation": observation,
        }
    )


def get_workflow_repository(
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> WorkflowRepository:
    """Return a repository bound to the current DB session."""

    return container.workflow_repository(db)


def get_chat_message_repository(
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> ChatMessageRepository:
    """Return a chat message repository bound to the current DB session."""

    return container.chat_message_repository(db)


def get_workflow_chat_llm() -> WorkflowChatLLM:
    """Resolve the LLM implementation used for workflow chat."""

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key is not configured for workflow chat.",
        )

    try:
        return LangChainWorkflowChatLLM(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            temperature=0.0,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def get_chat_openai() -> ChatOpenAI:
    """
    Backward-compatible helper for tests/patching.

    Workflow chat no longer depends directly on ChatOpenAI, but some integration tests
    patch this symbol to prevent accidental network calls.
    """

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key is not configured for workflow chat.",
        )

    return ChatOpenAI(
        api_key=SecretStr(settings.openai_api_key),
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        temperature=0.0,
    )


def get_workflow_chat_service(
    workflow_id: str = "",  # 从路径参数传入
    container: ApiContainer = Depends(get_container),
    llm: WorkflowChatLLM = Depends(get_workflow_chat_llm),
    chat_message_repository: ChatMessageRepository | None = Depends(get_chat_message_repository),
    db: Session = Depends(get_db_session),
) -> WorkflowChatServicePort:
    """构建增强版对话服务（使用新的 CompositeMemoryService）

    每个工作流的对话历史使用高性能内存系统（缓存 + 压缩 + 性能监控）
    """
    if workflow_id and chat_message_repository:
        # 导入 CompositeMemoryService 依赖
        from src.interfaces.api.dependencies.memory import get_composite_memory_service

        # 获取新的内存服务
        memory_service = get_composite_memory_service(session=db, container=container)

        # 使用新的内存系统创建服务
        return EnhancedWorkflowChatService(
            workflow_id=workflow_id,
            llm=llm,
            chat_message_repository=chat_message_repository,
            memory_service=memory_service,
        )
    else:
        # 临时会话（向后兼容，但需要 workflow_id）
        # 注意：这种情况下服务无法初始化，因为需要 workflow_id
        raise ValueError("workflow_id is required for EnhancedWorkflowChatService")


def get_update_workflow_by_chat_use_case(
    workflow_id: str,  # 从路径参数注入
    container: ApiContainer = Depends(get_container),
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
    chat_message_repository: ChatMessageRepository = Depends(get_chat_message_repository),
    llm: WorkflowChatLLM = Depends(get_workflow_chat_llm),
    rag_service=Depends(get_rag_service),
    db: Session = Depends(get_db_session),
) -> UpdateWorkflowByChatUseCase:
    """Assemble the chat update use case with its dependencies (using CompositeMemoryService)."""

    # 导入 CompositeMemoryService 依赖
    from src.interfaces.api.dependencies.memory import get_composite_memory_service

    # 获取新的内存服务
    memory_service = get_composite_memory_service(session=db, container=container)

    # 为每个请求创建新的对话服务实例（使用高性能内存系统）
    chat_service = EnhancedWorkflowChatService(
        workflow_id=workflow_id,
        llm=llm,
        chat_message_repository=chat_message_repository,
        rag_service=rag_service,
        memory_service=memory_service,
    )
    save_validator = WorkflowSaveValidator(
        executor_registry=container.executor_registry,
        tool_repository=container.tool_repository(db),
    )

    return UpdateWorkflowByChatUseCase(
        workflow_repository=workflow_repository,
        chat_service=chat_service,
        save_validator=save_validator,
    )


def get_update_workflow_by_chat_use_case_factory(
    container: ApiContainer = Depends(get_container),
    llm: WorkflowChatLLM = Depends(get_workflow_chat_llm),
    rag_service=Depends(get_rag_service),
    db: Session = Depends(get_db_session),
) -> Callable[[str], UpdateWorkflowByChatUseCase]:
    """Return a factory that can build UpdateWorkflowByChatUseCase for a given workflow_id.

    用于需要“先创建 workflow 再开始对话”的场景（如 chat-create）。
    """

    from src.interfaces.api.dependencies.memory import get_composite_memory_service

    def factory(workflow_id: str) -> UpdateWorkflowByChatUseCase:
        workflow_repository = container.workflow_repository(db)
        chat_message_repository = container.chat_message_repository(db)
        memory_service = get_composite_memory_service(session=db, container=container)
        save_validator = WorkflowSaveValidator(
            executor_registry=container.executor_registry,
            tool_repository=container.tool_repository(db),
        )
        chat_service = EnhancedWorkflowChatService(
            workflow_id=workflow_id,
            llm=llm,
            chat_message_repository=chat_message_repository,
            rag_service=rag_service,
            memory_service=memory_service,
        )
        return UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=chat_service,
            save_validator=save_validator,
        )

    return factory


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> WorkflowResponse:
    """Return workflow details."""

    repository = container.workflow_repository(db)
    workflow = repository.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found",
        )
    return WorkflowResponse.from_entity(workflow)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(
    workflow_id: str,
    request: UpdateWorkflowRequest,
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> WorkflowResponse:
    """Update a workflow via drag-and-drop payloads."""

    repository = container.workflow_repository(db)
    save_validator = WorkflowSaveValidator(
        executor_registry=container.executor_registry,
        tool_repository=container.tool_repository(db),
    )
    use_case = UpdateWorkflowByDragUseCase(
        workflow_repository=repository,
        save_validator=save_validator,
    )

    nodes = [node_dto.to_entity() for node_dto in request.nodes]
    edges = [edge_dto.to_entity() for edge_dto in request.edges]

    try:
        input_data = UpdateWorkflowByDragInput(
            workflow_id=workflow_id,
            nodes=nodes,
            edges=edges,
        )
        workflow = use_case.execute(input_data)
        db.commit()
        return WorkflowResponse.from_entity(workflow)
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{exc.entity_type} not found: {exc.entity_id}",
        ) from exc
    except DomainValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.to_dict(),
        ) from exc
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


class ExecuteWorkflowRequest(BaseModel):
    """Workflow execution request payload."""

    initial_input: Any = None
    run_id: str | None = None


@router.post("/{workflow_id}/execute/stream")
async def execute_workflow_streaming(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    http_request: Request,
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Execute a workflow and stream progress via SSE."""

    if settings.disable_run_persistence:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Runs API is disabled by feature flag (disable_run_persistence).",
        )

    run_id = request.run_id
    if run_id is None or not run_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="run_id is required (create run first, then execute/stream).",
        )

    assert run_id is not None
    from src.application.use_cases.execute_workflow import WORKFLOW_EXECUTION_KERNEL_ID

    executor_id = WORKFLOW_EXECUTION_KERNEL_ID

    # Fail-closed: ensure run exists and persist a deterministic start event before streaming begins.
    from src.application.use_cases.append_run_event import (
        AppendRunEventInput,
        AppendRunEventUseCase,
    )
    from src.domain.value_objects.run_status import RunStatus
    from src.infrastructure.database.repositories.run_event_repository import (
        SQLAlchemyRunEventRepository,
    )
    from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository
    from src.infrastructure.database.transaction_manager import SQLAlchemyTransactionManager

    run_repository = SQLAlchemyRunRepository(db)
    try:
        run = run_repository.get_by_id(run_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"run_id not found: {exc.entity_id}",
        ) from exc

    if run.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="run_id does not belong to this workflow",
        )
    if run.status is not RunStatus.CREATED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"run is not executable (status={run.status.value})",
        )

    run_event_use_case = AppendRunEventUseCase(
        run_repository=run_repository,
        run_event_repository=SQLAlchemyRunEventRepository(db),
        transaction_manager=SQLAlchemyTransactionManager(db),
    )

    run_event_use_case.execute(
        AppendRunEventInput(
            run_id=run_id,
            event_type="workflow_start",
            channel="execution",
            payload={
                "workflow_id": workflow_id,
                "executor_id": executor_id,
            },
        )
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        event_recorder = getattr(http_request.app.state, "event_recorder", None)
        started = time.perf_counter()
        events_sent = 0
        terminal_persisted = False
        try:
            kernel = container.workflow_execution_kernel(db)
            event_iter = kernel.execute_streaming(
                workflow_id=workflow_id,
                input_data=request.initial_input,
            )

            async for event in event_iter:
                if event_recorder is not None:
                    try:
                        event_recorder.enqueue(
                            run_id=run_id,
                            sse_event={**event, "channel": "execution"},
                        )
                    except Exception:
                        pass

                event_type = event.get("type", "")
                if not terminal_persisted and event_type in {"workflow_complete", "workflow_error"}:
                    run_event_use_case.execute(
                        AppendRunEventInput(
                            run_id=run_id,
                            event_type=event_type,
                            channel="execution",
                            payload={
                                "workflow_id": workflow_id,
                                "executor_id": executor_id,
                            },
                        )
                    )
                    terminal_persisted = True

                event = {
                    **event,
                    "run_id": run_id,
                    "executor_id": event.get("executor_id", executor_id),
                }
                events_sent += 1
                yield f"data: {json.dumps(event)}\n\n"
        except NotFoundError as exc:
            error_event = {
                "type": "workflow_error",
                "error": f"{exc.entity_type} not found: {exc.entity_id}",
            }
            run_event_use_case.execute(
                AppendRunEventInput(
                    run_id=run_id,
                    event_type="workflow_error",
                    channel="execution",
                    payload={
                        "workflow_id": workflow_id,
                        "executor_id": executor_id,
                        "error": error_event["error"],
                    },
                )
            )
            error_event["run_id"] = run_id
            if event_recorder is not None:
                try:
                    event_recorder.enqueue(
                        run_id=run_id,
                        sse_event={**error_event, "channel": "execution"},
                    )
                except Exception:
                    pass
            yield f"data: {json.dumps(error_event)}\n\n"
        except Exception as exc:  # pragma: no cover - best-effort error reporting
            error_event = {
                "type": "workflow_error",
                "error": f"Workflow execution failed: {exc}",
            }
            run_event_use_case.execute(
                AppendRunEventInput(
                    run_id=run_id,
                    event_type="workflow_error",
                    channel="execution",
                    payload={
                        "workflow_id": workflow_id,
                        "executor_id": executor_id,
                        "error": "workflow execution failed",
                    },
                )
            )
            error_event["run_id"] = run_id
            if event_recorder is not None:
                try:
                    event_recorder.enqueue(
                        run_id=run_id,
                        sse_event={**error_event, "channel": "execution"},
                    )
                except Exception:
                    pass
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "workflow_execute_stream_done",
                extra={
                    "workflow_id": workflow_id,
                    "executor_id": executor_id,
                    "duration_ms": duration_ms,
                    "events_sent": events_sent,
                    "run_id_present": True,
                    "run_persistence_enabled": True,
                },
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/chat-create/stream")
async def chat_create_stream(
    request: ChatCreateRequest,
    http_request: Request,
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user_optional),
    use_case_factory: Callable[[str], UpdateWorkflowByChatUseCase] = Depends(
        get_update_workflow_by_chat_use_case_factory
    ),
) -> StreamingResponse:
    """Create a base workflow and stream the first chat planning session (SSE).

    Contract:
    - Ensures an early event contains `metadata.workflow_id` (<= 1st event).
    - Uses SSEEmitterHandler so the payload is `data: <json>\\n\\n` (fetch-friendly).
    """

    from src.domain.entities.workflow import Workflow
    from src.domain.services.conversation_flow_emitter import ConversationFlowEmitter
    from src.interfaces.api.services.sse_emitter_handler import SSEEmitterHandler

    repository = container.workflow_repository(db)
    save_validator = WorkflowSaveValidator(
        executor_registry=container.executor_registry,
        tool_repository=container.tool_repository(db),
    )

    try:
        workflow = Workflow.create_base(
            description=request.message,
            project_id=request.project_id,
        )
        if current_user:
            workflow.user_id = current_user.id
        save_validator.validate_or_raise(workflow)
        repository.save(workflow)
        db.commit()
    except DomainValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.to_dict(),
        ) from exc
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    use_case = use_case_factory(workflow.id)

    session_id = f"chat_create_{workflow.id}_{id(http_request)}"
    emitter = ConversationFlowEmitter(session_id=session_id, timeout=30.0)
    handler = SSEEmitterHandler(emitter, http_request)

    base_metadata: dict[str, Any] = {"workflow_id": workflow.id}
    if request.project_id:
        base_metadata["project_id"] = request.project_id
    if request.run_id:
        base_metadata["run_id"] = request.run_id

    # 1st event MUST include workflow_id (contract: <= 1 event)
    await emitter.emit_thinking("AI is analyzing the request.", **base_metadata)

    async def run_chat() -> None:
        def _cleanup_failed_creation() -> None:
            try:
                repository.delete(workflow.id)
                db.commit()
            except Exception:  # pragma: no cover - best-effort cleanup
                db.rollback()
                logger.exception("chat_create_cleanup_failed", extra=base_metadata)

        try:
            input_data = UpdateWorkflowByChatInput(
                workflow_id=workflow.id,
                user_message=request.message,
            )

            async for event in use_case.execute_streaming(input_data):
                if await http_request.is_disconnected():
                    db.rollback()
                    _cleanup_failed_creation()
                    return

                event_type = event.get("type", "")

                if event_type == "react_step":
                    if event.get("thought"):
                        await emitter.emit_thinking(event["thought"], **base_metadata)

                    action = event.get("action") or {}
                    if action:
                        tool_name = action.get("type", "unknown")
                        tool_id = f"action_{event.get('step_number', 0)}"
                        await emitter.emit_tool_call(
                            tool_name=tool_name,
                            tool_id=tool_id,
                            arguments=action,
                            **base_metadata,
                        )

                    if event.get("observation"):
                        tool_id = f"action_{event.get('step_number', 0)}"
                        await emitter.emit_tool_result(
                            tool_id=tool_id,
                            result={"observation": event["observation"]},
                            success=True,
                            **base_metadata,
                        )

                elif event_type == "modifications_preview":
                    await emitter.emit_thinking(
                        f"Planned modifications: {event.get('modifications_count', 0)}",
                        **base_metadata,
                    )

                elif event_type == "workflow_updated":
                    workflow_payload = event.get("workflow") or {}
                    final_metadata = {
                        **base_metadata,
                        "workflow": workflow_payload,
                    }
                    await emitter.emit_final_response(
                        event.get("ai_message", "Workflow created."),
                        metadata=final_metadata,
                    )
                    db.commit()
                    return

        except DomainError as exc:
            db.rollback()
            _cleanup_failed_creation()
            await emitter.emit_error(
                str(exc),
                error_code="DOMAIN_ERROR",
                recoverable=False,
                **base_metadata,
            )
        except Exception:  # pragma: no cover - best-effort fallback
            db.rollback()
            _cleanup_failed_creation()
            logger.exception("chat-create streaming failed", extra=base_metadata)
            await emitter.emit_error(
                "Server error",
                error_code="SERVER_ERROR",
                recoverable=False,
                **base_metadata,
            )
        finally:
            await emitter.complete()

    asyncio.create_task(run_chat())
    return handler.create_response()


@router.post("/{workflow_id}/chat", response_model=ChatResponse)
def chat_with_workflow(
    workflow_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db_session),
    use_case: UpdateWorkflowByChatUseCase = Depends(get_update_workflow_by_chat_use_case),
) -> ChatResponse:
    """Modify a workflow through conversational input."""

    try:
        input_data = UpdateWorkflowByChatInput(
            workflow_id=workflow_id,
            user_message=request.message,
        )
        output = use_case.execute(input_data)
        db.commit()
        return ChatResponse(
            workflow=WorkflowResponse.from_entity(output.workflow),
            ai_message=output.ai_message,
            intent=output.intent,
            confidence=output.confidence,
            modifications_count=output.modifications_count,
            rag_sources=output.rag_sources,
            react_steps=output.react_steps,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{exc.entity_type} not found: {exc.entity_id}",
        ) from exc
    except DomainValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.to_dict(),
        ) from exc
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{workflow_id}/chat-stream")
async def chat_stream_with_workflow(
    workflow_id: str,
    request: ChatRequest,
    http_request: Request,
    db: Session = Depends(get_db_session),
    use_case: UpdateWorkflowByChatUseCase = Depends(get_update_workflow_by_chat_use_case),
):
    """Modify a workflow through conversational input with streaming steps (SSE).

    Phase 3 改进版：使用 ConversationFlowEmitter 实现流式输出。

    返回事件类型:
    - thinking: 思考过程
    - tool_call: 工具调用
    - tool_result: 工具执行结果
    - final: 最终响应
    - error: 错误信息

    Returns: Server-Sent Events stream of ReAct reasoning steps
    """
    from src.domain.services.conversation_flow_emitter import (
        ConversationFlowEmitter,
    )
    from src.interfaces.api.services.sse_emitter_handler import SSEEmitterHandler

    # 创建 emitter
    session_id = f"wf_{workflow_id}_{id(http_request)}"
    emitter = ConversationFlowEmitter(session_id=session_id, timeout=30.0)

    async def run_workflow_chat():
        """运行工作流聊天逻辑，通过 emitter 发送事件"""
        try:
            input_data = UpdateWorkflowByChatInput(
                workflow_id=workflow_id,
                user_message=request.message,
            )

            # 发送开始思考
            await emitter.emit_thinking(f"正在分析请求: {request.message[:50]}...")

            # Stream events from the use case
            async for event in use_case.execute_streaming(input_data):
                # 检查客户端是否断开
                if await http_request.is_disconnected():
                    await emitter.complete_with_error("Client disconnected")
                    return

                event_type = event.get("type", "")

                # 转换事件类型到 emitter
                if event_type == "processing_started":
                    await emitter.emit_thinking(event.get("message", "处理中..."))
                elif event_type == "react_step":
                    try:
                        step = _normalize_react_step_event(event)
                    except Exception:
                        await emitter.emit_error(
                            "Invalid react_step event payload",
                            error_code="INVALID_REACT_STEP",
                        )
                        continue

                    if step.thought:
                        await emitter.emit_thinking(step.thought)

                    if step.action:
                        action_type = step.action.get("type", "unknown")

                        from src.application.services.coordinator_policy_chain import (
                            CoordinatorPolicyChain,
                            CoordinatorRejectedError,
                        )

                        coordinator = getattr(http_request.app.state, "coordinator", None)
                        event_bus = getattr(http_request.app.state, "event_bus", None)

                        decision = {
                            "type": action_type,
                            "session_id": session_id,
                            "workflow_id": workflow_id,
                            "tool_id": step.tool_id,
                            **step.action,
                        }
                        policy = CoordinatorPolicyChain(
                            coordinator=coordinator,
                            event_bus=event_bus,
                            source="workflow_chat_stream_react",
                        )
                        try:
                            await policy.enforce_action_or_raise(
                                decision_type=action_type,
                                decision=decision,
                                correlation_id=session_id,
                                original_decision_id=step.tool_id,
                            )
                        except CoordinatorRejectedError as exc:
                            await emitter.emit_error(
                                error_message=str(exc),
                                error_code="COORDINATOR_REJECTED",
                                recoverable=False,
                                decision_type=action_type,
                                tool_id=step.tool_id,
                                correlation_id=session_id,
                            )
                            await emitter.complete()
                            db.rollback()
                            return

                        await emitter.emit_tool_call(
                            tool_name=action_type,
                            tool_id=step.tool_id,
                            arguments=step.action,
                        )

                    if step.observation:
                        await emitter.emit_tool_result(
                            tool_id=step.tool_id,
                            result={"observation": step.observation},
                            success=True,
                        )
                elif event_type == "modifications_preview":
                    await emitter.emit_tool_call(
                        tool_name="modifications_preview",
                        tool_id="modifications",
                        arguments={
                            "modifications_count": event.get("modifications_count", 0),
                            "intent": event.get("intent", ""),
                            "confidence": event.get("confidence", 0.0),
                        },
                    )
                    await emitter.emit_tool_result(
                        tool_id="modifications",
                        result={
                            "count": event.get("modifications_count", 0),
                            "intent": event.get("intent", ""),
                            "confidence": event.get("confidence", 0.0),
                        },
                        success=True,
                    )
                elif event_type == "workflow_updated":
                    await emitter.emit_final_response(
                        event.get("ai_message", "工作流已更新"),
                        metadata={
                            "workflow_id": workflow_id,
                            "workflow": event.get("workflow", {}),
                            "rag_sources": event.get("rag_sources", []),
                        },
                    )
                elif event_type == "error":
                    await emitter.emit_error(
                        event.get("detail", "未知错误"),
                        error_code=event.get("error", "UNKNOWN"),
                    )

            # 完成
            await emitter.complete()
            db.commit()

        except NotFoundError as exc:
            await emitter.emit_error(
                f"{exc.entity_type} not found: {exc.entity_id}",
                error_code="WORKFLOW_NOT_FOUND",
            )
            await emitter.complete()
            db.rollback()
        except DomainError as exc:
            await emitter.emit_error(str(exc), error_code="DOMAIN_ERROR")
            await emitter.complete()
            db.rollback()
        except Exception as exc:
            await emitter.emit_error(str(exc), error_code="INTERNAL_ERROR")
            await emitter.complete()
            db.rollback()

    # 启动工作流聊天任务
    import asyncio

    asyncio.create_task(run_workflow_chat())

    # 创建 SSE handler 并返回响应
    handler = SSEEmitterHandler(emitter, http_request)
    return handler.create_response(
        headers={"X-Session-ID": session_id},
    )


class GenerateWorkflowRequest(BaseModel):
    """Generate-workflow request payload."""

    description: str
    goal: str


class GenerateWorkflowResponse(BaseModel):
    """Generate-workflow response payload."""

    workflow_id: str
    name: str
    description: str
    node_count: int
    edge_count: int


class SimpleWorkflowLLMClient:
    """LLM client wrapper used by the generation use case."""

    def __init__(self, llm_model: ChatOpenAI):
        self.llm = llm_model

    async def generate_workflow(self, description: str, goal: str) -> dict[str, Any]:
        """Generate a workflow specification via LLM."""

        prompt = f"""
You are a workflow designer. Based on the following requirements, create a JSON workflow specification.

Description: {description}
Goal: {goal}

The JSON must include:
{{
  "name": "Workflow name",
  "description": "Workflow description",
  "nodes": [
    {{
      "type": "start|end|httpRequest|textModel|database|conditional|loop|python|transform|file|notification",
      "name": "Node name",
      "config": {{}},
      "position": {{"x": 100, "y": 100}}
    }}
  ],
  "edges": [
    {{"source": "node_1", "target": "node_2"}}
  ]
}}

Rules:
1. Include at least one start node and one end node.
2. Node types must be selected from the supported list.
3. Edge source/target must reference existing nodes.
4. Return valid JSON only, without extra commentary.
"""

        response = await self.llm.ainvoke(prompt)

        try:
            raw_content = getattr(response, "content", response)
            if isinstance(raw_content, str):
                text = raw_content
            elif isinstance(raw_content, list):
                text = "".join(
                    part if isinstance(part, str) else json.dumps(part) for part in raw_content
                )
            else:
                text = str(raw_content)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                raise ValueError("LLM response did not contain JSON.")
            return json.loads(text[start:end])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from LLM: {exc}") from exc


@router.post(
    "/import",
    response_model=ImportWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_workflow(
    request: ImportWorkflowRequest,
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> ImportWorkflowResponse:
    """Import a workflow from a Coze JSON payload."""

    repository = container.workflow_repository(db)
    use_case = ImportWorkflowUseCase(workflow_repository=repository)

    try:
        input_data = ImportWorkflowInput(coze_json=request.coze_json)
        result = use_case.execute(input_data)
        db.commit()
        return ImportWorkflowResponse(
            workflow_id=result.workflow_id,
            name=result.name,
            source=result.source,
            source_id=result.source_id,
        )
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/generate-from-form",
    response_model=GenerateWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_workflow_from_form(
    request: GenerateWorkflowRequest,
    container: ApiContainer = Depends(get_container),
    db: Session = Depends(get_db_session),
) -> GenerateWorkflowResponse:
    """Generate a workflow structure using the supplied form inputs."""

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured.",
        )

    repository = container.workflow_repository(db)
    llm = ChatOpenAI(
        api_key=SecretStr(settings.openai_api_key),
        model=settings.openai_model,
        temperature=0.7,
    )
    llm_client = SimpleWorkflowLLMClient(llm)

    use_case = GenerateWorkflowFromFormUseCase(
        workflow_repository=repository,
        llm_client=llm_client,
    )

    try:
        input_data = GenerateWorkflowInput(
            description=request.description,
            goal=request.goal,
        )
        workflow = await use_case.execute(input_data)
        db.commit()
        return GenerateWorkflowResponse(
            workflow_id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            node_count=len(workflow.nodes),
            edge_count=len(workflow.edges),
        )
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
