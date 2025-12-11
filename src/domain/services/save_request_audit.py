"""保存请求审核与执行模块 (Save Request Audit & Execution)

业务定义：
- 为 CoordinatorAgent 提供保存请求的审核和执行能力
- 基于可配置规则集评估 SaveRequest
- 审核通过后执行实际的文件操作
- 记录完整的审计日志

设计原则：
- 规则引擎：可扩展的审核规则系统
- 安全第一：路径白名单/黑名单、内容检查
- 完整审计：所有决策和执行都有日志

实现日期：2025-12-07
"""

import logging
import os
import re
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================


class AuditStatus(str, Enum):
    """审核状态枚举"""

    APPROVED = "approved"  # 审核通过
    REJECTED = "rejected"  # 审核拒绝
    PENDING_REVIEW = "pending_review"  # 待人工审核


class RejectionReason(str, Enum):
    """拒绝原因枚举"""

    PATH_BLACKLISTED = "path_blacklisted"  # 路径在黑名单中
    PATH_NOT_WHITELISTED = "path_not_whitelisted"  # 路径不在白名单中
    CONTENT_TOO_LARGE = "content_too_large"  # 内容过大
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"  # 超过频率限制
    SENSITIVE_CONTENT = "sensitive_content"  # 包含敏感内容
    INVALID_OPERATION = "invalid_operation"  # 无效操作


# =============================================================================
# 数据结构定义
# =============================================================================


@dataclass
class AuditRuleResult:
    """单个审核规则的评估结果"""

    passed: bool
    rule_id: str
    reason: str = ""


@dataclass
class AuditResult:
    """完整审核结果

    属性：
        request_id: 请求 ID
        status: 审核状态
        rule_id: 触发拒绝的规则 ID（如有）
        reason: 原因说明
        timestamp: 审核时间戳
    """

    request_id: str
    status: AuditStatus
    rule_id: str | None = None
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExecutionResult:
    """执行结果

    属性：
        request_id: 请求 ID
        success: 是否成功
        error_message: 错误信息（如有）
        bytes_written: 写入字节数
        execution_time_ms: 执行时间（毫秒）
    """

    request_id: str
    success: bool
    error_message: str | None = None
    bytes_written: int = 0
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "request_id": self.request_id,
            "success": self.success,
            "error_message": self.error_message,
            "bytes_written": self.bytes_written,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class ProcessResult:
    """处理结果（审核+执行）

    属性：
        request_id: 请求 ID
        success: 是否成功
        audit_status: 审核状态
        error_message: 错误信息
        bytes_written: 写入字节数
    """

    request_id: str
    success: bool
    audit_status: AuditStatus
    error_message: str | None = None
    bytes_written: int = 0


# =============================================================================
# 事件定义
# =============================================================================


@dataclass
class SaveRequestCompletedEvent(Event):
    """保存请求完成事件"""

    request_id: str = ""
    success: bool = False
    audit_status: str = ""
    error_message: str | None = None
    bytes_written: int = 0

    @property
    def event_type(self) -> str:
        return "save_request_completed"


# =============================================================================
# 审核规则基类
# =============================================================================


