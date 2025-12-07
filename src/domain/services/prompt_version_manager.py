"""提示词版本管理系统

实现 Prompt 版本控制流程：
1. 版本命名规则（语义化版本 MAJOR.MINOR.PATCH）
2. 变更流程（新增→记录原因→协调者审批）
3. Coordinator 加载指定版本
4. 回滚策略

创建日期：2025-12-07
"""

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# =============================================================================
# 异常定义
# =============================================================================


class ApprovalError(Exception):
    """审批错误"""

    pass


class VersionNotFoundError(Exception):
    """版本未找到错误"""

    pass


# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class PromptVersion:
    """提示词版本

    Attributes:
        version: 语义化版本号 (MAJOR.MINOR.PATCH)
        module_name: 模块名称
        template: 模板内容
        variables: 变量列表
        changelog: 变更说明
        author: 作者
        created_at: 创建时间
    """

    version: str
    module_name: str
    template: str
    variables: list[str]
    changelog: str
    author: str
    created_at: datetime = field(default_factory=datetime.now)

    # 语义化版本正则
    _VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

    def is_valid_version(self) -> bool:
        """验证版本号是否符合语义化版本规范"""
        return bool(self._VERSION_PATTERN.match(self.version))

    def _parse_version(self) -> tuple[int, int, int]:
        """解析版本号为元组"""
        parts = self.version.split(".")
        if len(parts) != 3:
            return (0, 0, 0)
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return (0, 0, 0)

    def __lt__(self, other: "PromptVersion") -> bool:
        """版本比较：小于"""
        return self._parse_version() < other._parse_version()

    def __le__(self, other: "PromptVersion") -> bool:
        """版本比较：小于等于"""
        return self._parse_version() <= other._parse_version()

    def __gt__(self, other: "PromptVersion") -> bool:
        """版本比较：大于"""
        return self._parse_version() > other._parse_version()

    def __ge__(self, other: "PromptVersion") -> bool:
        """版本比较：大于等于"""
        return self._parse_version() >= other._parse_version()


@dataclass
class VersionChangeRecord:
    """版本变更记录

    Attributes:
        id: 记录ID
        from_version: 原版本
        to_version: 目标版本
        module_name: 模块名称
        change_type: 变更类型 (major/minor/patch)
        reason: 变更原因
        author: 提交者
        status: 审批状态 (pending/approved/rejected)
        approver: 审批人
        approved_at: 审批时间
        rejection_reason: 拒绝原因
    """

    from_version: str
    to_version: str
    module_name: str
    change_type: str  # major, minor, patch
    reason: str
    author: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    approver: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class RollbackResult:
    """回滚结果

    Attributes:
        success: 是否成功
        from_version: 回滚前版本
        to_version: 回滚后版本
        reason: 回滚原因
        timestamp: 回滚时间
    """

    success: bool
    from_version: str
    to_version: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RollbackHistory:
    """回滚历史记录"""

    from_version: str
    to_version: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AuditLog:
    """审计日志

    Attributes:
        action: 操作类型 (register/activate/rollback/approve/reject)
        module_name: 模块名称
        version: 版本号
        actor: 操作者
        details: 详细信息
        timestamp: 时间戳
    """

    action: str
    module_name: str
    version: str
    actor: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LoadingLog:
    """加载日志"""

    module_name: str
    version: str
    timestamp: datetime = field(default_factory=datetime.now)


# =============================================================================
# 版本配置
# =============================================================================


@dataclass
class VersionConfig:
    """版本配置

    用于配置驱动的版本控制，指定各模块使用的版本。
    """

    _versions: dict[str, str] = field(default_factory=dict)

    def get_version(self, module_name: str) -> str | None:
        """获取模块的配置版本"""
        return self._versions.get(module_name)

    def set_version(self, module_name: str, version: str) -> None:
        """设置模块的配置版本"""
        self._versions[module_name] = version

    @classmethod
    def from_dict(cls, config: dict[str, str]) -> "VersionConfig":
        """从字典创建配置"""
        instance = cls()
        instance._versions = dict(config)
        return instance


