"""结果回执与记忆更新模块 (Save Request Receipt)

业务定义：
- SaveRequest 执行成功或失败时，Coordinator 返回结果（含状态码、错误信息）
- ConversationAgent 记录在短期/中期记忆以供后续参考
- 严重违规写入长期知识库

设计原则：
- 结构化回执：状态码、错误信息、审计追踪
- 记忆分层：短期（最近几条）、中期（会话级）、长期（知识库）
- 完整链路：SaveRequest → 审核 → 回执

实现日期：2025-12-08
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================


class SaveResultStatus(str, Enum):
    """保存结果状态

    定义保存请求执行后的状态。
    """

    SUCCESS = "success"  # 成功
    REJECTED = "rejected"  # 被拒绝（规则违规）
    FAILED = "failed"  # 执行失败（IO错误等）
    PENDING = "pending"  # 待处理
    CANCELLED = "cancelled"  # 已取消


# =============================================================================
# 数据结构定义
# =============================================================================


@dataclass
class SaveRequestResult:
    """保存请求结果回执

    当 SaveRequest 执行完成后，返回此结果给 ConversationAgent。

    属性：
        request_id: 原始请求 ID
        status: 执行状态
        message: 状态消息
        error_code: 错误代码（如有）
        error_message: 错误信息（如有）
        execution_time: 执行时间（秒）
        violation_severity: 违规严重级别（none/low/medium/high/critical）
        audit_trail: 审计追踪信息
        metadata: 附加元数据
        timestamp: 结果时间戳
    """

    request_id: str
    status: SaveResultStatus
    message: str
    error_code: str | None = None
    error_message: str | None = None
    execution_time: float | None = None
    violation_severity: str | None = None
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def is_success(self) -> bool:
        """是否成功

        返回：
            True 如果状态为 SUCCESS
        """
        return self.status == SaveResultStatus.SUCCESS

    def is_error(self) -> bool:
        """是否为错误

        返回：
            True 如果状态为 FAILED 或 REJECTED
        """
        return self.status in (SaveResultStatus.FAILED, SaveResultStatus.REJECTED)

    def get_severity(self) -> str:
        """获取严重级别

        返回：
            严重级别字符串
        """
        if self.status == SaveResultStatus.SUCCESS:
            return "none"
        return self.violation_severity or "low"

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典

        返回：
            字典表示
        """
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "message": self.message,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "execution_time": self.execution_time,
            "violation_severity": self.violation_severity,
            "audit_trail": self.audit_trail,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SaveRequestResult":
        """从字典反序列化

        参数：
            data: 字典数据

        返回：
            SaveRequestResult 实例
        """
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            request_id=data.get("request_id", ""),
            status=SaveResultStatus(data.get("status", "pending")),
            message=data.get("message", ""),
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
            execution_time=data.get("execution_time"),
            violation_severity=data.get("violation_severity"),
            audit_trail=data.get("audit_trail", []),
            metadata=data.get("metadata", {}),
            timestamp=timestamp or datetime.now(),
        )


@dataclass
class SaveRequestResultEvent(Event):
    """保存请求结果事件

    当保存请求执行完成后发布此事件。
    ConversationAgent 订阅此事件更新记忆。

    属性：
        result: 保存结果
        session_id: 会话 ID
        source: 事件来源
    """

    result: SaveRequestResult = field(
        default_factory=lambda: SaveRequestResult(
            request_id="",
            status=SaveResultStatus.PENDING,
            message="",
        )
    )
    session_id: str = ""

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "save_request_result"


# =============================================================================
# 记忆处理器
# =============================================================================


