"""KnowledgeRetrievalOrchestrator - 知识检索编排器

负责知识检索、缓存管理、上下文增强与注入。
从 CoordinatorAgent 提取（Phase 34.9）。
"""

from typing import Any


class KnowledgeRetrievalOrchestrator:
    """知识检索编排器

    职责：
    - 知识检索（query/error/goal）
    - 缓存管理
    - 上下文增强与注入
    - 自动触发机制
    """

    def __init__(
        self,
        knowledge_retriever: Any | None = None,
        context_gateway: Any | None = None,
    ):
        """初始化知识检索编排器

        参数：
            knowledge_retriever: 知识检索器实例（可选）
            context_gateway: 上下文网关，用于访问压缩上下文（可选）
        """
        self.knowledge_retriever = knowledge_retriever
        self.context_gateway = context_gateway
        self._knowledge_cache: dict[str, Any] = {}
        self._auto_knowledge_retrieval_enabled = False

    # ==================== 知识检索 ====================

    async def retrieve_knowledge(
        self,
        query: str,
        workflow_id: str | None = None,
        top_k: int = 5,
    ) -> Any:
        """按查询检索知识

        参数：
            query: 查询文本
            workflow_id: 工作流ID（可选，用于过滤和缓存）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()

        if not self.knowledge_retriever:
            return refs

        # 检索知识
        results = await self.knowledge_retriever.retrieve_by_query(
            query=query,
            workflow_id=workflow_id,
            top_k=top_k,
        )

        # 转换为 KnowledgeReference
        for result in results:
            ref = KnowledgeReference(
                source_id=result.get("source_id", ""),
                title=result.get("title", ""),
                content_preview=result.get("content_preview", ""),
                relevance_score=result.get("relevance_score", 0.0),
                document_id=result.get("document_id"),
                source_type=result.get("source_type", "knowledge_base"),
            )
            refs.add(ref)

        # 如果指定了 workflow_id，缓存结果
        if workflow_id:
            self._knowledge_cache[workflow_id] = refs

        return refs

    async def retrieve_knowledge_by_error(
        self,
        error_type: str,
        error_message: str | None = None,
        top_k: int = 3,
    ) -> Any:
        """按错误类型检索解决方案

        参数：
            error_type: 错误类型
            error_message: 错误消息（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()

        if not self.knowledge_retriever:
            return refs

        # 检索错误相关知识
        results = await self.knowledge_retriever.retrieve_by_error(
            error_type=error_type,
            error_message=error_message,
            top_k=top_k,
        )

        # 转换为 KnowledgeReference
        for result in results:
            ref = KnowledgeReference(
                source_id=result.get("source_id", ""),
                title=result.get("title", ""),
                content_preview=result.get("content_preview", ""),
                relevance_score=result.get("relevance_score", 0.0),
                source_type=result.get("source_type", "error_solution"),
            )
            refs.add(ref)

        return refs

    async def retrieve_knowledge_by_goal(
        self,
        goal_text: str,
        workflow_id: str | None = None,
        top_k: int = 3,
    ) -> Any:
        """按目标检索相关知识

        参数：
            goal_text: 目标描述文本
            workflow_id: 工作流ID（可选）
            top_k: 返回结果数量

        返回：
            KnowledgeReferences 知识引用集合
        """
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()

        if not self.knowledge_retriever:
            return refs

        # 检索目标相关知识
        results = await self.knowledge_retriever.retrieve_by_goal(
            goal_text=goal_text,
            workflow_id=workflow_id,
            top_k=top_k,
        )

        # 转换为 KnowledgeReference
        for result in results:
            ref = KnowledgeReference(
                source_id=result.get("source_id", ""),
                title=result.get("title", ""),
                content_preview=result.get("content_preview", ""),
                relevance_score=result.get("relevance_score", 0.0),
                document_id=result.get("document_id"),
                source_type=result.get("source_type", "goal_related"),
            )
            refs.add(ref)

        return refs

    # ==================== 缓存管理 ====================

    def get_cached_knowledge(self, workflow_id: str) -> Any:
        """获取缓存的知识引用

        参数：
            workflow_id: 工作流ID

        返回：
            KnowledgeReferences 或 None
        """
        return self._knowledge_cache.get(workflow_id)

    def clear_cached_knowledge(self, workflow_id: str) -> None:
        """清除缓存的知识引用

        参数：
            workflow_id: 工作流ID
        """
        if workflow_id in self._knowledge_cache:
            del self._knowledge_cache[workflow_id]

    # ==================== 上下文增强与注入 ====================

    async def enrich_context_with_knowledge(
        self,
        workflow_id: str,
        goal: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """根据目标和错误丰富上下文

        自动检索与目标和错误相关的知识，并将结果附加到上下文中。

        参数：
            workflow_id: 工作流ID
            goal: 任务目标（可选）
            errors: 错误列表（可选），每个错误包含 error_type 和 message

        返回：
            包含 knowledge_references 的上下文字典
        """
        from src.domain.services.knowledge_reference import KnowledgeReferences

        all_refs = KnowledgeReferences()

        # 基于目标检索知识
        if goal and self.knowledge_retriever:
            goal_refs = await self.retrieve_knowledge_by_goal(
                goal_text=goal,
                workflow_id=workflow_id,
            )
            all_refs = all_refs.merge(goal_refs)

        # 基于错误检索知识
        if errors and self.knowledge_retriever:
            for error in errors:
                error_type = error.get("error_type", "")
                error_message = error.get("message", "")
                if error_type:
                    error_refs = await self.retrieve_knowledge_by_error(
                        error_type=error_type,
                        error_message=error_message,
                    )
                    all_refs = all_refs.merge(error_refs)

        # 去重
        all_refs = all_refs.deduplicate()

        # 缓存结果
        self._knowledge_cache[workflow_id] = all_refs

        # 返回包含知识引用的上下文
        return {
            "workflow_id": workflow_id,
            "knowledge_references": all_refs.to_dict_list(),
        }

    async def inject_knowledge_to_context(
        self,
        workflow_id: str,
        goal: str | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        """向现有压缩上下文注入知识

        参数：
            workflow_id: 工作流ID
            goal: 任务目标（可选）
            errors: 错误列表（可选）
        """
        if not self.context_gateway:
            return

        # 检索知识
        enriched = await self.enrich_context_with_knowledge(
            workflow_id=workflow_id,
            goal=goal,
            errors=errors,
        )

        # 获取上下文并注入知识引用（委托给 gateway 处理去重合并）
        new_refs = enriched.get("knowledge_references", [])
        self.context_gateway.update_knowledge_refs(workflow_id, new_refs)

    def get_knowledge_enhanced_summary(self, workflow_id: str) -> str | None:
        """获取知识增强的上下文摘要

        返回包含知识引用信息的人类可读摘要。

        参数：
            workflow_id: 工作流ID

        返回：
            摘要文本，如果不存在返回None
        """
        if not self.context_gateway:
            return None

        # 获取压缩上下文
        ctx = self.context_gateway.get_context(workflow_id)
        if not ctx:
            return None

        # 生成基础摘要
        summary_parts = []
        if hasattr(ctx, "to_summary_text"):
            summary_parts.append(ctx.to_summary_text())

        # 添加知识引用详情
        if hasattr(ctx, "knowledge_references") and ctx.knowledge_references:
            refs = ctx.knowledge_references
            ref_summaries = []
            for ref in refs[:3]:  # 最多显示3条
                title = ref.get("title", "未知")
                score = ref.get("relevance_score", 0)
                ref_summaries.append(f"  - {title} (相关度: {score:.0%})")

            if ref_summaries:
                summary_parts.append("知识引用:")
                summary_parts.extend(ref_summaries)

        return "\n".join(summary_parts) if summary_parts else None

    def get_context_for_conversation_agent(
        self,
        workflow_id: str,
    ) -> dict[str, Any] | None:
        """获取用于对话Agent的上下文

        将压缩上下文转换为对话Agent可用的格式。

        参数：
            workflow_id: 工作流ID

        返回：
            对话Agent可用的上下文字典，如果不存在返回None
        """
        if not self.context_gateway:
            return None

        ctx = self.context_gateway.get_context(workflow_id)
        if not ctx:
            return None

        # 构建对话Agent可用的上下文
        agent_context = {
            "workflow_id": workflow_id,
            "goal": getattr(ctx, "task_goal", ""),
            "task_goal": getattr(ctx, "task_goal", ""),
            "execution_status": getattr(ctx, "execution_status", {}),
            "node_summary": getattr(ctx, "node_summary", []),
            "errors": getattr(ctx, "error_log", []),
            "next_actions": getattr(ctx, "next_actions", []),
            "conversation_summary": getattr(ctx, "conversation_summary", ""),
            "reflection_summary": getattr(ctx, "reflection_summary", {}),
        }

        # 添加知识引用
        if hasattr(ctx, "knowledge_references"):
            agent_context["knowledge_references"] = ctx.knowledge_references
            agent_context["references"] = ctx.knowledge_references

        # 添加缓存的知识
        cached = self.get_cached_knowledge(workflow_id)
        if cached is not None and hasattr(cached, "to_dict_list"):
            agent_context["cached_knowledge"] = cached.to_dict_list()

        return agent_context

    # ==================== 自动触发机制 ====================

    async def auto_enrich_context_on_error(
        self,
        workflow_id: str,
        error_type: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """错误发生时自动丰富上下文

        当节点执行失败时，自动检索相关的错误解决方案知识。

        参数：
            workflow_id: 工作流ID
            error_type: 错误类型
            error_message: 错误消息（可选）

        返回：
            丰富后的上下文字典
        """
        # 构建错误列表
        errors = [{"error_type": error_type, "message": error_message or ""}]

        # 获取现有目标
        goal = None
        if self.context_gateway:
            ctx = self.context_gateway.get_context(workflow_id)
            if ctx:
                goal = getattr(ctx, "task_goal", None)

        # 丰富上下文
        enriched = await self.enrich_context_with_knowledge(
            workflow_id=workflow_id,
            goal=goal,
            errors=errors,
        )

        # 注入到压缩上下文
        await self.inject_knowledge_to_context(
            workflow_id=workflow_id,
            errors=errors,
        )

        return enriched

    def enable_auto_knowledge_retrieval(self) -> None:
        """启用自动知识检索

        启用后，在节点失败和反思事件时会自动检索相关知识。
        """
        self._auto_knowledge_retrieval_enabled = True

    def disable_auto_knowledge_retrieval(self) -> None:
        """禁用自动知识检索"""
        self._auto_knowledge_retrieval_enabled = False

    async def handle_node_failure_with_knowledge(
        self,
        workflow_id: str,
        node_id: str,
        error_type: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """处理节点失败并检索相关知识

        当节点执行失败时调用此方法，会自动检索与错误相关的知识，
        并将其添加到压缩上下文中。

        参数：
            workflow_id: 工作流ID
            node_id: 失败的节点ID
            error_type: 错误类型
            error_message: 错误消息（可选）

        返回：
            包含知识引用的结果字典
        """
        # 记录错误到错误日志（通过 context_gateway）
        if self.context_gateway:
            ctx = self.context_gateway.get_context(workflow_id)
            if ctx:
                self.context_gateway.update_error_log(
                    workflow_id,
                    {
                        "node_id": node_id,
                        "error_type": error_type,
                        "error_message": error_message or "",
                    },
                )

        # 自动检索错误相关知识
        result = await self.auto_enrich_context_on_error(
            workflow_id=workflow_id,
            error_type=error_type,
            error_message=error_message,
        )

        return result

    async def handle_reflection_with_knowledge(
        self,
        workflow_id: str,
        assessment: str,
        confidence: float = 0.0,
        recommendations: list[str] | None = None,
    ) -> dict[str, Any]:
        """处理反思事件并检索相关知识

        当收到反思事件时调用此方法，会基于工作流目标检索相关知识。

        参数：
            workflow_id: 工作流ID
            assessment: 评估内容
            confidence: 置信度
            recommendations: 建议列表（可选）

        返回：
            包含知识引用的结果字典
        """
        # 更新反思摘要（通过 context_gateway）
        if self.context_gateway:
            ctx = self.context_gateway.get_context(workflow_id)
            if ctx:
                self.context_gateway.update_reflection(
                    workflow_id,
                    {
                        "assessment": assessment,
                        "confidence": confidence,
                        "recommendations": recommendations or [],
                    },
                )

        # 获取目标并检索相关知识
        goal = None
        if self.context_gateway:
            ctx = self.context_gateway.get_context(workflow_id)
            if ctx:
                goal = getattr(ctx, "task_goal", None)

        # 基于目标和评估检索知识
        result = await self.enrich_context_with_knowledge(
            workflow_id=workflow_id,
            goal=goal or assessment,  # 如果没有目标，使用评估内容
        )

        # 注入到上下文
        await self.inject_knowledge_to_context(
            workflow_id=workflow_id,
            goal=goal or assessment,
        )

        return result
