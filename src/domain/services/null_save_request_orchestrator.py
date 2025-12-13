"""NullSaveRequestOrchestrator - SaveRequestOrchestrator的空对象实现

当event_bus=None时使用，所有方法为no-op或返回默认值。
符合Null Object模式，消除调用方的None检查。

设计原则：
- 保持与SaveRequestOrchestrator相同的接口签名
- 返回值与None检查分支的默认值一致
- 不抛异常（除非真实实现也抛异常）
- 不产生副作用（无EventBus通信、无文件操作）

使用示例::

    # Bootstrap中
    if self.config.event_bus is not None:
        orchestrator = SaveRequestOrchestrator(...)
    else:
        orchestrator = NullSaveRequestOrchestrator()

    # CoordinatorAgent中
    self._save_request_orchestrator.enable_save_request_handler()  # No-op
    count = self._save_request_orchestrator.get_pending_save_request_count()  # 返回0
"""

from __future__ import annotations

from typing import Any


class NullSaveRequestOrchestrator:
    """SaveRequestOrchestrator的空对象实现

    当CoordinatorAgent初始化时event_bus=None，将使用此空对象实现。
    所有方法为no-op或返回默认值，避免调用方进行None检查。
    """

    # ==================== 事件订阅/取消订阅 ====================

    def enable_save_request_handler(self) -> None:
        """No-op: 无EventBus时不启用处理器"""
        pass

    def disable_save_request_handler(self) -> None:
        """No-op: 无EventBus时不禁用处理器"""
        pass

    # ==================== 队列查询 ====================

    def has_pending_save_requests(self) -> bool:
        """No-op: 无队列时总是返回False

        返回：
            False（无待处理请求）
        """
        return False

    def get_pending_save_request_count(self) -> int:
        """No-op: 无队列时返回0

        返回：
            0（无待处理请求）
        """
        return 0

    def get_save_request_queue(self) -> list[Any]:
        """No-op: 无队列时返回空列表

        返回：
            空列表
        """
        return []

    def get_save_request_status(self, request_id: str) -> Any:
        """No-op: 无队列时返回PENDING状态

        参数：
            request_id: 请求ID（忽略）

        返回：
            SaveRequestStatus.PENDING
        """
        from src.domain.services.save_request_channel import SaveRequestStatus

        return SaveRequestStatus.PENDING

    def get_save_requests_by_session(self, session_id: str) -> list[Any]:
        """No-op: 无队列时返回空列表

        参数：
            session_id: 会话ID（忽略）

        返回：
            空列表
        """
        return []

    def dequeue_save_request(self) -> Any | None:
        """No-op: 无队列时返回None

        返回：
            None（队列为空）
        """
        return None

    # ==================== 审核与执行配置 ====================

    def configure_save_auditor(
        self,
        path_whitelist: list[str] | None = None,
        path_blacklist: list[str] | None = None,
        max_content_size: int = 10 * 1024 * 1024,
        enable_rate_limit: bool = True,
        enable_sensitive_check: bool = True,
    ) -> None:
        """抛出异常: 无EventBus时不支持审核器配置

        此方法的行为与SaveRequestOrchestrator.__init__一致。
        当event_bus=None时，真实实现在初始化时抛出ValueError，
        Null实现在配置时抛出相同异常。

        参数：
            path_whitelist: 路径白名单（忽略）
            path_blacklist: 路径黑名单（忽略）
            max_content_size: 最大内容大小（忽略）
            enable_rate_limit: 是否启用频率限制（忽略）
            enable_sensitive_check: 是否启用敏感内容检查（忽略）

        异常：
            ValueError: 总是抛出（event_bus required）
        """
        raise ValueError("SaveRequestOrchestrator not initialized (event_bus required)")

    # ==================== 审核与执行 ====================

    async def process_next_save_request(self) -> Any | None:
        """No-op: 无队列时返回None

        返回：
            None（队列为空）
        """
        return None

    def get_save_audit_logs(self) -> list[dict]:
        """No-op: 无审核器时返回空列表

        返回：
            空列表
        """
        return []

    def get_save_audit_logs_by_session(self, session_id: str) -> list[dict]:
        """No-op: 无审核器时返回空列表

        参数：
            session_id: 会话ID（忽略）

        返回：
            空列表
        """
        return []

    # ==================== 回执系统 ====================

    async def send_save_result_receipt(
        self,
        session_id: str,
        request_id: str,
        success: bool,
        message: str,
        error_code: str | None = None,
        error_message: str | None = None,
        violation_severity: str | None = None,
        audit_trail: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """No-op: 无回执系统时返回空处理结果

        返回值结构与 SaveResultReceiptSystem.process_result() 一致。

        参数：
            session_id: 会话ID（忽略）
            request_id: 请求ID
            success: 是否成功（忽略）
            message: 状态消息（忽略）
            error_code: 错误代码（忽略）
            error_message: 错误信息（忽略）
            violation_severity: 违规严重级别（忽略）
            audit_trail: 审计追踪信息（忽略）

        返回：
            处理结果字典（所有操作均失败）
        """
        return {
            "request_id": request_id,
            "recorded_to_short_term": False,
            "recorded_to_medium_term": False,
            "written_to_knowledge_base": False,
            "knowledge_entry_id": None,
        }

    async def process_save_request_with_receipt(self) -> dict[str, Any] | None:
        """No-op: 无队列时返回None

        返回：
            None（队列为空）
        """
        return None

    def get_save_receipt_context(self, session_id: str) -> dict[str, Any]:
        """No-op: 无回执系统时返回空字典

        参数：
            session_id: 会话ID（忽略）

        返回：
            空字典
        """
        return {}

    def get_save_receipt_chain_log(self, request_id: str) -> dict[str, Any] | None:
        """No-op: 无回执系统时返回None

        参数：
            request_id: 请求ID（忽略）

        返回：
            None
        """
        return None

    def get_save_receipt_logs(self) -> list[dict[str, Any]]:
        """No-op: 无回执系统时返回空列表

        返回：
            空列表
        """
        return []

    def get_session_save_statistics(self, session_id: str) -> dict[str, Any]:
        """No-op: 无回执系统时返回零值统计

        返回值结构与 SaveResultMemoryHandler.get_session_statistics() 一致。

        参数：
            session_id: 会话ID（忽略）

        返回：
            零值统计字典
        """
        return {
            "total_requests": 0,
            "success_count": 0,
            "rejected_count": 0,
            "failed_count": 0,
            "success_rate": 0.0,
        }


__all__ = ["NullSaveRequestOrchestrator"]