class SaveResultMemoryHandler:
    """保存结果记忆处理器

    管理保存结果的短期和中期记忆。

    短期记忆：最近几条保存结果，用于即时上下文
    中期记忆：会话内所有保存操作，用于统计和回顾
    """

    def __init__(self, short_term_limit: int = 10):
        """初始化

        参数：
            short_term_limit: 短期记忆容量限制
        """
        self._short_term_limit = short_term_limit
        self._short_term: dict[str, list[dict[str, Any]]] = {}  # session_id -> records
        self._medium_term: dict[str, list[dict[str, Any]]] = {}  # session_id -> records
        self._lock = threading.RLock()

    def record_to_short_term(self, session_id: str, result: SaveRequestResult) -> None:
        """记录到短期记忆

        参数：
            session_id: 会话 ID
            result: 保存结果
        """
        with self._lock:
            if session_id not in self._short_term:
                self._short_term[session_id] = []

            record = {
                "request_id": result.request_id,
                "status": result.status.value,
                "message": result.message,
                "error_code": result.error_code,
                "error_message": result.error_message,
                "timestamp": result.timestamp.isoformat(),
            }

            self._short_term[session_id].append(record)

            # 保持容量限制
            if len(self._short_term[session_id]) > self._short_term_limit:
                self._short_term[session_id] = self._short_term[session_id][
                    -self._short_term_limit :
                ]

    def record_to_medium_term(self, session_id: str, result: SaveRequestResult) -> None:
        """记录到中期记忆

        参数：
            session_id: 会话 ID
            result: 保存结果
        """
        with self._lock:
            if session_id not in self._medium_term:
                self._medium_term[session_id] = []

            record = {
                "request_id": result.request_id,
                "status": result.status.value,
                "message": result.message,
                "error_code": result.error_code,
                "error_message": result.error_message,
                "violation_severity": result.violation_severity,
                "execution_time": result.execution_time,
                "audit_trail": result.audit_trail,
                "timestamp": result.timestamp.isoformat(),
            }

            self._medium_term[session_id].append(record)

    def get_short_term_memory(self, session_id: str) -> list[dict[str, Any]]:
        """获取短期记忆

        参数：
            session_id: 会话 ID

        返回：
            短期记忆记录列表
        """
        with self._lock:
            return self._short_term.get(session_id, []).copy()

    def get_medium_term_memory(self, session_id: str) -> list[dict[str, Any]]:
        """获取中期记忆

        参数：
            session_id: 会话 ID

        返回：
            中期记忆记录列表
        """
        with self._lock:
            return self._medium_term.get(session_id, []).copy()

    def get_session_statistics(self, session_id: str) -> dict[str, Any]:
        """获取会话统计

        参数：
            session_id: 会话 ID

        返回：
            统计信息字典
        """
        with self._lock:
            records = self._medium_term.get(session_id, [])

            if not records:
                return {
                    "total_requests": 0,
                    "success_count": 0,
                    "rejected_count": 0,
                    "failed_count": 0,
                    "success_rate": 0.0,
                }

            total = len(records)
            success_count = sum(1 for r in records if r["status"] == "success")
            rejected_count = sum(1 for r in records if r["status"] == "rejected")
            failed_count = sum(1 for r in records if r["status"] == "failed")

            return {
                "total_requests": total,
                "success_count": success_count,
                "rejected_count": rejected_count,
                "failed_count": failed_count,
                "success_rate": success_count / total if total > 0 else 0.0,
            }

    def generate_context_for_agent(self, session_id: str) -> dict[str, Any]:
        """为 ConversationAgent 生成上下文

        参数：
            session_id: 会话 ID

        返回：
            上下文字典
        """
        return {
            "recent_save_results": self.get_short_term_memory(session_id),
            "save_statistics": self.get_session_statistics(session_id),
        }

    def clear_session(self, session_id: str) -> None:
        """清空会话记忆

        参数：
            session_id: 会话 ID
        """
        with self._lock:
            self._short_term.pop(session_id, None)
            self._medium_term.pop(session_id, None)


# =============================================================================
# 违规知识库写入器
# =============================================================================


