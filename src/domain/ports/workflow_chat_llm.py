"""Workflow Chat LLM 接口

该端口定义了领域层对大模型的最小依赖，避免直接耦合任意 LLM SDK。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class WorkflowChatLLM(Protocol):
    """用于工作流对话场景的大模型能力接口。"""

    def generate_modifications(self, system_prompt: str, user_prompt: str) -> dict:
        """根据系统提示词与用户输入生成结构化的工作流修改指令。"""
        ...

    async def generate_modifications_async(self, system_prompt: str, user_prompt: str) -> dict:
        """异步生成工作流修改指令。"""
        ...