class AuditRule(ABC):
    """审核规则抽象基类"""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """规则唯一标识"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """规则名称"""
        pass

    @abstractmethod
    def evaluate(self, request: Any) -> AuditRuleResult:
        """评估请求

        参数：
            request: SaveRequest 实例

        返回：
            AuditRuleResult 评估结果
        """
        pass


# =============================================================================
# 内置审核规则
# =============================================================================


class PathBlacklistRule(AuditRule):
    """路径黑名单规则

    拒绝目标路径在黑名单中的请求。
    """

    def __init__(self, blacklist: list[str] | None = None):
        """初始化

        参数：
            blacklist: 黑名单路径列表（支持路径前缀匹配）
        """
        self._blacklist = blacklist or [
            "/etc",
            "/sys",
            "/proc",
            "/root",
            "/boot",
            "/dev",
        ]

    @property
    def rule_id(self) -> str:
        return "path_blacklist"

    @property
    def name(self) -> str:
        return "Path Blacklist Rule"

    def evaluate(self, request: Any) -> AuditRuleResult:
        """评估路径是否在黑名单中"""
        target_path = request.target_path

        for blacklisted in self._blacklist:
            if target_path.startswith(blacklisted):
                return AuditRuleResult(
                    passed=False,
                    rule_id=self.rule_id,
                    reason=f"Path '{target_path}' is in blacklist (matches '{blacklisted}')",
                )

        return AuditRuleResult(passed=True, rule_id=self.rule_id)


class PathWhitelistRule(AuditRule):
    """路径白名单规则

    只允许目标路径在白名单中的请求。
    """

    def __init__(self, whitelist: list[str] | None = None):
        """初始化

        参数：
            whitelist: 白名单路径列表（支持路径前缀匹配）
        """
        self._whitelist = whitelist or ["/tmp"]

    @property
    def rule_id(self) -> str:
        return "path_whitelist"

    @property
    def name(self) -> str:
        return "Path Whitelist Rule"

    def evaluate(self, request: Any) -> AuditRuleResult:
        """评估路径是否在白名单中"""
        target_path = request.target_path

        for whitelisted in self._whitelist:
            if target_path.startswith(whitelisted):
                return AuditRuleResult(passed=True, rule_id=self.rule_id)

        return AuditRuleResult(
            passed=False,
            rule_id=self.rule_id,
            reason=f"Path '{target_path}' is not in whitelist",
        )


class ContentSizeRule(AuditRule):
    """内容大小限制规则

    拒绝内容超过大小限制的请求。
    """

    def __init__(self, max_size_bytes: int = 10 * 1024 * 1024):
        """初始化

        参数：
            max_size_bytes: 最大内容大小（字节），默认 10MB
        """
        self._max_size = max_size_bytes

    @property
    def rule_id(self) -> str:
        return "content_size"

    @property
    def name(self) -> str:
        return "Content Size Rule"

    def evaluate(self, request: Any) -> AuditRuleResult:
        """评估内容大小是否在限制内"""
        content = request.content

        if isinstance(content, str):
            size = len(content.encode("utf-8"))
        else:
            size = len(content)

        if size > self._max_size:
            return AuditRuleResult(
                passed=False,
                rule_id=self.rule_id,
                reason=f"Content size ({size} bytes) exceeds limit ({self._max_size} bytes)",
            )

        return AuditRuleResult(passed=True, rule_id=self.rule_id)


class RateLimitRule(AuditRule):
    """频率限制规则

    限制每分钟和每会话的请求数量。
    """

    def __init__(
        self,
        max_requests_per_minute: int = 60,
        max_requests_per_session: int = 1000,
    ):
        """初始化

        参数：
            max_requests_per_minute: 每分钟最大请求数
            max_requests_per_session: 每会话最大请求数
        """
        self._max_per_minute = max_requests_per_minute
        self._max_per_session = max_requests_per_session
        self._minute_counts: dict[str, list[float]] = defaultdict(list)
        self._session_counts: dict[str, int] = defaultdict(int)

    @property
    def rule_id(self) -> str:
        return "rate_limit"

    @property
    def name(self) -> str:
        return "Rate Limit Rule"

    def evaluate(self, request: Any) -> AuditRuleResult:
        """评估是否超过频率限制"""
        session_id = request.session_id
        current_time = time.time()

        # 检查会话限制
        self._session_counts[session_id] += 1
        if self._session_counts[session_id] > self._max_per_session:
            return AuditRuleResult(
                passed=False,
                rule_id=self.rule_id,
                reason=f"Session rate limit exceeded ({self._max_per_session} requests per session)",
            )

        # 检查每分钟限制
        minute_key = f"{session_id}:{int(current_time // 60)}"
        self._minute_counts[minute_key].append(current_time)

        # 清理过期记录
        one_minute_ago = current_time - 60
        self._minute_counts[minute_key] = [
            t for t in self._minute_counts[minute_key] if t > one_minute_ago
        ]

        if len(self._minute_counts[minute_key]) > self._max_per_minute:
            return AuditRuleResult(
                passed=False,
                rule_id=self.rule_id,
                reason=f"Rate limit exceeded ({self._max_per_minute} requests per minute)",
            )

        return AuditRuleResult(passed=True, rule_id=self.rule_id)

    def reset(self) -> None:
        """重置计数器"""
        self._minute_counts.clear()
        self._session_counts.clear()


class SensitiveContentRule(AuditRule):
    """敏感内容检查规则

    检测内容中是否包含敏感信息（密钥、密码等）。
    """

    # 敏感模式列表
    SENSITIVE_PATTERNS = [
        r"api[_-]?key\s*[=:]\s*['\"]?[\w-]+",
        r"secret[_-]?key\s*[=:]\s*['\"]?[\w-]+",
        r"password\s*[=:]\s*['\"]?[^\s'\"]+",
        r"passwd\s*[=:]\s*['\"]?[^\s'\"]+",
        r"private[_-]?key",
        r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
        r"aws[_-]?access[_-]?key",
        r"aws[_-]?secret",
        r"bearer\s+[\w-]+\.[\w-]+\.[\w-]+",
        r"sk-[a-zA-Z0-9]{20,}",
    ]

    def __init__(self, additional_patterns: list[str] | None = None):
        """初始化

        参数：
            additional_patterns: 额外的敏感模式正则表达式
        """
        patterns = self.SENSITIVE_PATTERNS.copy()
        if additional_patterns:
            patterns.extend(additional_patterns)

        self._patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

    @property
    def rule_id(self) -> str:
        return "sensitive_content"

    @property
    def name(self) -> str:
        return "Sensitive Content Rule"

    def evaluate(self, request: Any) -> AuditRuleResult:
        """评估内容是否包含敏感信息"""
        content = request.content

        if isinstance(content, bytes):
            try:
                content = content.decode("utf-8", errors="ignore")
            except Exception:
                return AuditRuleResult(passed=True, rule_id=self.rule_id)

        for pattern in self._patterns:
            if pattern.search(content):
                return AuditRuleResult(
                    passed=False,
                    rule_id=self.rule_id,
                    reason="Content contains sensitive information (e.g., API keys, passwords)",
                )

        return AuditRuleResult(passed=True, rule_id=self.rule_id)


# =============================================================================
# 审核引擎
# =============================================================================


class SaveRequestAuditor:
    """保存请求审核器

    按顺序运行所有审核规则，任一规则失败则拒绝请求。
    """

    def __init__(self, rules: list[AuditRule] | None = None):
        """初始化

        参数：
            rules: 审核规则列表
        """
        self._rules: list[AuditRule] = rules or []

    @property
    def rules(self) -> list[AuditRule]:
        """获取规则列表"""
        return self._rules

    def add_rule(self, rule: AuditRule) -> None:
        """添加规则"""
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则

        参数：
            rule_id: 规则 ID

        返回：
            是否成功移除
        """
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def audit(self, request: Any) -> AuditResult:
        """执行审核

        参数：
            request: SaveRequest 实例

        返回：
            AuditResult 审核结果
        """
        request_id = getattr(request, "request_id", "unknown")

        # 无规则时默认通过
        if not self._rules:
            logger.debug(f"No audit rules configured, approving request {request_id}")
            return AuditResult(
                request_id=request_id,
                status=AuditStatus.APPROVED,
                reason="No audit rules configured",
            )

        # 按顺序运行规则
        for rule in self._rules:
            try:
                result = rule.evaluate(request)

                if not result.passed:
                    logger.info(
                        f"Request {request_id} rejected by rule '{rule.rule_id}': {result.reason}"
                    )
                    return AuditResult(
                        request_id=request_id,
                        status=AuditStatus.REJECTED,
                        rule_id=result.rule_id,
                        reason=result.reason,
                    )

            except Exception as e:
                logger.error(f"Rule '{rule.rule_id}' failed with error: {e}")
                # 规则执行失败时拒绝请求（安全优先）
                return AuditResult(
                    request_id=request_id,
                    status=AuditStatus.REJECTED,
                    rule_id=rule.rule_id,
                    reason=f"Rule evaluation failed: {e}",
                )

        # 所有规则通过
        logger.info(f"Request {request_id} approved (passed {len(self._rules)} rules)")
        return AuditResult(
            request_id=request_id,
            status=AuditStatus.APPROVED,
            reason=f"All {len(self._rules)} rules passed",
        )


