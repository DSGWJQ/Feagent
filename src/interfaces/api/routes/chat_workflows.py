"""Chat Workflows 路由

定义增强对话工作流相关的 API 端点：
- POST /api/workflows/{workflow_id}/chat - 处理用户消息（流式）
- GET /api/workflows/{workflow_id}/chat-history - 获取对话历史
- GET /api/workflows/{workflow_id}/chat-search - 搜索对话历史
- GET /api/workflows/{workflow_id}/suggestions - 获取工作流建议
- DELETE /api/workflows/{workflow_id}/chat-history - 清空对话历史
- GET /api/workflows/{workflow_id}/chat-context - 获取压缩后的上下文
"""

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
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.dto.workflow_dto import (
    ChatRequest,
)
from src.interfaces.api.routes.workflows import (
    get_workflow_chat_service,
    get_workflow_repository,
    get_update_workflow_by_chat_use_case,
)

# 创建路由器
router = APIRouter(tags=["Chat Workflows"])


@router.post(
    "/workflows/{workflow_id}/chat-stream",
    status_code=status.HTTP_200_OK,
)
async def chat_workflow_stream(
    workflow_id: str,
    request: ChatRequest,
    use_case: UpdateWorkflowByChatUseCase = Depends(get_update_workflow_by_chat_use_case),
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    """处理用户消息并流式返回更新过程

    SSE 事件类型：
    - llm_thinking: LLM 推理中
    - preview_changes: 变更预览
    - workflow_updated: 最终工作流
    - error: 错误
    - done: 完成
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # 1. LLM 推理阶段
            yield f"event: llm_thinking\ndata: {json.dumps({'message': 'AI 正在分析您的需求...'})}\n\n"

            # 2. 执行更新
            input_data = UpdateWorkflowByChatInput(
                workflow_id=workflow_id,
                user_message=request.message,
            )

            modified_workflow, ai_message = use_case.execute(input_data)

            # 3. 发送预览
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

            # 4. 保存到数据库
            db.commit()

            # 5. 发送最终结果
            final_data = {
                "type": "workflow_updated",
                "message": "工作流已更新",
                "workflow": {
                    "id": modified_workflow.id,
                    "name": modified_workflow.name,
                    "nodes": preview_data["nodes"],
                    "edges": preview_data["edges"],
                },
            }
            yield f"event: workflow_updated\ndata: {json.dumps(final_data)}\n\n"

            # 6. 完成
            yield "event: done\ndata: {}\n\n"

        except NotFoundError:
            error_data = {"type": "error", "message": f"工作流不存在: {workflow_id}"}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        except DomainError as e:
            error_data = {"type": "error", "message": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        except Exception as e:
            error_data = {"type": "error", "message": f"服务器错误: {str(e)}"}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
