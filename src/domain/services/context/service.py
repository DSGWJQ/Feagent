"""上下文服务

Phase 35.1: 从 CoordinatorAgent 提取的上下文查询与工具/知识筛选逻辑
"""

from collections.abc import Callable
from typing import Any, Protocol

from src.domain.services.context.models import ContextResponse


class WorkflowContextProvider(Protocol):
    """工作流上下文提供者协议"""

    def get(self, workflow_id: str) -> dict[str, Any] | None:
        """获取工作流上下文"""
        ...


class ContextService:
    """上下文服务

    负责查询规则/工具/知识并组装 ContextResponse。

    Phase 35.1: 从 CoordinatorAgent 提取，解耦上下文查询逻辑。

    依赖：
        - rule_provider: 规则提供者（callable 返回规则列表）
        - tool_repository: 工具仓库（实现 find_published/find_all/find_by_tags）
        - knowledge_retriever: 知识检索器（实现 retrieve_by_query）
        - workflow_context_provider: 工作流上下文提供者（dict 或 Protocol）
    """

    def __init__(
        self,
        rule_provider: Callable[[], list[Any]],
        tool_repository: Any | None = None,
        knowledge_retriever: Any | None = None,
        workflow_context_provider: Any | None = None,
    ):
        """初始化上下文服务

        参数：
            rule_provider: 规则提供者函数
            tool_repository: 工具仓库（可选）
            knowledge_retriever: 知识检索器（可选）
            workflow_context_provider: 工作流上下文提供者（可选）
        """
        self._rule_provider = rule_provider
        self._tool_repository = tool_repository
        self._knowledge_retriever = knowledge_retriever
        self._workflow_context_provider = workflow_context_provider

    def get_context(
        self,
        user_input: str,
        workflow_id: str | None = None,
    ) -> ContextResponse:
        """获取上下文信息（同步版本）

        根据用户输入，查询规则库、工具库，返回相关上下文。
        同步版本不查询知识库。

        参数：
            user_input: 用户输入文本
            workflow_id: 可选的工作流ID，用于获取工作流上下文

        返回：
            ContextResponse 包含规则、工具和摘要
        """
        rules = self._build_rules()
        tools = self._find_tools(user_input)
        workflow_ctx = self._get_workflow_context(workflow_id)
        summary = self._build_summary(user_input, len(rules), len(tools), 0)

        return ContextResponse(
            rules=rules,
            knowledge=[],  # 同步版本不查询知识库
            tools=tools,
            summary=summary,
            workflow_context=workflow_ctx,
        )

    async def get_context_async(
        self,
        user_input: str,
        workflow_id: str | None = None,
    ) -> ContextResponse:
        """获取上下文信息（异步版本）

        根据用户输入，异步查询规则库、知识库、工具库，返回相关上下文。

        参数：
            user_input: 用户输入文本
            workflow_id: 可选的工作流ID，用于获取工作流上下文

        返回：
            ContextResponse 包含规则、知识、工具和摘要
        """
        rules = self._build_rules()
        knowledge = await self._retrieve_knowledge(user_input, workflow_id)
        tools = self._find_tools(user_input)
        workflow_ctx = self._get_workflow_context(workflow_id)
        summary = self._build_summary(user_input, len(rules), len(tools), len(knowledge))

        return ContextResponse(
            rules=rules,
            knowledge=knowledge,
            tools=tools,
            summary=summary,
            workflow_context=workflow_ctx,
        )

    def get_available_tools(self) -> list[dict[str, Any]]:
        """获取所有可用工具

        返回：
            工具字典列表
        """
        if not self._tool_repository:
            return []

        try:
            all_tools = self._tool_repository.find_all()
            return [
                {
                    "id": getattr(tool, "id", ""),
                    "name": getattr(tool, "name", ""),
                    "description": getattr(tool, "description", ""),
                    "category": getattr(tool, "category", ""),
                }
                for tool in all_tools
            ]
        except Exception:
            return []

    def find_tools_by_query(self, query: str) -> list[dict[str, Any]]:
        """按查询找到相关工具

        参数：
            query: 查询字符串（可以是关键词或标签）

        返回：
            匹配的工具列表
        """
        if not self._tool_repository:
            return []

        try:
            # 尝试按标签查找
            if hasattr(self._tool_repository, "find_by_tags"):
                tools = self._tool_repository.find_by_tags([query])
                return [
                    {
                        "id": getattr(tool, "id", ""),
                        "name": getattr(tool, "name", ""),
                        "description": getattr(tool, "description", ""),
                    }
                    for tool in tools
                ]
            return []
        except Exception:
            return []

    def _build_rules(self) -> list[dict[str, Any]]:
        """构建规则列表

        返回：
            规则字典列表
        """
        return [
            {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "priority": rule.priority,
            }
            for rule in self._rule_provider()
        ]

    async def _retrieve_knowledge(
        self,
        user_input: str,
        workflow_id: str | None,
    ) -> list[dict[str, Any]]:
        """异步检索知识

        参数：
            user_input: 用户输入
            workflow_id: 工作流ID

        返回：
            知识条目列表
        """
        if not self._knowledge_retriever:
            return []

        try:
            results = await self._knowledge_retriever.retrieve_by_query(
                query=user_input,
                workflow_id=workflow_id,
                top_k=5,
            )
            return results
        except Exception:
            return []

    def _find_tools(self, user_input: str) -> list[dict[str, Any]]:
        """查找相关工具

        根据用户输入的关键词匹配工具

        参数：
            user_input: 用户输入

        返回：
            工具字典列表
        """
        if not self._tool_repository:
            return []

        try:
            # 获取所有已发布的工具
            all_tools = self._tool_repository.find_published()

            # 简单的关键词匹配
            input_lower = user_input.lower()
            keywords = input_lower.split()

            matched_tools = []
            for tool in all_tools:
                # 检查工具名称、描述或标签是否匹配关键词
                tool_text = (
                    getattr(tool, "name", "").lower()
                    + " "
                    + getattr(tool, "description", "").lower()
                    + " "
                    + " ".join(getattr(tool, "tags", []))
                ).lower()

                if any(kw in tool_text for kw in keywords) or not user_input:
                    matched_tools.append(
                        {
                            "id": getattr(tool, "id", ""),
                            "name": getattr(tool, "name", ""),
                            "description": getattr(tool, "description", ""),
                            "category": getattr(tool, "category", ""),
                        }
                    )

            return matched_tools
        except Exception:
            return []

    def _get_workflow_context(self, workflow_id: str | None) -> dict[str, Any] | None:
        """获取工作流上下文

        参数：
            workflow_id: 工作流ID

        返回：
            工作流上下文字典（浅拷贝）
        """
        if not workflow_id or not self._workflow_context_provider:
            return None

        provider = self._workflow_context_provider

        # 支持 dict 或 Protocol 两种方式
        if isinstance(provider, dict):
            context = provider.get(workflow_id)
        elif hasattr(provider, "get"):
            context = provider.get(workflow_id)
        else:
            return None

        # 返回浅拷贝以防止引用污染
        return context.copy() if isinstance(context, dict) else context

    def _build_summary(
        self,
        user_input: str,
        rules_count: int,
        tools_count: int,
        knowledge_count: int,
    ) -> str:
        """生成上下文摘要

        参数：
            user_input: 用户输入
            rules_count: 规则数量
            tools_count: 工具数量
            knowledge_count: 知识条目数量

        返回：
            摘要文本
        """
        parts = []

        if user_input:
            parts.append(f"用户输入: {user_input[:50]}{'...' if len(user_input) > 50 else ''}")

        parts.append(f"可用规则: {rules_count}")
        parts.append(f"相关工具: {tools_count}")

        if knowledge_count > 0:
            parts.append(f"知识条目: {knowledge_count}")

        return " | ".join(parts)


__all__ = ["ContextService", "WorkflowContextProvider"]
