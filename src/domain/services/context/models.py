"""上下文服务数据模型

Phase 35.1: 从 CoordinatorAgent 提取的数据结构
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextResponse:
    """上下文响应结构（Phase 1）

    协调者返回给对话Agent的上下文信息，包含：
    - rules: 相关规则列表
    - knowledge: 相关知识库条目
    - tools: 可用工具列表
    - summary: 上下文摘要文本
    - workflow_context: 可选的工作流上下文

    属性：
        rules: 规则字典列表，每个包含 id, name, description
        knowledge: 知识条目列表，每个包含 source_id, title, content_preview
        tools: 工具字典列表，每个包含 id, name, description
        summary: 人类可读的上下文摘要
        workflow_context: 当前工作流的状态上下文（可选）
    """

    rules: list[dict[str, Any]] = field(default_factory=list)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    workflow_context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "rules": self.rules,
            "knowledge": self.knowledge,
            "tools": self.tools,
            "summary": self.summary,
        }
        if self.workflow_context is not None:
            result["workflow_context"] = self.workflow_context
        return result


__all__ = ["ContextResponse"]
