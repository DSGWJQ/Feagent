"""保存请求审核与执行测试 (Save Request Audit & Execution Tests)

TDD 测试用例，验证：
1. 审核规则评估
2. 审核通过场景
3. 审核拒绝场景
4. 执行成功场景
5. 执行失败场景
6. 审计日志记录

测试日期：2025-12-07
"""

import os
import tempfile
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# 测试辅助类
# =============================================================================


class SyncEventBus:
    """同步事件总线（测试用）"""

    def __init__(self):
        self._subscribers: dict[type, list] = {}
        self._event_log: list = []

    def subscribe(self, event_type: type, handler) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        self._event_log.append(event)
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            handler(event)

    @property
    def event_log(self) -> list:
        return self._event_log


def create_test_global_context():
    """创建测试用全局上下文"""
    from src.domain.services.context_manager import GlobalContext
    return GlobalContext(
        user_id="test-user",
        user_preferences={"language": "zh-CN"},
        system_config={"max_tokens": 4096}
    )


def create_test_session_context(session_id: str = "test-session"):
    """创建测试用会话上下文"""
    from src.domain.services.context_manager import SessionContext
    global_context = create_test_global_context()
    return SessionContext(
        session_id=session_id,
        global_context=global_context
    )


# =============================================================================
# 第一部分：审核状态和结果数据结构测试
# =============================================================================


class TestAuditStatusEnum:
    """AuditStatus 枚举测试"""

    def test_approved_status_exists(self):
        """测试：APPROVED 状态存在"""
        from src.domain.services.save_request_audit import AuditStatus

        assert AuditStatus.APPROVED == "approved"

    def test_rejected_status_exists(self):
        """测试：REJECTED 状态存在"""
        from src.domain.services.save_request_audit import AuditStatus

        assert AuditStatus.REJECTED == "rejected"

    def test_pending_review_status_exists(self):
        """测试：PENDING_REVIEW 状态存在"""
        from src.domain.services.save_request_audit import AuditStatus

        assert AuditStatus.PENDING_REVIEW == "pending_review"


class TestRejectionReasonEnum:
    """RejectionReason 枚举测试"""

    def test_path_blacklisted_reason(self):
        """测试：PATH_BLACKLISTED 原因存在"""
        from src.domain.services.save_request_audit import RejectionReason

        assert RejectionReason.PATH_BLACKLISTED == "path_blacklisted"

    def test_content_too_large_reason(self):
        """测试：CONTENT_TOO_LARGE 原因存在"""
        from src.domain.services.save_request_audit import RejectionReason

        assert RejectionReason.CONTENT_TOO_LARGE == "content_too_large"

    def test_rate_limit_exceeded_reason(self):
        """测试：RATE_LIMIT_EXCEEDED 原因存在"""
        from src.domain.services.save_request_audit import RejectionReason

        assert RejectionReason.RATE_LIMIT_EXCEEDED == "rate_limit_exceeded"

    def test_sensitive_content_reason(self):
        """测试：SENSITIVE_CONTENT 原因存在"""
        from src.domain.services.save_request_audit import RejectionReason

        assert RejectionReason.SENSITIVE_CONTENT == "sensitive_content"


class TestAuditResult:
    """AuditResult 数据结构测试"""

    def test_create_approved_result(self):
        """测试：创建审核通过结果"""
        from src.domain.services.save_request_audit import (
            AuditResult,
            AuditStatus,
        )

        result = AuditResult(
            request_id="save-123456",
            status=AuditStatus.APPROVED,
            rule_id=None,
            reason="All rules passed",
        )

        assert result.request_id == "save-123456"
        assert result.status == AuditStatus.APPROVED
        assert result.rule_id is None
        assert result.reason == "All rules passed"
        assert result.timestamp is not None

    def test_create_rejected_result(self):
        """测试：创建审核拒绝结果"""
        from src.domain.services.save_request_audit import (
            AuditResult,
            AuditStatus,
            RejectionReason,
        )

        result = AuditResult(
            request_id="save-123456",
            status=AuditStatus.REJECTED,
            rule_id="path_blacklist_rule",
            reason=RejectionReason.PATH_BLACKLISTED.value,
        )

        assert result.status == AuditStatus.REJECTED
        assert result.rule_id == "path_blacklist_rule"

    def test_audit_result_to_dict(self):
        """测试：AuditResult 序列化为字典"""
        from src.domain.services.save_request_audit import (
            AuditResult,
            AuditStatus,
        )

        result = AuditResult(
            request_id="save-123456",
            status=AuditStatus.APPROVED,
            rule_id=None,
            reason="OK",
        )

        data = result.to_dict()

        assert data["request_id"] == "save-123456"
        assert data["status"] == "approved"
        assert "timestamp" in data