# =============================================================================
# 版本管理器
# =============================================================================


class PromptVersionManager:
    """提示词版本管理器

    负责：
    1. 版本注册与存储
    2. 版本历史管理
    3. 活跃版本管理
    4. 变更审批流程
    5. 回滚策略
    6. 审计日志
    """

    # 允许审批的角色
    APPROVER_ROLES = {"coordinator", "admin", "system"}

    def __init__(self) -> None:
        # 版本存储: module_name -> [versions]
        self._versions: dict[str, list[PromptVersion]] = {}
        # 活跃版本: module_name -> version_str
        self._active_versions: dict[str, str] = {}
        # 变更记录: record_id -> VersionChangeRecord
        self._change_records: dict[str, VersionChangeRecord] = {}
        # 回滚历史: module_name -> [RollbackHistory]
        self._rollback_history: dict[str, list[RollbackHistory]] = {}
        # 审计日志: module_name -> [AuditLog]
        self._audit_logs: dict[str, list[AuditLog]] = {}
        # 线程锁
        self._lock = threading.RLock()

    def register_version(
        self,
        module_name: str,
        version: str,
        template: str,
        variables: list[str],
        changelog: str,
        author: str,
    ) -> PromptVersion:
        """注册新版本

        Args:
            module_name: 模块名称
            version: 版本号
            template: 模板内容
            variables: 变量列表
            changelog: 变更说明
            author: 作者

        Returns:
            PromptVersion: 创建的版本对象
        """
        with self._lock:
            prompt_version = PromptVersion(
                version=version,
                module_name=module_name,
                template=template,
                variables=variables,
                changelog=changelog,
                author=author,
            )

            # 初始化模块存储
            if module_name not in self._versions:
                self._versions[module_name] = []
                self._rollback_history[module_name] = []
                self._audit_logs[module_name] = []

            # 添加版本
            self._versions[module_name].append(prompt_version)

            # 如果是第一个版本，设为活跃版本
            if module_name not in self._active_versions:
                self._active_versions[module_name] = version

            # 记录审计日志
            self._add_audit_log(
                action="register",
                module_name=module_name,
                version=version,
                actor=author,
                details={"changelog": changelog},
            )

            return prompt_version

    def get_current_version(self, module_name: str) -> str | None:
        """获取模块当前活跃版本号"""
        with self._lock:
            return self._active_versions.get(module_name)

    def get_version(self, module_name: str, version: str) -> PromptVersion:
        """获取指定版本

        Args:
            module_name: 模块名称
            version: 版本号

        Returns:
            PromptVersion: 版本对象

        Raises:
            VersionNotFoundError: 版本不存在
        """
        with self._lock:
            versions = self._versions.get(module_name, [])
            for v in versions:
                if v.version == version:
                    return v
            raise VersionNotFoundError(f"Version {version} not found for module {module_name}")

    def get_active_version(self, module_name: str) -> PromptVersion:
        """获取活跃版本对象"""
        with self._lock:
            active_version = self._active_versions.get(module_name)
            if not active_version:
                raise VersionNotFoundError(f"No active version for module {module_name}")
            return self.get_version(module_name, active_version)

    def get_version_history(self, module_name: str) -> list[PromptVersion]:
        """获取版本历史"""
        with self._lock:
            return list(self._versions.get(module_name, []))

    def set_active_version(self, module_name: str, version: str) -> None:
        """设置活跃版本

        Args:
            module_name: 模块名称
            version: 版本号

        Raises:
            VersionNotFoundError: 版本不存在
        """
        with self._lock:
            # 验证版本存在
            self.get_version(module_name, version)

            # 设置活跃版本
            self._active_versions[module_name] = version

            # 记录审计日志
            self._add_audit_log(
                action="activate",
                module_name=module_name,
                version=version,
                actor="system",
            )

    def submit_change(
        self,
        module_name: str,
        new_version: str,
        template: str,
        variables: list[str],
        reason: str,
        author: str,
    ) -> VersionChangeRecord:
        """提交版本变更申请

        Args:
            module_name: 模块名称
            new_version: 新版本号
            template: 新模板内容
            variables: 变量列表
            reason: 变更原因
            author: 提交者

        Returns:
            VersionChangeRecord: 变更记录
        """
        with self._lock:
            # 获取当前版本
            current_version = self._active_versions.get(module_name, "0.0.0")

            # 判断变更类型
            change_type = self._determine_change_type(current_version, new_version)

            # 创建变更记录
            record = VersionChangeRecord(
                from_version=current_version,
                to_version=new_version,
                module_name=module_name,
                change_type=change_type,
                reason=reason,
                author=author,
            )

            # 存储变更记录和待审批的版本
            self._change_records[record.id] = record

            # 预注册版本（待审批状态）
            self.register_version(
                module_name=module_name,
                version=new_version,
                template=template,
                variables=variables,
                changelog=f"[待审批] {reason}",
                author=author,
            )

            return record

    def approve_change(
        self,
        record_id: str,
        approver: str,
        comment: str = "",
    ) -> VersionChangeRecord:
        """审批通过版本变更

        Args:
            record_id: 变更记录ID
            approver: 审批人
            comment: 审批意见

        Returns:
            VersionChangeRecord: 更新后的变更记录

        Raises:
            ApprovalError: 审批错误
        """
        with self._lock:
            # 验证审批权限
            if approver not in self.APPROVER_ROLES:
                raise ApprovalError(f"User '{approver}' is not authorized to approve changes")

            # 获取变更记录
            record = self._change_records.get(record_id)
            if not record:
                raise ApprovalError(f"Change record {record_id} not found")

            # 更新状态
            record.status = "approved"
            record.approver = approver
            record.approved_at = datetime.now()

            # 激活新版本
            self.set_active_version(record.module_name, record.to_version)

            # 记录审计日志
            self._add_audit_log(
                action="approve",
                module_name=record.module_name,
                version=record.to_version,
                actor=approver,
                details={"comment": comment, "from_version": record.from_version},
            )

            return record

    def reject_change(
        self,
        record_id: str,
        approver: str,
        reason: str,
    ) -> VersionChangeRecord:
        """拒绝版本变更

        Args:
            record_id: 变更记录ID
            approver: 审批人
            reason: 拒绝原因

        Returns:
            VersionChangeRecord: 更新后的变更记录
        """
        with self._lock:
            record = self._change_records.get(record_id)
            if not record:
                raise ApprovalError(f"Change record {record_id} not found")

            record.status = "rejected"
            record.approver = approver
            record.rejection_reason = reason

            # 记录审计日志
            self._add_audit_log(
                action="reject",
                module_name=record.module_name,
                version=record.to_version,
                actor=approver,
                details={"reason": reason},
            )

            return record

    def rollback(
        self,
        module_name: str,
        target_version: str | None = None,
        reason: str = "",
    ) -> RollbackResult:
        """回滚版本

        Args:
            module_name: 模块名称
            target_version: 目标版本（不指定则回滚到上一个版本）
            reason: 回滚原因

        Returns:
            RollbackResult: 回滚结果
        """
        with self._lock:
            current_version = self._active_versions.get(module_name)
            if not current_version:
                return RollbackResult(
                    success=False,
                    from_version="",
                    to_version="",
                    reason="No active version to rollback",
                )

            # 获取版本历史
            versions = self._versions.get(module_name, [])
            if len(versions) < 2 and not target_version:
                return RollbackResult(
                    success=False,
                    from_version=current_version,
                    to_version="",
                    reason="No previous version to rollback to",
                )

            # 确定目标版本
            if target_version:
                # 验证目标版本存在
                try:
                    self.get_version(module_name, target_version)
                except VersionNotFoundError:
                    return RollbackResult(
                        success=False,
                        from_version=current_version,
                        to_version=target_version,
                        reason=f"Target version {target_version} not found",
                    )
            else:
                # 找到上一个版本
                sorted_versions = sorted(versions, key=lambda v: v._parse_version())
                current_idx = next(
                    (i for i, v in enumerate(sorted_versions) if v.version == current_version),
                    -1,
                )
                if current_idx <= 0:
                    return RollbackResult(
                        success=False,
                        from_version=current_version,
                        to_version="",
                        reason="No previous version to rollback to",
                    )
                target_version = sorted_versions[current_idx - 1].version

            # 执行回滚
            self._active_versions[module_name] = target_version

            # 记录回滚历史
            rollback_history = RollbackHistory(
                from_version=current_version,
                to_version=target_version,
                reason=reason,
            )
            self._rollback_history[module_name].append(rollback_history)

            # 记录审计日志
            self._add_audit_log(
                action="rollback",
                module_name=module_name,
                version=target_version,
                actor="system",
                details={
                    "from_version": current_version,
                    "reason": reason,
                },
            )

            return RollbackResult(
                success=True,
                from_version=current_version,
                to_version=target_version,
                reason=reason,
            )

    def get_rollback_history(self, module_name: str) -> list[RollbackHistory]:
        """获取回滚历史"""
        with self._lock:
            return list(self._rollback_history.get(module_name, []))

    def get_audit_logs(self, module_name: str) -> list[AuditLog]:
        """获取审计日志"""
        with self._lock:
            return list(self._audit_logs.get(module_name, []))

    def _add_audit_log(
        self,
        action: str,
        module_name: str,
        version: str,
        actor: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """添加审计日志"""
        log = AuditLog(
            action=action,
            module_name=module_name,
            version=version,
            actor=actor,
            details=details or {},
        )
        if module_name not in self._audit_logs:
            self._audit_logs[module_name] = []
        self._audit_logs[module_name].append(log)

    def _determine_change_type(self, from_version: str, to_version: str) -> str:
        """判断变更类型"""
        from_parts = from_version.split(".")
        to_parts = to_version.split(".")

        if len(from_parts) != 3 or len(to_parts) != 3:
            return "unknown"

        try:
            from_major, from_minor, from_patch = map(int, from_parts)
            to_major, to_minor, to_patch = map(int, to_parts)
        except ValueError:
            return "unknown"

        if to_major > from_major:
            return "major"
        elif to_minor > from_minor:
            return "minor"
        else:
            return "patch"


# =============================================================================
# Coordinator 集成
# =============================================================================


class CoordinatorPromptLoader:
    """Coordinator 提示词加载器

    提供给 CoordinatorAgent 使用的版本加载接口。
    支持：
    1. 加载指定版本
    2. 运行时切换版本
    3. 配置驱动的版本控制
    4. 加载日志记录
    """

    def __init__(self, manager: PromptVersionManager) -> None:
        self._manager = manager
        self._loading_logs: list[LoadingLog] = []
        self._config: VersionConfig | None = None

    def load_template(
        self,
        module_name: str,
        version: str | None = None,
    ) -> str:
        """加载模板

        Args:
            module_name: 模块名称
            version: 版本号（不指定则使用配置版本或活跃版本）

        Returns:
            str: 模板内容
        """
        # 确定版本
        if version is None:
            # 优先使用配置版本
            if self._config:
                config_version = self._config.get_version(module_name)
                if config_version and config_version != "latest":
                    version = config_version

            # 否则使用活跃版本
            if version is None:
                version = self._manager.get_current_version(module_name)

        # 加载版本（确保 version 不为 None）
        if version is None:
            raise ValueError(f"No version available for module {module_name}")

        prompt_version = self._manager.get_version(module_name, version)

        # 记录加载日志
        self._loading_logs.append(
            LoadingLog(
                module_name=module_name,
                version=version,
            )
        )

        return prompt_version.template

    def get_loading_logs(self) -> list[LoadingLog]:
        """获取加载日志"""
        return list(self._loading_logs)

    def apply_config(self, config: VersionConfig) -> None:
        """应用版本配置

        Args:
            config: 版本配置
        """
        self._config = config
