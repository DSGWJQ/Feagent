"""Complete Chat Workflows API - 完整的对话 API 端点

实现文档定义的所有 Chat Workflows 端点（docs/api/workflow_platform_api.md:68-76）
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.chat_message_repository import (
    SQLAlchemyChatMessageRepository,
)
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.dto.chat_dto import (
    ChatMessageResponse,
    CompressedContextResponse,
    SearchResultResponse,
)

router = APIRouter(prefix="/api/workflows", tags=["Chat Workflows"])


def get_chat_message_repository(
    db: Session = Depends(get_db_session),
) -> SQLAlchemyChatMessageRepository:
    """获取 ChatMessage Repository"""
    return SQLAlchemyChatMessageRepository(db)


def get_workflow_repository(db: Session = Depends(get_db_session)) -> SQLAlchemyWorkflowRepository:
    """获取 Workflow Repository"""
    return SQLAlchemyWorkflowRepository(db)


# ─────────────────────────────────────────────────────
# 1. 查看对话历史
# ─────────────────────────────────────────────────────
@router.get("/{workflow_id}/chat-history", response_model=list[ChatMessageResponse])
async def get_chat_history(
    workflow_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="最多返回多少条消息"),
    repo: SQLAlchemyChatMessageRepository = Depends(get_chat_message_repository),
    workflow_repo: SQLAlchemyWorkflowRepository = Depends(get_workflow_repository),
) -> list[ChatMessageResponse]:
    """获取工作流的对话历史

    真实场景：
    - 用户打开工作流页面
    - 前端调用此 API 加载历史对话
    - 显示用户和 AI 的历史交互记录

    返回：
        按时间升序排列的消息列表（旧 → 新）
    """
    # 验证工作流存在
    workflow = workflow_repo.find_by_id(workflow_id)
    if not workflow:
        raise NotFoundError(f"Workflow not found: {workflow_id}")

    # 查询历史记录
    messages = repo.find_by_workflow_id(workflow_id, limit=limit)

    # 转换为 DTO
    return [ChatMessageResponse.from_entity(msg) for msg in messages]


# ─────────────────────────────────────────────────────
# 2. 搜索历史消息
# ─────────────────────────────────────────────────────
@router.get("/{workflow_id}/chat-search", response_model=list[SearchResultResponse])
async def search_chat_history(
    workflow_id: str,
    query: str = Query(..., min_length=1, description="搜索关键词"),
    threshold: float = Query(default=0.5, ge=0.0, le=1.0, description="相关性阈值"),
    max_results: int = Query(default=20, ge=1, le=100, description="最多返回结果数"),
    repo: SQLAlchemyChatMessageRepository = Depends(get_chat_message_repository),
    workflow_repo: SQLAlchemyWorkflowRepository = Depends(get_workflow_repository),
) -> list[SearchResultResponse]:
    """搜索对话历史

    真实场景：
    - 用户在历史记录中搜索："HTTP节点"
    - 系统返回所有包含关键词的消息
    - 按相关性排序

    参数：
        query: 搜索关键词
        threshold: 相关性阈值（0-1），低于此值的结果会被过滤
        max_results: 最多返回多少条结果

    返回：
        按相关性降序排列的搜索结果
    """
    # 验证工作流存在
    workflow = workflow_repo.find_by_id(workflow_id)
    if not workflow:
        raise NotFoundError(f"Workflow not found: {workflow_id}")

    # 搜索消息
    results = repo.search(workflow_id, query, threshold=threshold)

    # 限制返回数量
    results = results[:max_results]

    # 转换为 DTO
    return [
        SearchResultResponse(
            message=ChatMessageResponse.from_entity(msg),
            relevance_score=score,
        )
        for msg, score in results
    ]


# ─────────────────────────────────────────────────────
# 3. 获取工作流建议
# ─────────────────────────────────────────────────────
@router.get("/{workflow_id}/suggestions", response_model=list[str])
async def get_workflow_suggestions(
    workflow_id: str,
    workflow_repo: SQLAlchemyWorkflowRepository = Depends(get_workflow_repository),
) -> list[str]:
    """获取工作流优化建议

    真实场景：
    - 用户想了解如何改进工作流
    - 系统分析工作流结构
    - 返回优化建议列表

    返回：
        建议列表（例如："缺少开始节点"、"节点未连接"等）
    """
    # 获取工作流
    workflow = workflow_repo.find_by_id(workflow_id)
    if not workflow:
        raise NotFoundError(f"Workflow not found: {workflow_id}")

    # 生成建议（简单实现）
    from src.domain.value_objects.node_type import NodeType

    suggestions = []

    if not workflow.nodes:
        suggestions.append("工作流没有任何节点，请添加至少一个节点")
        return suggestions

    # 检查开始和结束节点
    has_start = any(node.type == NodeType.START for node in workflow.nodes)
    has_end = any(node.type == NodeType.END for node in workflow.nodes)

    if not has_start:
        suggestions.append("缺少开始节点（start），建议在工作流开头添加开始节点")
    if not has_end:
        suggestions.append("缺少结束节点（end），建议在工作流末尾添加结束节点")

    # 检查节点连接
    if workflow.edges:
        connected_nodes = set()
        for edge in workflow.edges:
            connected_nodes.add(edge.source_node_id)
            connected_nodes.add(edge.target_node_id)

        for node in workflow.nodes:
            if node.type != NodeType.START and node.id not in connected_nodes:
                suggestions.append(f"节点 '{node.name}' 未连接到任何边，可能会被跳过")
    else:
        if len(workflow.nodes) > 1:
            suggestions.append("工作流有多个节点但没有边连接，请添加边以连接节点")

    # 检查节点配置
    for node in workflow.nodes:
        if node.type not in [NodeType.START, NodeType.END] and not node.config:
            suggestions.append(f"节点 '{node.name}' 没有配置，可能需要添加配置信息")

    if not suggestions:
        suggestions.append("工作流结构良好，暂无优化建议")

    return suggestions


# ─────────────────────────────────────────────────────
# 4. 清空对话历史
# ─────────────────────────────────────────────────────
@router.delete("/{workflow_id}/chat-history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(
    workflow_id: str,
    repo: SQLAlchemyChatMessageRepository = Depends(get_chat_message_repository),
    workflow_repo: SQLAlchemyWorkflowRepository = Depends(get_workflow_repository),
    db: Session = Depends(get_db_session),
) -> None:
    """清空对话历史

    真实场景：
    - 用户点击"清空历史记录"按钮
    - 系统删除该工作流的所有历史消息
    - 用户刷新页面，历史记录为空

    注意：此操作不可撤销
    """
    # 验证工作流存在
    workflow = workflow_repo.find_by_id(workflow_id)
    if not workflow:
        raise NotFoundError(f"Workflow not found: {workflow_id}")

    # 删除历史记录
    repo.delete_by_workflow_id(workflow_id)
    db.commit()


# ─────────────────────────────────────────────────────
# 5. 获取压缩上下文
# ─────────────────────────────────────────────────────
@router.get("/{workflow_id}/chat-context", response_model=CompressedContextResponse)
async def get_chat_context(
    workflow_id: str,
    max_tokens: int = Query(default=2000, ge=100, le=10000, description="最大 token 数"),
    repo: SQLAlchemyChatMessageRepository = Depends(get_chat_message_repository),
    workflow_repo: SQLAlchemyWorkflowRepository = Depends(get_workflow_repository),
) -> CompressedContextResponse:
    """获取压缩后的对话上下文

    真实场景：
    - LLM 调用需要上下文，但 token 有限
    - 系统智能压缩历史记录
    - 保留最近的和最重要的消息

    参数：
        max_tokens: 最大 token 数（默认 2000）

    返回：
        压缩后的消息列表 + token 统计
    """
    # 验证工作流存在
    workflow = workflow_repo.find_by_id(workflow_id)
    if not workflow:
        raise NotFoundError(f"Workflow not found: {workflow_id}")

    # 获取所有消息
    all_messages = repo.find_by_workflow_id(workflow_id, limit=1000)

    if not all_messages:
        return CompressedContextResponse(
            messages=[],
            total_tokens=0,
            compression_ratio=1.0,
        )

    # 简单压缩：从最新的消息开始，直到达到 token 限制
    compressed = []
    token_count = 0

    # 从后往前（最新到最旧）
    for msg in reversed(all_messages):
        # 估计消息的 token 数（简化算法）
        msg_tokens = _estimate_tokens(msg.content)

        if token_count + msg_tokens <= max_tokens:
            compressed.insert(0, msg)  # 插入到前面以保持时间顺序
            token_count += msg_tokens
        else:
            break

    # 计算压缩比例
    compression_ratio = len(compressed) / len(all_messages) if all_messages else 1.0

    return CompressedContextResponse(
        messages=[ChatMessageResponse.from_entity(msg) for msg in compressed],
        total_tokens=token_count,
        compression_ratio=compression_ratio,
    )


def _estimate_tokens(text: str) -> int:
    """估计文本的 token 数

    简化算法：
    - 中文：约 1.3 字符 = 1 token
    - 英文：约 4 字符 = 1 token
    """
    import re

    # 估计中文字符数（CJK 字符）
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))

    # 估计其他字符
    other_count = len(text) - cjk_count

    # 中文：平均 1.3 字符 = 1 token
    # 英文：平均 4 字符 = 1 token
    tokens = int(cjk_count / 1.3) + int(other_count / 4)

    # 至少计为 1 token
    return max(1, tokens)
