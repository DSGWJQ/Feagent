"""PowerCompressorFacade - PowerCompressor 包装器

业务职责：
- 包装 PowerCompressor 压缩功能
- 管理压缩上下文存储
- 提供八段数据查询接口
- 生成统计信息

设计原则：
- 简单包装，不改变 PowerCompressor 行为
- 直接初始化，无懒加载
- 返回副本保护数据一致性
- 支持可选 PowerCompressor 注入

使用示例：
    facade = PowerCompressorFacade()

    # 压缩并存储
    compressed = await facade.compress_and_store(summary)

    # 查询
    context = facade.query_compressed_context(workflow_id)
    errors = facade.query_subtask_errors(workflow_id)
"""

import copy
from typing import Any


class PowerCompressorFacade:
    """PowerCompressor 包装器

    负责压缩上下文的存储、查询和统计。
    """

    def __init__(self, power_compressor: Any | None = None):
        """初始化 PowerCompressor Facade

        参数：
            power_compressor: PowerCompressor 实例（可选，懒加载）
        """
        self._power_compressor = power_compressor
        self._compressed_contexts: dict[str, dict[str, Any]] = {}

    @property
    def power_compressor(self) -> Any:
        """获取 PowerCompressor 实例（懒加载）"""
        if self._power_compressor is None:
            from src.domain.services.power_compressor import PowerCompressor

            self._power_compressor = PowerCompressor()
        return self._power_compressor

    async def compress_and_store(self, summary: Any) -> Any:
        """压缩执行总结并存储

        使用 PowerCompressor 压缩执行总结，生成八段格式的压缩上下文，
        并存储到内部缓存中。

        参数：
            summary: ExecutionSummary 实例

        返回：
            PowerCompressedContext 实例
        """
        # 使用压缩器压缩总结
        compressed = self.power_compressor.compress_summary(summary)

        # 转换为字典并存储
        workflow_id = getattr(compressed, "workflow_id", "")
        if workflow_id:
            self._compressed_contexts[workflow_id] = compressed.to_dict()

        return compressed

    def store_compressed_context(self, workflow_id: str, data: dict[str, Any]) -> None:
        """存储压缩上下文

        直接存储已格式化的压缩上下文数据。

        参数：
            workflow_id: 工作流ID
            data: 压缩上下文数据字典
        """
        self._compressed_contexts[workflow_id] = data

    def query_compressed_context(self, workflow_id: str) -> dict[str, Any] | None:
        """查询压缩上下文

        参数：
            workflow_id: 工作流ID

        返回：
            压缩上下文字典（副本），如果不存在返回 None
        """
        ctx = self._compressed_contexts.get(workflow_id)
        # 返回副本保护内部状态
        return copy.deepcopy(ctx) if ctx is not None else None

    def query_subtask_errors(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询子任务错误

        参数：
            workflow_id: 工作流ID

        返回：
            子任务错误列表
        """
        ctx = self._compressed_contexts.get(workflow_id)
        if ctx:
            return ctx.get("subtask_errors", [])
        return []

    def query_unresolved_issues(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询未解决问题

        参数：
            workflow_id: 工作流ID

        返回：
            未解决问题列表
        """
        ctx = self._compressed_contexts.get(workflow_id)
        if ctx:
            return ctx.get("unresolved_issues", [])
        return []

    def query_next_plan(self, workflow_id: str) -> list[dict[str, Any]]:
        """查询后续计划

        参数：
            workflow_id: 工作流ID

        返回：
            后续计划列表
        """
        ctx = self._compressed_contexts.get(workflow_id)
        if ctx:
            return ctx.get("next_plan", [])
        return []

    def get_context_for_conversation(self, workflow_id: str) -> dict[str, Any] | None:
        """获取用于对话Agent下一轮输入的上下文

        返回包含所有八段压缩信息的上下文，供对话Agent引用。

        参数：
            workflow_id: 工作流ID

        返回：
            对话Agent可用的上下文字典，如果不存在返回 None
        """
        ctx = self._compressed_contexts.get(workflow_id)
        if not ctx:
            return None

        # 返回完整的八段上下文
        return {
            "workflow_id": ctx.get("workflow_id", workflow_id),
            "task_goal": ctx.get("task_goal", ""),
            "execution_status": ctx.get("execution_status", {}),
            "node_summary": ctx.get("node_summary", []),
            "subtask_errors": ctx.get("subtask_errors", []),
            "unresolved_issues": ctx.get("unresolved_issues", []),
            "decision_history": ctx.get("decision_history", []),
            "next_plan": ctx.get("next_plan", []),
            "knowledge_sources": ctx.get("knowledge_sources", []),
        }

    def get_knowledge_for_conversation(self, workflow_id: str) -> list[dict[str, Any]]:
        """获取用于对话Agent引用的知识来源

        参数：
            workflow_id: 工作流ID

        返回：
            知识来源列表
        """
        ctx = self._compressed_contexts.get(workflow_id)
        if ctx:
            return ctx.get("knowledge_sources", [])
        return []

    def get_statistics(self) -> dict[str, Any]:
        """获取强力压缩器统计

        返回：
            包含统计信息的字典
        """
        total = len(self._compressed_contexts)
        total_errors = sum(
            len(ctx.get("subtask_errors", [])) for ctx in self._compressed_contexts.values()
        )
        total_issues = sum(
            len(ctx.get("unresolved_issues", [])) for ctx in self._compressed_contexts.values()
        )
        total_plans = sum(
            len(ctx.get("next_plan", [])) for ctx in self._compressed_contexts.values()
        )

        return {
            "total_contexts": total,
            "total_subtask_errors": total_errors,
            "total_unresolved_issues": total_issues,
            "total_next_plan_items": total_plans,
        }
