"""Chat workflow streaming endpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.application.use_cases.update_workflow_by_chat import (
    UpdateWorkflowByChatInput,
    UpdateWorkflowByChatUseCase,
)
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.interfaces.api.dto.workflow_dto import ChatRequest
from src.interfaces.api.routes import workflows as workflows_routes

router = APIRouter(tags=["Chat Workflows"])


def _chat_use_case_dependency(
    workflow_repository=Depends(workflows_routes.get_workflow_repository),
    chat_service=Depends(workflows_routes.get_workflow_chat_service),
) -> UpdateWorkflowByChatUseCase:
    """Reuse the workflow module dependency wiring."""

    return UpdateWorkflowByChatUseCase(
        workflow_repository=workflow_repository,
        chat_service=chat_service,
    )


@router.post(
    "/workflows/{workflow_id}/chat-stream",
    status_code=status.HTTP_200_OK,
)
async def chat_workflow_stream(
    workflow_id: str,
    request: ChatRequest,
    use_case: UpdateWorkflowByChatUseCase = Depends(_chat_use_case_dependency),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Stream workflow updates produced by the chat use case."""

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            yield f"event: llm_thinking\ndata: {json.dumps({'message': 'AI is analyzing the request.'})}\n\n"

            input_data = UpdateWorkflowByChatInput(
                workflow_id=workflow_id,
                user_message=request.message,
            )
            modified_workflow, ai_message = use_case.execute(input_data)

            preview_data = {
                "type": "preview",
                "message": ai_message,
                "nodes": [
                    {
                        "id": node.id,
                        "type": node.type.value,
                        "name": node.name,
                        "position": {"x": node.position.x, "y": node.position.y},
                        "data": node.config,
                    }
                    for node in modified_workflow.nodes
                ],
                "edges": [
                    {
                        "id": edge.id,
                        "source": edge.source_node_id,
                        "target": edge.target_node_id,
                        "condition": edge.condition,
                    }
                    for edge in modified_workflow.edges
                ],
            }
            yield f"event: preview_changes\ndata: {json.dumps(preview_data)}\n\n"

            db.commit()

            final_data = {
                "type": "workflow_updated",
                "message": "Workflow updated successfully.",
                "workflow": {
                    "id": modified_workflow.id,
                    "name": modified_workflow.name,
                    "nodes": preview_data["nodes"],
                    "edges": preview_data["edges"],
                },
            }
            yield f"event: workflow_updated\ndata: {json.dumps(final_data)}\n\n"
            yield "event: done\ndata: {}\n\n"

        except NotFoundError:
            error_data = {"type": "error", "message": f"Workflow not found: {workflow_id}"}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        except DomainError as exc:
            error_data = {"type": "error", "message": str(exc)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        except Exception as exc:  # pragma: no cover - best-effort fallback
            error_data = {"type": "error", "message": f"Server error: {exc}"}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
