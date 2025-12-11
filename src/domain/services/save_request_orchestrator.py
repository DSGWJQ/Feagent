"""SaveRequestOrchestrator - SaveRequest 全流程编排器

职责:
- SaveRequest 事件订阅与入队
- 队列管理（查询、出队）
- 审核与执行（规则装配、审核、执行、审计记录）
- 回执生成与事件发布
- 统计与查询

设计要点:
- 从 CoordinatorAgent 提取的独立服务
- 懒加载审核器初始化
- 方法签名与 CoordinatorAgent 完全一致（便于代理）
- 事件驱动架构

使用示例::

    orchestrator = SaveRequestOrchestrator(
        event_bus=bus,
        knowledge_manager=km
    )
    orchestrator.enable_save_request_handler()
    ...
    result = orchestrator.process_save_request_with_receipt()
"""

from __future__ import annotations

import logging
from typing import Any

from src.domain.services.event_bus import EventBus

logger = logging.getLogger(__name__)


class SaveRequestOrchestrator:
    """SaveRequest 全流程编排器

    负责 SaveRequest 的事件订阅、入队、审核与执行，以及结果回执发布。

    属性:
        event_bus: 事件总线实例
        knowledge_manager: 知识管理器（用于回执系统）
        log_collector: 日志收集器（可选）
    """

    def __init__(
        self,
        event_bus: EventBus,
        knowledge_manager: Any,
        log_collector: Any | None = None,
    ) -> None:
        """初始化 SaveRequest 编排器

        参数:
            event_bus: 事件总线实例（必需）
            knowledge_manager: 知识管理器实例（必需，用于回执）
            log_collector: 日志收集器实例（可选）

        异常:
            ValueError: 如果 event_bus 为 None
        """
        if event_bus is None:
            raise ValueError("event_bus is required")

        self.event_bus = event_bus
        self.knowledge_manager = knowledge_manager
        self.log_collector = log_collector

        # 队列管理
        from src.domain.services.save_request_channel import SaveRequestQueueManager

        self._save_request_queue = SaveRequestQueueManager()
        self._save_request_handler_enabled = False
        self._is_listening_save_requests = False

        # 审核与执行（懒加载）
        self._save_auditor: Any | None = None
        self._save_executor: Any | None = None
        self._save_audit_logger: Any | None = None

        # 回执系统
        from src.domain.services.save_request_receipt import SaveResultReceiptSystem

        self.save_receipt_system = SaveResultReceiptSystem(
            knowledge_manager=self.knowledge_manager,
            short_term_limit=10,
        )

    # ==================== 事件订阅/取消订阅 ====================

    def enable_save_request_handler(self) -> None:
        """启用保存请求处理器

        启用后，Coordinator 将订阅 SaveRequest 事件并管理请求队列。
        """
        from src.domain.services.save_request_channel import SaveRequest

        self._save_request_handler_enabled = True

        # 订阅 SaveRequest 事件（使用类型）
        if self.event_bus and not self._is_listening_save_requests:
            self.event_bus.subscribe(SaveRequest, self._handle_save_request)
            self._is_listening_save_requests = True

    def disable_save_request_handler(self) -> None:
        """禁用保存请求处理器"""
        self._save_request_handler_enabled = False
        if self.event_bus and self._is_listening_save_requests:
            from src.domain.services.save_request_channel import SaveRequest

            self.event_bus.unsubscribe(SaveRequest, self._handle_save_request)
            self._is_listening_save_requests = False

    async def _handle_save_request(self, event: Any) -> None:
        """处理 SaveRequest 事件

        参数：
            event: SaveRequest 事件
        """
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestReceivedEvent,
        )

        if not isinstance(event, SaveRequest):
            return

        # 入队
        queue_position = self._save_request_queue.enqueue(event)

        # 发布接收确认事件
        if self.event_bus:
            received_event = SaveRequestReceivedEvent(
                request_id=event.request_id,
                queue_position=queue_position,
            )
            await self.event_bus.publish(received_event)

    # ==================== 队列查询 ====================

    def has_pending_save_requests(self) -> bool:
        """检查是否有待处理的保存请求

        返回：
            True 如果有待处理请求
        """
        return not self._save_request_queue.is_empty()

    def get_pending_save_request_count(self) -> int:
        """获取待处理保存请求数量

        返回：
            待处理请求数量
        """
        return self._save_request_queue.queue_size()

    def get_save_request_queue(self) -> list[Any]:
        """获取保存请求队列（按优先级排序）

        返回：
            排序后的 SaveRequest 列表
        """
        return self._save_request_queue.get_all_sorted()

    def get_save_request_status(self, request_id: str) -> Any:
        """获取保存请求状态

        参数：
            request_id: 请求 ID

        返回：
            SaveRequestStatus 或 None
        """
        from src.domain.services.save_request_channel import SaveRequestStatus

        status = self._save_request_queue.get_status(request_id)
        return status if status else SaveRequestStatus.PENDING

    def get_save_requests_by_session(self, session_id: str) -> list[Any]:
        """获取特定会话的保存请求

        参数：
            session_id: 会话 ID

        返回：
            该会话的 SaveRequest 列表
        """
        return self._save_request_queue.get_by_session(session_id)

    def dequeue_save_request(self) -> Any | None:
        """从队列中取出最高优先级的保存请求

        返回：
            SaveRequest 或 None
        """
        return self._save_request_queue.dequeue()

    # ==================== 审核与执行配置 ====================

    def configure_save_auditor(
        self,
        path_whitelist: list[str] | None = None,
        path_blacklist: list[str] | None = None,
        max_content_size: int = 10 * 1024 * 1024,
        enable_rate_limit: bool = True,
        enable_sensitive_check: bool = True,
    ) -> None:
        """配置保存请求审核器

        参数：
            path_whitelist: 路径白名单（如果提供，只允许这些路径）
            path_blacklist: 路径黑名单
            max_content_size: 最大内容大小（字节）
            enable_rate_limit: 是否启用频率限制
            enable_sensitive_check: 是否启用敏感内容检查
        """
        from src.domain.services.save_request_audit import (
            AuditLogger,
            ContentSizeRule,
            PathBlacklistRule,
            PathWhitelistRule,
            RateLimitRule,
            SaveExecutor,
            SaveRequestAuditor,
            SensitiveContentRule,
        )

        rules = []

        # 路径黑名单规则（优先）
        if path_blacklist:
            rules.append(PathBlacklistRule(blacklist=path_blacklist))

        # 路径白名单规则
        if path_whitelist:
            rules.append(PathWhitelistRule(whitelist=path_whitelist))

        # 内容大小规则
        rules.append(ContentSizeRule(max_size_bytes=max_content_size))

        # 频率限制规则
        if enable_rate_limit:
            rules.append(RateLimitRule())

        # 敏感内容检查规则
        if enable_sensitive_check:
            rules.append(SensitiveContentRule())

        self._save_auditor = SaveRequestAuditor(rules=rules)
        self._save_executor = SaveExecutor()
        self._save_audit_logger = AuditLogger()

    # ==================== 审核与执行 ====================

    async def process_next_save_request(self) -> Any | None:
        """处理下一个保存请求

        流程：
        1. 从队列取出请求
        2. 执行审核
        3. 如果通过，执行写操作
        4. 记录审计日志
        5. 发布完成事件

        返回：
            ProcessResult 或 None（队列为空时）
        """
        from src.domain.services.save_request_audit import (
            AuditStatus,
            ProcessResult,
            SaveRequestCompletedEvent,
        )
        from src.domain.services.save_request_channel import SaveRequestStatus

        # 确保审核器已初始化
        if not hasattr(self, "_save_auditor") or self._save_auditor is None:
            self.configure_save_auditor()

        # 从队列取出请求
        request = self.dequeue_save_request()
        if request is None:
            return None

        request_id = request.request_id

        # 执行审核（断言已初始化，供类型检查器使用）
        assert self._save_auditor is not None
        assert self._save_audit_logger is not None
        assert self._save_executor is not None

        audit_result = self._save_auditor.audit(request)
        self._save_audit_logger.log_audit(request, audit_result)

        # 如果审核未通过
        if audit_result.status != AuditStatus.APPROVED:
            result = ProcessResult(
                request_id=request_id,
                success=False,
                audit_status=audit_result.status,
                error_message=audit_result.reason,
            )
            self._save_request_queue.update_status(request_id, SaveRequestStatus.REJECTED)

            # 发布完成事件
            if self.event_bus:
                await self.event_bus.publish(
                    SaveRequestCompletedEvent(
                        request_id=request_id,
                        success=False,
                        audit_status=audit_result.status.value,
                        error_message=audit_result.reason,
                    )
                )

            return result

        # 执行写操作
        exec_result = self._save_executor.execute(request)
        self._save_audit_logger.log_execution(exec_result)

        result = ProcessResult(
            request_id=request_id,
            success=exec_result.success,
            audit_status=AuditStatus.APPROVED,
            error_message=exec_result.error_message,
            bytes_written=exec_result.bytes_written,
        )
        final_status = (
            SaveRequestStatus.COMPLETED if exec_result.success else SaveRequestStatus.FAILED
        )
        self._save_request_queue.update_status(request_id, final_status)

        # 发布完成事件
        if self.event_bus:
            await self.event_bus.publish(
                SaveRequestCompletedEvent(
                    request_id=request_id,
                    success=exec_result.success,
                    audit_status=AuditStatus.APPROVED.value,
                    error_message=exec_result.error_message,
                    bytes_written=exec_result.bytes_written,
                )
            )

        return result

    def get_save_audit_logs(self) -> list[dict]:
        """获取保存审计日志

        返回：
            审计日志列表
        """
        if not hasattr(self, "_save_audit_logger") or self._save_audit_logger is None:
            return []
        return self._save_audit_logger.get_logs()

    def get_save_audit_logs_by_session(self, session_id: str) -> list[dict]:
        """获取特定会话的保存审计日志

        参数：
            session_id: 会话 ID

        返回：
            该会话的审计日志列表
        """
        if not hasattr(self, "_save_audit_logger") or self._save_audit_logger is None:
            return []
        return self._save_audit_logger.get_logs_by_session(session_id)

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
        """发送保存结果回执

        当 SaveRequest 执行完成后，调用此方法发送回执给 ConversationAgent。

        参数：
            session_id: 会话 ID
            request_id: 原始请求 ID
            success: 是否成功
            message: 状态消息
            error_code: 错误代码（如有）
            error_message: 错误信息（如有）
            violation_severity: 违规严重级别（如有）
            audit_trail: 审计追踪信息

        返回：
            处理结果字典
        """
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveRequestResultEvent,
            SaveResultStatus,
        )

        # 确定状态
        if success:
            status = SaveResultStatus.SUCCESS
        elif violation_severity:
            status = SaveResultStatus.REJECTED
        else:
            status = SaveResultStatus.FAILED

        # 记录请求接收日志
        self.save_receipt_system.receipt_logger.log_request_received(
            request_id=request_id,
            session_id=session_id,
            target_path="",  # 可从 audit_trail 中提取
        )

        # 创建回执
        result = SaveRequestResult(
            request_id=request_id,
            status=status,
            message=message,
            error_code=error_code,
            error_message=error_message,
            violation_severity=violation_severity,
            audit_trail=audit_trail or [],
        )

        # 记录审核日志
        self.save_receipt_system.receipt_logger.log_audit_completed(
            request_id=request_id,
            approved=success,
            rules_checked=[t.get("rule_id", "") for t in (audit_trail or []) if "rule_id" in t],
        )

        # 处理结果（记忆更新、知识库写入）
        processing_result = self.save_receipt_system.process_result(session_id, result)

        # 发布结果事件
        if self.event_bus:
            event = SaveRequestResultEvent(
                result=result,
                session_id=session_id,
                source="save_request_orchestrator",
            )
            await self.event_bus.publish(event)

        logger.info(
            "[RECEIPT SENT] request_id=%s session_id=%s status=%s written_to_kb=%s",
            request_id,
            session_id,
            status.value,
            processing_result["written_to_knowledge_base"],
        )

        return processing_result

    async def process_save_request_with_receipt(self) -> dict[str, Any] | None:
        """处理保存请求并发送回执

        完整流程：
        1. 从队列取出请求
        2. 执行审核
        3. 如果通过，执行写操作
        4. 发送结果回执
        5. 更新 ConversationAgent 记忆

        返回：
            处理结果或 None（队列为空时）
        """
        from src.domain.services.save_request_audit import AuditStatus
        from src.domain.services.save_request_channel import SaveRequestStatus

        # 确保审核器已初始化
        if not hasattr(self, "_save_auditor") or self._save_auditor is None:
            self.configure_save_auditor()

        # 从队列取出请求
        request = self.dequeue_save_request()
        if request is None:
            return None

        request_id = request.request_id
        session_id = request.session_id

        # 执行审核（断言已初始化，供类型检查器使用）
        assert self._save_auditor is not None
        assert self._save_audit_logger is not None
        assert self._save_executor is not None

        audit_result = self._save_auditor.audit(request)
        self._save_audit_logger.log_audit(request, audit_result)

        # 构建审计追踪
        audit_trail = [
            {
                "step": "received",
                "timestamp": request.timestamp.isoformat(),
            },
            {
                "step": "audited",
                "status": audit_result.status.value,
                "reason": audit_result.reason,
                "rule_id": audit_result.rule_id,
            },
        ]

        # 如果审核未通过
        if audit_result.status != AuditStatus.APPROVED:
            # 确定违规严重级别
            violation_severity = "low"
            if "dangerous" in (audit_result.reason or "").lower():
                violation_severity = "critical"
            elif "sensitive" in (audit_result.reason or "").lower():
                violation_severity = "high"

            self._save_request_queue.update_status(request_id, SaveRequestStatus.REJECTED)
            return await self.send_save_result_receipt(
                session_id=session_id,
                request_id=request_id,
                success=False,
                message=f"审核未通过: {audit_result.reason}",
                error_code=f"AUDIT_{audit_result.status.value.upper()}",
                error_message=audit_result.reason,
                violation_severity=violation_severity,
                audit_trail=audit_trail,
            )

        # 执行写操作
        exec_result = self._save_executor.execute(request)
        self._save_audit_logger.log_execution(exec_result)

        audit_trail.append(
            {
                "step": "executed",
                "success": exec_result.success,
                "bytes_written": exec_result.bytes_written,
            }
        )

        final_status = (
            SaveRequestStatus.COMPLETED if exec_result.success else SaveRequestStatus.FAILED
        )
        self._save_request_queue.update_status(request_id, final_status)

        return await self.send_save_result_receipt(
            session_id=session_id,
            request_id=request_id,
            success=exec_result.success,
            message="保存成功" if exec_result.success else f"执行失败: {exec_result.error_message}",
            error_code="IO_ERROR" if not exec_result.success else None,
            error_message=exec_result.error_message,
            audit_trail=audit_trail,
        )

    # ==================== 回执查询 ====================

    def get_save_receipt_context(self, session_id: str) -> dict[str, Any]:
        """获取保存回执上下文

        为 ConversationAgent 生成保存结果相关的上下文。

        参数：
            session_id: 会话 ID

        返回：
            上下文字典
        """
        return self.save_receipt_system.generate_context_for_agent(session_id)

    def get_save_receipt_chain_log(self, request_id: str) -> dict[str, Any] | None:
        """获取保存请求的完整链路日志

        参数：
            request_id: 请求 ID

        返回：
            链路日志或 None
        """
        return self.save_receipt_system.get_receipt_chain_log(request_id)

    def get_save_receipt_logs(self) -> list[dict[str, Any]]:
        """获取所有回执日志"""
        return self.save_receipt_system.receipt_logger.get_all_logs()

    def get_session_save_statistics(self, session_id: str) -> dict[str, Any]:
        """获取会话的保存统计

        参数：
            session_id: 会话 ID

        返回：
            统计信息字典
        """
        return self.save_receipt_system.memory_handler.get_session_statistics(session_id)


__all__ = ["SaveRequestOrchestrator"]
