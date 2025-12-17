"""WorkflowChatService Port - 工作流对话服务端口

Domain 层接口定义，用于解耦具体实现。

设计原则：
- Protocol 定义最小接口契约
- 支持基础版和增强版实现
- 避免 Domain 层对具体框架的依赖
"""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.workflow import Workflow
from src.domain.value_objects.workflow_modification_result import ModificationResult


class WorkflowChatServicePort(Protocol):
    """工作流对话服务端口

    职责：
    - 处理用户的自然语言消息
    - 生成工作流修改指令
    - 应用修改到工作流实体
    - 管理对话历史

    实现要求：
    - 实现类必须提供 process_message 方法
    - 支持对话历史管理（可选）
    - 支持工作流优化建议（可选）
    """

    def process_message(self, workflow: Workflow, user_message: str) -> ModificationResult:
        """处理用户消息并修改工作流

        参数：
            workflow: 当前工作流实体
            user_message: 用户消息

        返回：
            ModificationResult: 包含修改结果和详细信息

        抛出：
            DomainError: 当消息为空或处理失败时
        """
        ...

    def add_message(self, content: str, is_user: bool) -> None:
        """添加消息到对话历史

        参数：
            content: 消息内容
            is_user: 是否来自用户
        """
        ...

    def clear_history(self) -> None:
        """清空对话历史"""
        ...

    def get_workflow_suggestions(self, workflow: Workflow) -> list[str]:
        """根据工作流结构提供优化建议

        参数：
            workflow: 工作流实体

        返回：
            建议列表
        """
        ...