# =============================================================================
# 保存执行器
# =============================================================================


class SaveExecutor:
    """保存执行器

    执行实际的文件操作。
    """

    def execute(self, request: Any) -> ExecutionResult:
        """执行保存操作

        参数：
            request: SaveRequest 实例

        返回：
            ExecutionResult 执行结果
        """
        from src.domain.services.save_request_channel import SaveRequestType

        request_id = getattr(request, "request_id", "unknown")
        start_time = time.time()

        try:
            operation_type = request.operation_type
            target_path = request.target_path
            content = request.content
            is_binary = getattr(request, "is_binary", False)

            if operation_type == SaveRequestType.FILE_WRITE:
                bytes_written = self._write_file(target_path, content, is_binary)

            elif operation_type == SaveRequestType.FILE_APPEND:
                bytes_written = self._append_file(target_path, content, is_binary)

            elif operation_type == SaveRequestType.FILE_DELETE:
                bytes_written = self._delete_file(target_path)

            elif operation_type == SaveRequestType.CONFIG_UPDATE:
                bytes_written = self._write_file(target_path, content, is_binary)

            else:
                raise ValueError(f"Unknown operation type: {operation_type}")

            execution_time = (time.time() - start_time) * 1000

            logger.info(
                f"Executed {operation_type.value} for request {request_id}: "
                f"{bytes_written} bytes in {execution_time:.2f}ms"
            )

            return ExecutionResult(
                request_id=request_id,
                success=True,
                bytes_written=bytes_written,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_message = str(e)

            logger.error(f"Execution failed for request {request_id}: {error_message}")

            return ExecutionResult(
                request_id=request_id,
                success=False,
                error_message=error_message,
                bytes_written=0,
                execution_time_ms=execution_time,
            )

    def _write_file(self, path: str, content: str | bytes, is_binary: bool) -> int:
        """写入文件"""
        # 创建父目录
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        mode = "wb" if is_binary else "w"
        encoding = None if is_binary else "utf-8"

        with open(path, mode, encoding=encoding) as f:
            if is_binary and isinstance(content, str):
                content = content.encode("utf-8")
            elif not is_binary and isinstance(content, bytes):
                content = content.decode("utf-8")

            f.write(content)

            if isinstance(content, str):
                return len(content.encode("utf-8"))
            return len(content)

    def _append_file(self, path: str, content: str | bytes, is_binary: bool) -> int:
        """追加文件"""
        mode = "ab" if is_binary else "a"
        encoding = None if is_binary else "utf-8"

        with open(path, mode, encoding=encoding) as f:
            if is_binary and isinstance(content, str):
                content = content.encode("utf-8")
            elif not is_binary and isinstance(content, bytes):
                content = content.decode("utf-8")

            f.write(content)

            if isinstance(content, str):
                return len(content.encode("utf-8"))
            return len(content)

    def _delete_file(self, path: str) -> int:
        """删除文件"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")

        os.remove(path)
        return 0


# =============================================================================
# 审计日志
# =============================================================================


class AuditLogger:
    """审计日志记录器

    记录所有审核决策和执行结果。
    """

    def __init__(self):
        """初始化"""
        self._logs: list[dict[str, Any]] = []

    def log_audit(self, request: Any, result: AuditResult) -> None:
        """记录审核决策

        参数：
            request: SaveRequest 实例
            result: AuditResult 审核结果
        """
        log_entry = {
            "type": "audit",
            "request_id": result.request_id,
            "status": result.status.value,
            "rule_id": result.rule_id,
            "reason": result.reason,
            "target_path": getattr(request, "target_path", ""),
            "session_id": getattr(request, "session_id", ""),
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        # 同时输出到标准日志
        if result.status == AuditStatus.APPROVED:
            logger.info(
                f"[AUDIT] APPROVED request={result.request_id} "
                f"path={log_entry['target_path']} session={log_entry['session_id']}"
            )
        else:
            logger.warning(
                f"[AUDIT] REJECTED request={result.request_id} "
                f"rule={result.rule_id} reason={result.reason} "
                f"path={log_entry['target_path']} session={log_entry['session_id']}"
            )

    def log_execution(self, result: ExecutionResult) -> None:
        """记录执行结果

        参数：
            result: ExecutionResult 执行结果
        """
        log_entry = {
            "type": "execution",
            "request_id": result.request_id,
            "success": result.success,
            "error_message": result.error_message,
            "bytes_written": result.bytes_written,
            "execution_time_ms": result.execution_time_ms,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        # 同时输出到标准日志
        if result.success:
            logger.info(
                f"[EXEC] SUCCESS request={result.request_id} "
                f"bytes={result.bytes_written} time={result.execution_time_ms:.2f}ms"
            )
        else:
            logger.error(
                f"[EXEC] FAILED request={result.request_id} " f"error={result.error_message}"
            )

    def get_logs(self) -> list[dict[str, Any]]:
        """获取所有日志"""
        return self._logs.copy()

    def get_logs_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """按会话获取日志"""
        return [log for log in self._logs if log.get("session_id") == session_id]

    def get_logs_by_request(self, request_id: str) -> list[dict[str, Any]]:
        """按请求获取日志"""
        return [log for log in self._logs if log.get("request_id") == request_id]

    def clear(self) -> None:
        """清空日志"""
        self._logs.clear()


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "AuditStatus",
    "RejectionReason",
    "AuditRuleResult",
    "AuditResult",
    "ExecutionResult",
    "ProcessResult",
    "SaveRequestCompletedEvent",
    "AuditRule",
    "PathBlacklistRule",
    "PathWhitelistRule",
    "ContentSizeRule",
    "RateLimitRule",
    "SensitiveContentRule",
    "SaveRequestAuditor",
    "SaveExecutor",
    "AuditLogger",
]