class TestExecutionResult:
    """ExecutionResult 数据结构测试"""

    def test_create_success_result(self):
        """测试：创建执行成功结果"""
        from src.domain.services.save_request_audit import ExecutionResult

        result = ExecutionResult(
            request_id="save-123456",
            success=True,
            error_message=None,
            bytes_written=1024,
            execution_time_ms=15.5,
        )

        assert result.success is True
        assert result.bytes_written == 1024
        assert result.execution_time_ms == 15.5
        assert result.error_message is None

    def test_create_failure_result(self):
        """测试：创建执行失败结果"""
        from src.domain.services.save_request_audit import ExecutionResult

        result = ExecutionResult(
            request_id="save-123456",
            success=False,
            error_message="Permission denied: /etc/passwd",
            bytes_written=0,
            execution_time_ms=2.0,
        )

        assert result.success is False
        assert result.error_message == "Permission denied: /etc/passwd"
        assert result.bytes_written == 0


# =============================================================================
# 第二部分：审核规则测试
# =============================================================================


class TestPathBlacklistRule:
    """路径黑名单规则测试"""

    def test_reject_blacklisted_path(self):
        """测试：拒绝黑名单路径"""
        from src.domain.services.save_request_audit import (
            AuditStatus,
            PathBlacklistRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = PathBlacklistRule(
            blacklist=["/etc", "/sys", "/proc", "/root"]
        )

        request = SaveRequest(
            target_path="/etc/passwd",
            content="malicious",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is False
        assert result.rule_id == "path_blacklist"
        assert "blacklist" in result.reason.lower()

    def test_allow_non_blacklisted_path(self):
        """测试：允许非黑名单路径"""
        from src.domain.services.save_request_audit import (
            PathBlacklistRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = PathBlacklistRule(
            blacklist=["/etc", "/sys"]
        )

        request = SaveRequest(
            target_path="/tmp/output.txt",
            content="safe content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is True


class TestPathWhitelistRule:
    """路径白名单规则测试"""

    def test_allow_whitelisted_path(self):
        """测试：允许白名单路径"""
        from src.domain.services.save_request_audit import (
            PathWhitelistRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = PathWhitelistRule(
            whitelist=["/tmp", "/data/output", "/home/user"]
        )

        request = SaveRequest(
            target_path="/data/output/result.json",
            content="{}",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is True

    def test_reject_non_whitelisted_path(self):
        """测试：拒绝非白名单路径"""
        from src.domain.services.save_request_audit import (
            PathWhitelistRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = PathWhitelistRule(
            whitelist=["/tmp", "/data/output"]
        )

        request = SaveRequest(
            target_path="/var/log/app.log",
            content="log data",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is False
        assert "whitelist" in result.reason.lower()


class TestContentSizeRule:
    """内容大小限制规则测试"""

    def test_allow_content_within_limit(self):
        """测试：允许大小在限制内的内容"""
        from src.domain.services.save_request_audit import (
            ContentSizeRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = ContentSizeRule(max_size_bytes=1024 * 1024)  # 1MB

        request = SaveRequest(
            target_path="/tmp/small.txt",
            content="small content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is True

    def test_reject_content_exceeds_limit(self):
        """测试：拒绝超过大小限制的内容"""
        from src.domain.services.save_request_audit import (
            ContentSizeRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = ContentSizeRule(max_size_bytes=100)  # 100 bytes

        large_content = "x" * 200  # 200 bytes

        request = SaveRequest(
            target_path="/tmp/large.txt",
            content=large_content,
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is False
        assert "size" in result.reason.lower()


class TestRateLimitRule:
    """频率限制规则测试"""

    def test_allow_within_rate_limit(self):
        """测试：允许在频率限制内的请求"""
        from src.domain.services.save_request_audit import (
            RateLimitRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = RateLimitRule(
            max_requests_per_minute=10,
            max_requests_per_session=100,
        )

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is True

    def test_reject_exceeds_session_rate_limit(self):
        """测试：拒绝超过会话频率限制的请求"""
        from src.domain.services.save_request_audit import (
            RateLimitRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = RateLimitRule(
            max_requests_per_minute=100,
            max_requests_per_session=3,
        )

        # 模拟达到限制
        for i in range(3):
            request = SaveRequest(
                target_path=f"/tmp/test{i}.txt",
                content="content",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="session-001",
                reason="test",
            )
            rule.evaluate(request)

        # 第四个请求应该被拒绝
        request = SaveRequest(
            target_path="/tmp/test4.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is False
        assert "rate" in result.reason.lower() or "limit" in result.reason.lower()


class TestSensitiveContentRule:
    """敏感内容检查规则测试"""

    def test_allow_safe_content(self):
        """测试：允许安全内容"""
        from src.domain.services.save_request_audit import (
            SensitiveContentRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = SensitiveContentRule()

        request = SaveRequest(
            target_path="/tmp/safe.txt",
            content="This is safe content without any secrets.",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is True

    def test_reject_content_with_api_key(self):
        """测试：拒绝包含 API 密钥的内容"""
        from src.domain.services.save_request_audit import (
            SensitiveContentRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = SensitiveContentRule()

        request = SaveRequest(
            target_path="/tmp/config.txt",
            content="api_key=sk-1234567890abcdef",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is False
        assert "sensitive" in result.reason.lower()

    def test_reject_content_with_password(self):
        """测试：拒绝包含密码的内容"""
        from src.domain.services.save_request_audit import (
            SensitiveContentRule,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        rule = SensitiveContentRule()

        request = SaveRequest(
            target_path="/tmp/config.txt",
            content='password="secretpassword123"',
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = rule.evaluate(request)

        assert result.passed is False


# =============================================================================
# 第三部分：审核引擎测试
# =============================================================================


class TestSaveRequestAuditor:
    """SaveRequestAuditor 审核引擎测试"""

    def test_auditor_with_no_rules_approves_all(self):
        """测试：无规则时审核通过所有请求"""
        from src.domain.services.save_request_audit import (
            AuditStatus,
            SaveRequestAuditor,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        auditor = SaveRequestAuditor(rules=[])

        request = SaveRequest(
            target_path="/any/path.txt",
            content="any content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = auditor.audit(request)

        assert result.status == AuditStatus.APPROVED

    def test_auditor_runs_all_rules(self):
        """测试：审核器运行所有规则"""
        from src.domain.services.save_request_audit import (
            AuditStatus,
            ContentSizeRule,
            PathBlacklistRule,
            SaveRequestAuditor,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        auditor = SaveRequestAuditor(rules=[
            PathBlacklistRule(blacklist=["/etc"]),
            ContentSizeRule(max_size_bytes=1024),
        ])

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="small content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = auditor.audit(request)

        assert result.status == AuditStatus.APPROVED

    def test_auditor_stops_on_first_rejection(self):
        """测试：审核器在第一个拒绝时停止"""
        from src.domain.services.save_request_audit import (
            AuditStatus,
            ContentSizeRule,
            PathBlacklistRule,
            SaveRequestAuditor,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        auditor = SaveRequestAuditor(rules=[
            PathBlacklistRule(blacklist=["/etc"]),
            ContentSizeRule(max_size_bytes=1024),
        ])

        request = SaveRequest(
            target_path="/etc/passwd",  # 黑名单路径
            content="small",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = auditor.audit(request)

        assert result.status == AuditStatus.REJECTED
        assert result.rule_id == "path_blacklist"

    def test_auditor_add_rule_dynamically(self):
        """测试：动态添加规则"""
        from src.domain.services.save_request_audit import (
            ContentSizeRule,
            SaveRequestAuditor,
        )

        auditor = SaveRequestAuditor(rules=[])
        assert len(auditor.rules) == 0

        auditor.add_rule(ContentSizeRule(max_size_bytes=1024))
        assert len(auditor.rules) == 1

    def test_auditor_remove_rule(self):
        """测试：移除规则"""
        from src.domain.services.save_request_audit import (
            ContentSizeRule,
            SaveRequestAuditor,
        )

        rule = ContentSizeRule(max_size_bytes=1024)
        auditor = SaveRequestAuditor(rules=[rule])

        auditor.remove_rule("content_size")
        assert len(auditor.rules) == 0


# =============================================================================
# 第四部分：保存执行器测试
# =============================================================================


class TestSaveExecutor:
    """SaveExecutor 执行器测试"""

    def test_execute_file_write_success(self):
        """测试：文件写入执行成功"""
        from src.domain.services.save_request_audit import SaveExecutor
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        executor = SaveExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "output.txt")

            request = SaveRequest(
                target_path=target_path,
                content="Hello, World!",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="session-001",
                reason="test",
            )

            result = executor.execute(request)

            assert result.success is True
            assert result.bytes_written == 13
            assert result.error_message is None
            assert os.path.exists(target_path)

            with open(target_path, "r") as f:
                assert f.read() == "Hello, World!"

    def test_execute_file_append_success(self):
        """测试：文件追加执行成功"""
        from src.domain.services.save_request_audit import SaveExecutor
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        executor = SaveExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "output.txt")

            # 先写入初始内容
            with open(target_path, "w") as f:
                f.write("Initial. ")

            request = SaveRequest(
                target_path=target_path,
                content="Appended.",
                operation_type=SaveRequestType.FILE_APPEND,
                session_id="session-001",
                reason="test",
            )

            result = executor.execute(request)

            assert result.success is True

            with open(target_path, "r") as f:
                assert f.read() == "Initial. Appended."

    def test_execute_file_delete_success(self):
        """测试：文件删除执行成功"""
        from src.domain.services.save_request_audit import SaveExecutor
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        executor = SaveExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "to_delete.txt")

            # 先创建文件
            with open(target_path, "w") as f:
                f.write("to be deleted")

            assert os.path.exists(target_path)

            request = SaveRequest(
                target_path=target_path,
                content="",
                operation_type=SaveRequestType.FILE_DELETE,
                session_id="session-001",
                reason="test",
            )

            result = executor.execute(request)

            assert result.success is True
            assert not os.path.exists(target_path)

    def test_execute_creates_parent_directories(self):
        """测试：执行时自动创建父目录"""
        from src.domain.services.save_request_audit import SaveExecutor
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        executor = SaveExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "nested", "deep", "output.txt")

            request = SaveRequest(
                target_path=target_path,
                content="nested content",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="session-001",
                reason="test",
            )

            result = executor.execute(request)

            assert result.success is True
            assert os.path.exists(target_path)

    def test_execute_binary_content(self):
        """测试：执行二进制内容写入"""
        from src.domain.services.save_request_audit import SaveExecutor
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        executor = SaveExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "binary.bin")
            binary_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00'

            request = SaveRequest(
                target_path=target_path,
                content=binary_content,
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="session-001",
                reason="test",
                is_binary=True,
            )

            result = executor.execute(request)

            assert result.success is True

            with open(target_path, "rb") as f:
                assert f.read() == binary_content

    def test_execute_failure_permission_denied(self):
        """测试：执行失败 - 权限拒绝"""
        from src.domain.services.save_request_audit import SaveExecutor
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        executor = SaveExecutor()

        # 尝试写入系统保护路径
        request = SaveRequest(
            target_path="/root/protected.txt",
            content="test",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        result = executor.execute(request)

        # 在大多数系统上这会失败（除非以 root 运行）
        # 如果测试以 root 运行，这个测试可能会通过
        if not result.success:
            assert result.error_message is not None
            assert result.bytes_written == 0

    def test_execute_delete_nonexistent_file(self):
        """测试：删除不存在的文件"""
        from src.domain.services.save_request_audit import SaveExecutor
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        executor = SaveExecutor()

        request = SaveRequest(
            target_path="/tmp/nonexistent_file_xyz.txt",
            content="",
            operation_type=SaveRequestType.FILE_DELETE,
            session_id="session-001",
            reason="test",
        )

        result = executor.execute(request)

        # 删除不存在的文件应该报错
        assert result.success is False
        assert "not found" in result.error_message.lower() or "not exist" in result.error_message.lower()


# =============================================================================
# 第五部分：审计日志测试
# =============================================================================


class TestAuditLogger:
    """AuditLogger 审计日志测试"""

    def test_log_audit_decision(self):
        """测试：记录审核决策日志"""
        from src.domain.services.save_request_audit import (
            AuditLogger,
            AuditResult,
            AuditStatus,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        logger = AuditLogger()

        request = SaveRequest(
            target_path="/tmp/test.txt",
            content="content",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        audit_result = AuditResult(
            request_id=request.request_id,
            status=AuditStatus.APPROVED,
            rule_id=None,
            reason="All rules passed",
        )

        logger.log_audit(request, audit_result)

        # 验证日志已记录
        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0]["request_id"] == request.request_id
        assert logs[0]["status"] == "approved"
        assert logs[0]["target_path"] == "/tmp/test.txt"

    def test_log_execution_result(self):
        """测试：记录执行结果日志"""
        from src.domain.services.save_request_audit import (
            AuditLogger,
            ExecutionResult,
        )

        logger = AuditLogger()

        exec_result = ExecutionResult(
            request_id="save-123456",
            success=True,
            error_message=None,
            bytes_written=1024,
            execution_time_ms=15.5,
        )

        logger.log_execution(exec_result)

        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0]["request_id"] == "save-123456"
        assert logs[0]["success"] is True
        assert logs[0]["bytes_written"] == 1024

    def test_log_rejection_with_reason(self):
        """测试：记录拒绝原因日志"""
        from src.domain.services.save_request_audit import (
            AuditLogger,
            AuditResult,
            AuditStatus,
            RejectionReason,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        logger = AuditLogger()

        request = SaveRequest(
            target_path="/etc/passwd",
            content="malicious",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )

        audit_result = AuditResult(
            request_id=request.request_id,
            status=AuditStatus.REJECTED,
            rule_id="path_blacklist",
            reason=RejectionReason.PATH_BLACKLISTED.value,
        )

        logger.log_audit(request, audit_result)

        logs = logger.get_logs()
        assert len(logs) == 1
        assert logs[0]["status"] == "rejected"
        assert logs[0]["rule_id"] == "path_blacklist"
        assert logs[0]["reason"] == "path_blacklisted"

    def test_get_logs_by_session(self):
        """测试：按会话获取日志"""
        from src.domain.services.save_request_audit import (
            AuditLogger,
            AuditResult,
            AuditStatus,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        logger = AuditLogger()

        # 记录不同会话的日志
        for session_id in ["session-A", "session-B", "session-A"]:
            request = SaveRequest(
                target_path="/tmp/test.txt",
                content="content",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id=session_id,
                reason="test",
            )
            logger.log_audit(
                request,
                AuditResult(
                    request_id=request.request_id,
                    status=AuditStatus.APPROVED,
                    rule_id=None,
                    reason="OK",
                )
            )

        session_a_logs = logger.get_logs_by_session("session-A")
        assert len(session_a_logs) == 2

        session_b_logs = logger.get_logs_by_session("session-B")
        assert len(session_b_logs) == 1


# =============================================================================
# 第六部分：Coordinator 集成测试
# =============================================================================


class TestCoordinatorAuditExecution:
    """Coordinator 审核执行集成测试"""

    def test_coordinator_process_approved_request(self):
        """测试：Coordinator 处理审核通过的请求"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "output.txt")

            # 配置审核器允许临时目录路径
            coordinator.configure_save_auditor(
                path_whitelist=[tmpdir, "/tmp"],
                max_content_size=1024 * 1024,
            )

            # 创建并入队请求
            request = SaveRequest(
                target_path=target_path,
                content="approved content",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="session-001",
                reason="test",
            )
            event_bus.publish(request)

            # 处理请求
            result = coordinator.process_next_save_request()

            assert result is not None
            assert result.success is True
            assert os.path.exists(target_path)

    def test_coordinator_process_rejected_request(self):
        """测试：Coordinator 处理审核拒绝的请求"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_audit import AuditStatus
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        # 配置审核器禁止 /etc 路径
        coordinator.configure_save_auditor(
            path_blacklist=["/etc"],
        )

        # 创建并入队请求
        request = SaveRequest(
            target_path="/etc/passwd",
            content="malicious",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )
        event_bus.publish(request)

        # 处理请求
        result = coordinator.process_next_save_request()

        assert result is not None
        assert result.success is False
        assert result.audit_status == AuditStatus.REJECTED

    def test_coordinator_emits_completion_event(self):
        """测试：Coordinator 发布完成事件"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_audit import (
            SaveRequestCompletedEvent,
        )
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        # 订阅完成事件
        completed_events = []
        event_bus.subscribe(
            SaveRequestCompletedEvent,
            lambda e: completed_events.append(e)
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # 配置审核器允许临时目录路径
            coordinator.configure_save_auditor(path_whitelist=[tmpdir, "/tmp"])
            target_path = os.path.join(tmpdir, "output.txt")

            request = SaveRequest(
                target_path=target_path,
                content="content",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="session-001",
                reason="test",
            )
            event_bus.publish(request)

            coordinator.process_next_save_request()

            assert len(completed_events) == 1
            assert completed_events[0].request_id == request.request_id
            assert completed_events[0].success is True

    def test_coordinator_get_audit_logs(self):
        """测试：Coordinator 获取审计日志"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        with tempfile.TemporaryDirectory() as tmpdir:
            # 配置审核器允许临时目录路径
            coordinator.configure_save_auditor(path_whitelist=[tmpdir, "/tmp"])
            target_path = os.path.join(tmpdir, "output.txt")

            request = SaveRequest(
                target_path=target_path,
                content="content",
                operation_type=SaveRequestType.FILE_WRITE,
                session_id="session-001",
                reason="test",
            )
            event_bus.publish(request)
            coordinator.process_next_save_request()

        logs = coordinator.get_save_audit_logs()
        assert len(logs) >= 1

    def test_coordinator_execution_failure_handling(self):
        """测试：Coordinator 处理执行失败"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_channel import (
            SaveRequest,
            SaveRequestType,
        )

        event_bus = SyncEventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()
        # 允许所有路径以通过审核
        coordinator.configure_save_auditor(path_whitelist=["/"])

        # 尝试写入受保护路径（应该在执行时失败）
        request = SaveRequest(
            target_path="/root/protected_test.txt",
            content="test",
            operation_type=SaveRequestType.FILE_WRITE,
            session_id="session-001",
            reason="test",
        )
        event_bus.publish(request)

        result = coordinator.process_next_save_request()

        # 除非以 root 运行，否则应该失败
        if result and not result.success:
            assert result.error_message is not None


# =============================================================================
# 第七部分：端到端场景测试
# =============================================================================


class TestAuditExecutionEndToEnd:
    """端到端场景测试"""

    def test_full_workflow_approved_and_executed(self):
        """测试：完整流程 - 审核通过并执行"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        event_bus = SyncEventBus()
        mock_llm = MagicMock()

        # 设置会话上下文
        session_context = create_test_session_context("user-session-001")

        # 创建 ConversationAgent
        conversation_agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )
        conversation_agent.enable_save_request_channel()

        # 创建 Coordinator
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "result.json")

            # 配置审核器允许临时目录路径
            coordinator.configure_save_auditor(
                path_whitelist=[tmpdir, "/tmp"],
                max_content_size=1024 * 1024,
            )

            # ConversationAgent 发起保存请求
            conversation_agent.request_save(
                target_path=target_path,
                content='{"result": "success"}',
                reason="Save analysis result",
            )

            # Coordinator 处理请求
            result = coordinator.process_next_save_request()

            # 验证
            assert result.success is True
            assert os.path.exists(target_path)

            with open(target_path, "r") as f:
                content = f.read()
                assert "success" in content

    def test_full_workflow_rejected_by_blacklist(self):
        """测试：完整流程 - 被黑名单拒绝"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_audit import AuditStatus

        event_bus = SyncEventBus()
        mock_llm = MagicMock()

        session_context = create_test_session_context("user-session-001")

        conversation_agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )
        conversation_agent.enable_save_request_channel()

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()
        coordinator.configure_save_auditor(
            path_blacklist=["/etc", "/sys", "/proc"],
        )

        # 尝试保存到黑名单路径
        conversation_agent.request_save(
            target_path="/etc/malicious.conf",
            content="malicious content",
            reason="Attempt to write to system path",
        )

        # Coordinator 处理请求
        result = coordinator.process_next_save_request()

        # 验证被拒绝
        assert result.success is False
        assert result.audit_status == AuditStatus.REJECTED
        assert not os.path.exists("/etc/malicious.conf")

    def test_full_workflow_rejected_by_content_size(self):
        """测试：完整流程 - 内容过大被拒绝"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.save_request_audit import AuditStatus

        event_bus = SyncEventBus()
        mock_llm = MagicMock()

        session_context = create_test_session_context("user-session-001")

        conversation_agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            event_bus=event_bus,
        )
        conversation_agent.enable_save_request_channel()

        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.enable_save_request_handler()
        coordinator.configure_save_auditor(
            path_whitelist=["/tmp"],
            max_content_size=100,  # 只允许 100 字节
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, "large.txt")

            # 尝试保存大文件
            large_content = "x" * 1000  # 1000 字节
            conversation_agent.request_save(
                target_path=target_path,
                content=large_content,
                reason="Save large file",
            )

            result = coordinator.process_next_save_request()

            # 验证被拒绝
            assert result.success is False
            assert result.audit_status == AuditStatus.REJECTED
            assert not os.path.exists(target_path)
