"""WorkflowModificationResult - 工作流修改结果值对象

Domain 层数据结构，用于封装工作流修改的结果信息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.entities.workflow import Workflow


@dataclass
class ModificationResult:
    """工作流修改结果

    封装工作流修改操作的完整结果信息。

    字段：
        success: 修改是否成功
        ai_message: AI 回复消息
        intent: 用户意图类型（add_node、delete_node、add_edge等）
        confidence: AI 的信心度（0-1）
        modifications_count: 修改数量
        error_message: 错误消息（失败时）
        error_details: 详细错误信息列表
        original_workflow: 原始工作流（用于回滚）
        modified_workflow: 修改后的工作流
        rag_sources: RAG 检索来源列表
        react_steps: ReAct 推理步骤列表
    """

    success: bool
    ai_message: str
    intent: str = ""
    confidence: float = 0.0
    modifications_count: int = 0
    error_message: str = ""
    error_details: list[str] = field(default_factory=list)
    original_workflow: Workflow | None = None
    modified_workflow: Workflow | None = None
    rag_sources: list[dict] = field(default_factory=list)
    react_steps: list[dict] = field(default_factory=list)

    def has_errors(self) -> bool:
        """是否有错误

        返回：
            True 如果存在错误消息或错误详情
        """
        return bool(self.error_message) or bool(self.error_details)
