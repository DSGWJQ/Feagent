"""Token Guardrail - Step 6

业务定义：
- 规划前检查 token 预算
- 为长链路工作流设置 token 保护
- 自动触发压缩以确保预算充足

设计原则：
- 预防性检查，避免执行中断
- 可配置的阈值
- 支持工作流预估
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.domain.services.context_manager import SessionContext
from src.domain.services.memory_compression_handler import BufferCompressor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BudgetStatus(Enum):
    """预算状态枚举"""

    OK = "ok"  # 预算充足
    COMPRESS_RECOMMENDED = "compress_recommended"  # 建议压缩
    CRITICAL = "critical"  # 临界状态


@dataclass
class WorkflowFeasibility:
    """工作流可行性评估结果"""

    is_feasible: bool
    needs_compression: bool
    remaining_budget: int
    estimated_required: int
    message: str


class TokenGuardrail:
    """Token Guardrail

    职责：
    - 检查 token 预算状态
    - 评估工作流可行性
    - 触发预规划压缩
    - 生成预算报告

    使用示例：
        guardrail = TokenGuardrail(pre_planning_threshold=0.85)
        status = guardrail.check_budget(session)

        if status == BudgetStatus.COMPRESS_RECOMMENDED:
            await guardrail.ensure_budget_for_planning(session)
    """

    # 默认每种节点类型的 token 估算
    DEFAULT_NODE_TOKEN_ESTIMATES = {
        "llm": 800,
        "code": 200,
        "http": 100,
        "condition": 50,
        "default": 300,
    }

    def __init__(
        self,
        pre_planning_threshold: float = 0.85,
        critical_threshold: float = 0.95,
        keep_recent_turns: int = 2,
        compressor: BufferCompressor | None = None,
    ):
        """初始化 Guardrail

        参数：
            pre_planning_threshold: 规划前压缩阈值
            critical_threshold: 临界阈值
            keep_recent_turns: 压缩后保留的轮次数
            compressor: 压缩器实例
        """
        self.pre_planning_threshold = pre_planning_threshold
        self.critical_threshold = critical_threshold
        self._keep_recent_turns = keep_recent_turns
        self._compressor = compressor or BufferCompressor()

    @classmethod
    def for_model(cls, model_name: str, context_limit: int) -> "TokenGuardrail":
        """根据模型创建 Guardrail

        大上下文模型可以使用更高的阈值。

        参数：
            model_name: 模型名称
            context_limit: 上下文限制

        返回：
            配置好的 TokenGuardrail 实例
        """
        # 大上下文模型（>32k）可以使用更高阈值
        if context_limit >= 32000:
            return cls(pre_planning_threshold=0.90, critical_threshold=0.97)
        # 中等上下文（8k-32k）
        elif context_limit >= 8000:
            return cls(pre_planning_threshold=0.85, critical_threshold=0.95)
        # 小上下文（<8k）
        else:
            return cls(pre_planning_threshold=0.75, critical_threshold=0.90)

    def check_budget(self, session: SessionContext) -> BudgetStatus:
        """检查预算状态

        参数：
            session: 会话上下文

        返回：
            BudgetStatus 枚举值
        """
        usage_ratio = session.get_usage_ratio()

        if usage_ratio >= self.critical_threshold:
            return BudgetStatus.CRITICAL
        elif usage_ratio >= self.pre_planning_threshold:
            return BudgetStatus.COMPRESS_RECOMMENDED
        else:
            return BudgetStatus.OK

    async def ensure_budget_for_planning(self, session: SessionContext) -> bool:
        """确保规划前有足够预算

        如果预算不足，执行压缩。

        参数：
            session: 会话上下文

        返回：
            是否执行了压缩
        """
        status = self.check_budget(session)

        if status == BudgetStatus.OK:
            logger.debug(f"Budget OK for session {session.session_id}")
            return False

        logger.info(
            f"Compressing before planning for session {session.session_id}, "
            f"usage: {session.get_usage_ratio():.1%}"
        )

        # 执行压缩
        await self._compress_session(session)

        return True

    async def _compress_session(self, session: SessionContext) -> None:
        """执行会话压缩"""
        if not session.short_term_buffer:
            logger.warning(f"No buffers to compress for session {session.session_id}")
            return

        # 冻结会话
        session.freeze()

        try:
            # 执行压缩
            summary = await self._compressor.compress(
                session.short_term_buffer,
                session.conversation_summary,
            )

            # 回写摘要
            session.compress_buffer_with_summary(summary, self._keep_recent_turns)

            logger.info(
                f"Pre-planning compression completed for session {session.session_id}, "
                f"kept {len(session.short_term_buffer)} turns"
            )

        finally:
            # 解冻会话
            session.unfreeze()
            session.reset_saturation()

    def estimate_workflow_tokens(self, workflow_nodes: list[dict[str, Any]]) -> int:
        """估算工作流 token 需求

        参数：
            workflow_nodes: 工作流节点列表

        返回：
            估算的总 token 数
        """
        total = 0

        for node in workflow_nodes:
            # 优先使用节点指定的估算值
            if "estimated_tokens" in node:
                total += node["estimated_tokens"]
            else:
                # 否则根据类型使用默认值
                node_type = node.get("type", "default")
                total += self.DEFAULT_NODE_TOKEN_ESTIMATES.get(
                    node_type, self.DEFAULT_NODE_TOKEN_ESTIMATES["default"]
                )

        return total

    def check_workflow_feasibility(
        self, session: SessionContext, workflow_nodes: list[dict[str, Any]]
    ) -> WorkflowFeasibility:
        """检查工作流可行性

        参数：
            session: 会话上下文
            workflow_nodes: 工作流节点列表

        返回：
            WorkflowFeasibility 评估结果
        """
        remaining = session.get_remaining_tokens()
        estimated = self.estimate_workflow_tokens(workflow_nodes)

        # 留出 20% 的缓冲
        buffer_ratio = 0.2
        effective_remaining = int(remaining * (1 - buffer_ratio))

        if effective_remaining >= estimated:
            return WorkflowFeasibility(
                is_feasible=True,
                needs_compression=False,
                remaining_budget=remaining,
                estimated_required=estimated,
                message="预算充足，可以执行工作流",
            )
        elif remaining >= estimated:
            return WorkflowFeasibility(
                is_feasible=True,
                needs_compression=True,
                remaining_budget=remaining,
                estimated_required=estimated,
                message="预算紧张，建议压缩后执行",
            )
        else:
            return WorkflowFeasibility(
                is_feasible=False,
                needs_compression=True,
                remaining_budget=remaining,
                estimated_required=estimated,
                message=f"预算不足，需要 {estimated} tokens，仅剩 {remaining} tokens",
            )

    async def prepare_for_workflow(
        self, session: SessionContext, workflow_nodes: list[dict[str, Any]]
    ) -> WorkflowFeasibility:
        """为工作流准备预算

        检查可行性，必要时执行压缩。

        参数：
            session: 会话上下文
            workflow_nodes: 工作流节点列表

        返回：
            最终的可行性评估
        """
        feasibility = self.check_workflow_feasibility(session, workflow_nodes)

        if feasibility.needs_compression and session.short_term_buffer:
            logger.info(f"Compressing before workflow execution: {feasibility.message}")
            await self._compress_session(session)

            # 重新评估
            feasibility = self.check_workflow_feasibility(session, workflow_nodes)

        return feasibility

    def get_recommended_compression_point(self, session: SessionContext) -> int:
        """获取推荐的压缩点

        根据缓冲区大小和使用率推荐应该压缩的轮次数。

        参数：
            session: 会话上下文

        返回：
            推荐保留的轮次数
        """
        buffer_size = len(session.short_term_buffer)

        if buffer_size <= 3:
            return buffer_size  # 太少，不压缩

        usage_ratio = session.get_usage_ratio()

        if usage_ratio >= 0.9:
            # 高使用率，只保留最少
            return min(2, buffer_size)
        elif usage_ratio >= 0.8:
            # 中等使用率，保留少量
            return min(3, buffer_size)
        else:
            # 低使用率，可以保留更多
            return min(5, buffer_size)

    def get_budget_report(self, session: SessionContext) -> dict[str, Any]:
        """获取预算报告

        参数：
            session: 会话上下文

        返回：
            预算报告字典
        """
        status = self.check_budget(session)
        usage_summary = session.get_token_usage_summary()

        report = {
            "session_id": session.session_id,
            "total_tokens": usage_summary["total_tokens"],
            "usage_ratio": usage_summary["usage_ratio"],
            "remaining_tokens": usage_summary["remaining_tokens"],
            "context_limit": usage_summary["context_limit"],
            "status": status.value,
            "buffer_size": len(session.short_term_buffer),
            "has_summary": session.conversation_summary is not None,
        }

        # 添加建议
        if status == BudgetStatus.CRITICAL:
            report["recommendation"] = "立即压缩，token 即将耗尽"
        elif status == BudgetStatus.COMPRESS_RECOMMENDED:
            report["recommendation"] = "建议在规划前压缩上下文"
        else:
            report["recommendation"] = None

        return report


# 导出
__all__ = [
    "BudgetStatus",
    "WorkflowFeasibility",
    "TokenGuardrail",
]