class ViolationKnowledgeWriter:
    """违规知识库写入器

    将严重违规记录写入长期知识库。
    """

    # 需要写入知识库的严重级别
    WRITABLE_SEVERITIES = {"high", "critical"}

    def __init__(self, knowledge_manager: Any | None = None):
        """初始化

        参数：
            knowledge_manager: 知识库管理器（可选）
        """
        self._knowledge_manager = knowledge_manager

    def should_write_to_knowledge_base(self, result: SaveRequestResult) -> bool:
        """判断是否应写入知识库

        参数：
            result: 保存结果

        返回：
            True 如果应写入
        """
        if result.is_success():
            return False

        severity = result.get_severity()
        return severity in self.WRITABLE_SEVERITIES

    def write_violation(
        self,
        session_id: str,
        result: SaveRequestResult,
    ) -> str | None:
        """写入违规记录

        参数：
            session_id: 会话 ID
            result: 保存结果

        返回：
            知识条目 ID 或 None
        """
        if not self._knowledge_manager:
            logger.warning("Knowledge manager not configured, skipping violation write")
            return None

        if not self.should_write_to_knowledge_base(result):
            return None

        # 构建知识条目
        title = f"Violation: {result.error_code or 'UNKNOWN'}"
        content = self._build_violation_content(session_id, result)

        entry_id = self._knowledge_manager.create(
            title=title,
            content=content,
            category="security_violation",
            tags=[
                "violation",
                result.error_code or "unknown",
                result.get_severity(),
                session_id,
            ],
            metadata={
                "request_id": result.request_id,
                "session_id": session_id,
                "status": result.status.value,
                "severity": result.get_severity(),
                "error_code": result.error_code,
                "audit_trail": result.audit_trail,
                "timestamp": result.timestamp.isoformat(),
            },
        )

        logger.info(
            f"[VIOLATION WRITTEN] entry_id={entry_id} "
            f"request_id={result.request_id} "
            f"severity={result.get_severity()}"
        )

        return entry_id

    def batch_write_violations(
        self,
        session_id: str,
        results: list[SaveRequestResult],
    ) -> list[str]:
        """批量写入违规记录

        参数：
            session_id: 会话 ID
            results: 保存结果列表

        返回：
            知识条目 ID 列表
        """
        entry_ids = []
        for result in results:
            if self.should_write_to_knowledge_base(result):
                entry_id = self.write_violation(session_id, result)
                if entry_id:
                    entry_ids.append(entry_id)
        return entry_ids

    def _build_violation_content(
        self,
        session_id: str,
        result: SaveRequestResult,
    ) -> str:
        """构建违规内容

        参数：
            session_id: 会话 ID
            result: 保存结果

        返回：
            格式化的违规内容
        """
        lines = [
            f"# Violation Report",
            f"",
            f"**Request ID:** {result.request_id}",
            f"**Session ID:** {session_id}",
            f"**Status:** {result.status.value}",
            f"**Severity:** {result.get_severity()}",
            f"**Error Code:** {result.error_code or 'N/A'}",
            f"**Error Message:** {result.error_message or 'N/A'}",
            f"**Timestamp:** {result.timestamp.isoformat()}",
            f"",
            f"## Audit Trail",
        ]

        for i, trail in enumerate(result.audit_trail, 1):
            lines.append(f"{i}. {trail}")

        return "\n".join(lines)


# =============================================================================
# 日志记录器
# =============================================================================


class ReceiptLogger:
    """回执日志记录器

    记录 SaveRequest → 审核 → 回执 的完整链路。
    """

    def __init__(self):
        """初始化"""
        self._logs: dict[str, list[dict[str, Any]]] = {}  # request_id -> events
        self._lock = threading.RLock()

    def log_request_received(
        self,
        request_id: str,
        session_id: str,
        target_path: str,
    ) -> dict[str, Any]:
        """记录请求接收

        参数：
            request_id: 请求 ID
            session_id: 会话 ID
            target_path: 目标路径

        返回：
            日志条目
        """
        entry = {
            "event": "request_received",
            "request_id": request_id,
            "session_id": session_id,
            "target_path": target_path,
            "timestamp": datetime.now().isoformat(),
        }

        self._add_log(request_id, entry)

        logger.info(
            f"[RECEIPT] request_received "
            f"request_id={request_id} "
            f"session_id={session_id} "
            f"target_path={target_path}"
        )

        return entry

    def log_audit_completed(
        self,
        request_id: str,
        approved: bool,
        rules_checked: list[str] | None = None,
    ) -> dict[str, Any]:
        """记录审核完成

        参数：
            request_id: 请求 ID
            approved: 是否批准
            rules_checked: 检查的规则列表

        返回：
            日志条目
        """
        entry = {
            "event": "audit_completed",
            "request_id": request_id,
            "approved": approved,
            "rules_checked": rules_checked or [],
            "timestamp": datetime.now().isoformat(),
        }

        self._add_log(request_id, entry)

        logger.info(
            f"[RECEIPT] audit_completed "
            f"request_id={request_id} "
            f"approved={approved} "
            f"rules_checked={rules_checked}"
        )

        return entry

    def log_receipt_sent(
        self,
        request_id: str,
        status: str,
        message: str,
    ) -> dict[str, Any]:
        """记录回执发送

        参数：
            request_id: 请求 ID
            status: 状态
            message: 消息

        返回：
            日志条目
        """
        entry = {
            "event": "receipt_sent",
            "request_id": request_id,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }

        self._add_log(request_id, entry)

        logger.info(
            f"[RECEIPT] receipt_sent "
            f"request_id={request_id} "
            f"status={status} "
            f"message={message}"
        )

        return entry

    def get_chain_log(self, request_id: str) -> list[dict[str, Any]]:
        """获取请求的完整链路日志

        参数：
            request_id: 请求 ID

        返回：
            链路日志列表
        """
        with self._lock:
            return self._logs.get(request_id, []).copy()

    def get_all_logs(self) -> list[dict[str, Any]]:
        """获取所有日志

        返回：
            所有日志条目列表
        """
        with self._lock:
            all_logs = []
            for logs in self._logs.values():
                all_logs.extend(logs)
            return all_logs

    def _add_log(self, request_id: str, entry: dict[str, Any]) -> None:
        """添加日志

        参数：
            request_id: 请求 ID
            entry: 日志条目
        """
        with self._lock:
            if request_id not in self._logs:
                self._logs[request_id] = []
            self._logs[request_id].append(entry)


