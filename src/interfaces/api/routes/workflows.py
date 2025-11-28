"""Workflow API routes."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from src.application.use_cases.execute_workflow import (
    ExecuteWorkflowInput,
    ExecuteWorkflowUseCase,
)
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
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.ports.workflow_chat_llm import WorkflowChatLLM
from src.domain.services.workflow_chat_service import WorkflowChatService
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry
from src.infrastructure.llm import LangChainWorkflowChatLLM
from src.interfaces.api.dependencies.current_user import get_current_user_optional
from src.interfaces.api.dto.workflow_dto import (
    ChatRequest,
    ChatResponse,
    CreateWorkflowRequest,
    ImportWorkflowRequest,
    ImportWorkflowResponse,
    UpdateWorkflowRequest,
    WorkflowResponse,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])

_executor_registry = create_executor_registry(
    openai_api_key=settings.openai_api_key or None,
    anthropic_api_key=getattr(settings, "anthropic_api_key", None),
)


def get_workflow_repository(
    db: Session = Depends(get_db_session),
) -> SQLAlchemyWorkflowRepository:
    """Return a repository bound to the current DB session."""

    return SQLAlchemyWorkflowRepository(db)


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


def get_workflow_chat_service(
    llm: WorkflowChatLLM = Depends(get_workflow_chat_llm),
) -> WorkflowChatService:
    """Construct the domain service that applies chat-driven updates."""

    return WorkflowChatService(llm=llm)


def get_update_workflow_by_chat_use_case(
    workflow_repository: SQLAlchemyWorkflowRepository = Depends(get_workflow_repository),
    chat_service: WorkflowChatService = Depends(get_workflow_chat_service),
) -> UpdateWorkflowByChatUseCase:
    """Assemble the chat update use case with its dependencies."""

    return UpdateWorkflowByChatUseCase(
        workflow_repository=workflow_repository,
        chat_service=chat_service,
    )


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    request: CreateWorkflowRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user_optional),
) -> WorkflowResponse:
    """Create a workflow."""

    from src.domain.entities.workflow import Workflow

    repository = SQLAlchemyWorkflowRepository(db)

    try:
        nodes = [node_dto.to_entity() for node_dto in request.nodes]
        edges = [edge_dto.to_entity() for edge_dto in request.edges]

        workflow = Workflow.create(
            name=request.name,
            description=request.description,
            nodes=nodes,
            edges=edges,
        )
        if current_user:
            workflow.user_id = current_user.id

        repository.save(workflow)
        db.commit()
        return WorkflowResponse.from_entity(workflow)

    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - unexpected failure path
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create workflow: {exc}",
        ) from exc


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db_session),
) -> WorkflowResponse:
    """Return workflow details."""

    repository = SQLAlchemyWorkflowRepository(db)
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
    db: Session = Depends(get_db_session),
) -> WorkflowResponse:
    """Update a workflow via drag-and-drop payloads."""

    repository = SQLAlchemyWorkflowRepository(db)
    use_case = UpdateWorkflowByDragUseCase(workflow_repository=repository)

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
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


class ExecuteWorkflowRequest(BaseModel):
    """Workflow execution request payload."""

    initial_input: Any = None


class ExecuteWorkflowResponse(BaseModel):
    """Workflow execution response."""

    execution_log: list[dict[str, Any]]
    final_result: Any


@router.post("/{workflow_id}/execute", response_model=ExecuteWorkflowResponse)
async def execute_workflow(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> ExecuteWorkflowResponse:
    """Execute a workflow synchronously."""

    repository = SQLAlchemyWorkflowRepository(db)
    use_case = ExecuteWorkflowUseCase(
        workflow_repository=repository,
        executor_registry=_executor_registry,
    )

    try:
        input_data = ExecuteWorkflowInput(
            workflow_id=workflow_id,
            initial_input=request.initial_input,
        )
        result = await use_case.execute(input_data)
        return ExecuteWorkflowResponse(
            execution_log=result["execution_log"],
            final_result=result["final_result"],
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{exc.entity_type} not found: {exc.entity_id}",
        ) from exc
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{workflow_id}/execute/stream")
async def execute_workflow_streaming(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Execute a workflow and stream progress via SSE."""

    async def event_generator() -> AsyncGenerator[str, None]:
        repository = SQLAlchemyWorkflowRepository(db)
        use_case = ExecuteWorkflowUseCase(
            workflow_repository=repository,
            executor_registry=_executor_registry,
        )

        try:
            input_data = ExecuteWorkflowInput(
                workflow_id=workflow_id,
                initial_input=request.initial_input,
            )
            async for event in use_case.execute_streaming(input_data):
                yield f"data: {json.dumps(event)}\n\n"
        except NotFoundError as exc:
            error_event = {
                "type": "workflow_error",
                "error": f"{exc.entity_type} not found: {exc.entity_id}",
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        except Exception as exc:  # pragma: no cover - best-effort error reporting
            error_event = {
                "type": "workflow_error",
                "error": f"Workflow execution failed: {exc}",
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
    use_case: UpdateWorkflowByChatUseCase = Depends(get_update_workflow_by_chat_use_case),
) -> ChatResponse:
    """Modify a workflow through conversational input."""

    try:
        input_data = UpdateWorkflowByChatInput(
            workflow_id=workflow_id,
            user_message=request.message,
        )
        workflow, ai_message = use_case.execute(input_data)
        db.commit()
        return ChatResponse(
            workflow=WorkflowResponse.from_entity(workflow),
            ai_message=ai_message,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{exc.entity_type} not found: {exc.entity_id}",
        ) from exc
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


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
    db: Session = Depends(get_db_session),
) -> ImportWorkflowResponse:
    """Import a workflow from a Coze JSON payload."""

    repository = SQLAlchemyWorkflowRepository(db)
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
    db: Session = Depends(get_db_session),
) -> GenerateWorkflowResponse:
    """Generate a workflow structure using the supplied form inputs."""

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured.",
        )

    repository = SQLAlchemyWorkflowRepository(db)
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