# =============================================================================
# 结果回执系统
# =============================================================================


class SaveResultReceiptSystem:
    """保存结果回执系统

    集成记忆处理和知识库写入的完整系统。
    """

    def __init__(
        self,
        knowledge_manager: Any | None = None,
        short_term_limit: int = 10,
    ):
        """初始化

        参数：
            knowledge_manager: 知识库管理器
            short_term_limit: 短期记忆容量
        """
        self._memory_handler = SaveResultMemoryHandler(short_term_limit=short_term_limit)
        self._violation_writer = ViolationKnowledgeWriter(knowledge_manager=knowledge_manager)
        self._logger = ReceiptLogger()
        self._processed_results: dict[str, dict[str, Any]] = {}

    @property
    def memory_handler(self) -> SaveResultMemoryHandler:
        """获取记忆处理器"""
        return self._memory_handler

    @property
    def violation_writer(self) -> ViolationKnowledgeWriter:
        """获取违规写入器"""
        return self._violation_writer

    @property
    def receipt_logger(self) -> ReceiptLogger:
        """获取回执日志记录器"""
        return self._logger

    def process_result(
        self,
        session_id: str,
        result: SaveRequestResult,
    ) -> dict[str, Any]:
        """处理保存结果

        完整流程：
        1. 记录到短期记忆
        2. 记录到中期记忆
        3. 严重违规写入知识库
        4. 记录回执日志

        参数：
            session_id: 会话 ID
            result: 保存结果

        返回：
            处理结果字典
        """
        processing_result = {
            "request_id": result.request_id,
            "recorded_to_short_term": False,
            "recorded_to_medium_term": False,
            "written_to_knowledge_base": False,
            "knowledge_entry_id": None,
        }

        # 1. 记录到短期记忆
        try:
            self._memory_handler.record_to_short_term(session_id, result)
            processing_result["recorded_to_short_term"] = True
        except Exception as e:
            logger.error(f"Failed to record to short-term memory: {e}")

        # 2. 记录到中期记忆
        try:
            self._memory_handler.record_to_medium_term(session_id, result)
            processing_result["recorded_to_medium_term"] = True
        except Exception as e:
            logger.error(f"Failed to record to medium-term memory: {e}")

        # 3. 严重违规写入知识库
        if self._violation_writer.should_write_to_knowledge_base(result):
            try:
                entry_id = self._violation_writer.write_violation(session_id, result)
                if entry_id:
                    processing_result["written_to_knowledge_base"] = True
                    processing_result["knowledge_entry_id"] = entry_id
            except Exception as e:
                logger.error(f"Failed to write violation to knowledge base: {e}")

        # 4. 记录回执日志
        self._logger.log_receipt_sent(
            request_id=result.request_id,
            status=result.status.value,
            message=result.message,
        )

        # 保存处理结果
        self._processed_results[result.request_id] = {
            "processing_result": processing_result,
            "result": result.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"[RECEIPT SYSTEM] Processed result "
            f"request_id={result.request_id} "
            f"status={result.status.value} "
            f"written_to_kb={processing_result['written_to_knowledge_base']}"
        )

        return processing_result

    def get_receipt_chain_log(self, request_id: str) -> dict[str, Any] | None:
        """获取回执链路日志

        参数：
            request_id: 请求 ID

        返回：
            链路日志或 None
        """
        processed = self._processed_results.get(request_id)
        if not processed:
            return None

        return {
            "request_id": request_id,
            "audit_trail": processed["result"].get("audit_trail", []),
            "receipt_timestamp": processed["timestamp"],
            "chain_log": self._logger.get_chain_log(request_id),
        }

    def generate_context_for_agent(self, session_id: str) -> dict[str, Any]:
        """为 ConversationAgent 生成上下文

        参数：
            session_id: 会话 ID

        返回：
            上下文字典
        """
        return self._memory_handler.generate_context_for_agent(session_id)


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "SaveResultStatus",
    "SaveRequestResult",
    "SaveRequestResultEvent",
    "SaveResultMemoryHandler",
    "ViolationKnowledgeWriter",
    "ReceiptLogger",
    "SaveResultReceiptSystem",
]
