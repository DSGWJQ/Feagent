"""PromptVersionFacade - 提示词版本管理门面

从 CoordinatorAgent 拆分出来的独立服务，负责提示词版本的：
- 注册与加载
- 版本切换与回滚
- 变更审批流程
- 审计日志

设计原则：
- 单一职责：只负责提示词版本管理
- 延迟初始化：按需创建底层服务
- 向后兼容：CoordinatorAgent 可以通过代理方法调用
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.services.prompt_version_manager import (
        CoordinatorPromptLoader,
        PromptVersion,
        PromptVersionManager,
        RollbackResult,
        VersionChangeRecord,
        VersionConfig,
    )


class PromptVersionFacade:
    """提示词版本管理门面

    提供统一的提示词版本管理接口，封装底层的 PromptVersionManager
    和 CoordinatorPromptLoader。

    使用示例：
        facade = PromptVersionFacade(config={"module_a": "1.0.0"})
        facade.initialize()
        template = facade.load_prompt_template("module_a")
    """

    def __init__(
        self,
        config: dict[str, str] | None = None,
        log_collector: Any | None = None,
    ) -> None:
        """初始化提示词版本门面

        参数：
            config: 版本配置字典 {module_name: version}
            log_collector: 日志收集器（可选）
        """
        self._config = config
        self._log_collector = log_collector

        # 延迟初始化的组件
        self._prompt_version_manager: PromptVersionManager | None = None
        self._prompt_loader: CoordinatorPromptLoader | None = None
        self._prompt_version_config: VersionConfig | None = None

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._prompt_version_manager is not None

    @property
    def prompt_version_manager(self) -> PromptVersionManager | None:
        """获取提示词版本管理器"""
        return self._prompt_version_manager

    def initialize(self, config: dict[str, str] | None = None) -> None:
        """初始化提示词版本管理器

        参数：
            config: 版本配置字典（覆盖构造函数中的配置）
        """
        if self._prompt_version_manager is not None:
            return  # 幂等：已初始化则跳过

        from src.domain.services.prompt_version_manager import (
            CoordinatorPromptLoader,
            PromptVersionManager,
            VersionConfig,
        )

        self._prompt_version_manager = PromptVersionManager()
        self._prompt_loader = CoordinatorPromptLoader(self._prompt_version_manager)

        # 使用传入的 config 或构造函数中的 config
        effective_config = config or self._config
        if effective_config:
            self._prompt_version_config = VersionConfig.from_dict(effective_config)
            self._prompt_loader.apply_config(self._prompt_version_config)

        self._log("提示词版本管理器已初始化", {"config": effective_config or {}})

    def _ensure_initialized(self) -> None:
        """确保已初始化（用于需要初始化的操作）"""
        if not self.is_initialized:
            self.initialize()

    def _log(
        self,
        message: str,
        data: dict[str, Any] | None = None,
        level: str = "info",
    ) -> None:
        """记录日志（如果有 log_collector）"""
        if self._log_collector:
            log_method = getattr(self._log_collector, level, self._log_collector.info)
            log_method("PromptVersionFacade", message, data or {})

    # ==================== 版本注册 ====================

    def register_prompt_version(
        self,
        module_name: str,
        version: str,
        template: str,
        variables: list[str],
        changelog: str,
        author: str = "system",
    ) -> PromptVersion:
        """注册新的提示词版本

        参数：
            module_name: 模块名称
            version: 版本号 (语义化版本 x.y.z)
            template: 模板内容
            variables: 变量列表
            changelog: 变更说明
            author: 作者

        返回：
            PromptVersion 对象
        """
        self._ensure_initialized()
        if self._prompt_version_manager is None:
            raise RuntimeError("提示词版本管理器初始化失败")

        prompt_version = self._prompt_version_manager.register_version(
            module_name=module_name,
            version=version,
            template=template,
            variables=variables,
            changelog=changelog,
            author=author,
        )

        self._log(
            f"已注册提示词版本: {module_name}@{version}",
            {"module_name": module_name, "version": version, "author": author},
        )

        return prompt_version

    # ==================== 模板加载 ====================

    def load_prompt_template(
        self,
        module_name: str,
        version: str | None = None,
    ) -> str:
        """加载提示词模板

        参数：
            module_name: 模块名称
            version: 版本号（不指定则使用活跃版本）

        返回：
            模板内容
        """
        self._ensure_initialized()
        if self._prompt_loader is None:
            raise RuntimeError("提示词加载器初始化失败")

        template = self._prompt_loader.load_template(module_name, version)

        self._log(
            f"已加载提示词模板: {module_name}@{version or 'active'}",
            {"module_name": module_name, "version": version},
        )

        return template

    # ==================== 版本切换 ====================

    def switch_prompt_version(
        self,
        module_name: str,
        version: str,
    ) -> None:
        """切换提示词版本

        参数：
            module_name: 模块名称
            version: 目标版本号
        """
        self._ensure_initialized()
        if self._prompt_version_manager is None:
            raise RuntimeError("提示词版本管理器初始化失败")

        self._prompt_version_manager.set_active_version(module_name, version)

        self._log(
            f"已切换提示词版本: {module_name} -> {version}",
            {"module_name": module_name, "version": version},
        )

    # ==================== 版本回滚 ====================

    def rollback_prompt_version(
        self,
        module_name: str,
        target_version: str | None = None,
        reason: str = "",
    ) -> RollbackResult:
        """回滚提示词版本

        参数：
            module_name: 模块名称
            target_version: 目标版本（不指定则回滚到上一版本）
            reason: 回滚原因

        返回：
            RollbackResult 对象
        """
        if not self._prompt_version_manager:
            raise ValueError("提示词版本管理器未初始化")

        result = self._prompt_version_manager.rollback(
            module_name=module_name,
            target_version=target_version,
            reason=reason,
        )

        if result.success:
            self._log(
                f"已回滚提示词版本: {module_name} {result.from_version} -> {result.to_version}",
                {
                    "module_name": module_name,
                    "from_version": result.from_version,
                    "to_version": result.to_version,
                    "reason": reason,
                },
                level="warning",
            )
        else:
            self._log(
                f"提示词版本回滚失败: {module_name}",
                {"reason": result.reason},
                level="error",
            )

        return result

    # ==================== 审计与历史 ====================

    def get_prompt_audit_logs(self, module_name: str) -> list[Any]:
        """获取提示词版本审计日志

        参数：
            module_name: 模块名称

        返回：
            审计日志列表
        """
        if not self._prompt_version_manager:
            return []

        return self._prompt_version_manager.get_audit_logs(module_name)

    def get_prompt_version_history(self, module_name: str) -> list[Any]:
        """获取提示词版本历史

        参数：
            module_name: 模块名称

        返回：
            版本历史列表
        """
        if not self._prompt_version_manager:
            return []

        return self._prompt_version_manager.get_version_history(module_name)

    def get_prompt_loading_logs(self) -> list[Any]:
        """获取提示词加载日志

        返回：
            加载日志列表
        """
        if not self._prompt_loader:
            return []

        return self._prompt_loader.get_loading_logs()

    # ==================== 变更管理 ====================

    def submit_prompt_change(
        self,
        module_name: str,
        new_version: str,
        template: str,
        variables: list[str],
        reason: str,
        author: str,
    ) -> VersionChangeRecord:
        """提交提示词变更申请

        参数：
            module_name: 模块名称
            new_version: 新版本号
            template: 新模板内容
            variables: 变量列表
            reason: 变更原因
            author: 提交者

        返回：
            VersionChangeRecord 对象
        """
        self._ensure_initialized()
        if self._prompt_version_manager is None:
            raise RuntimeError("提示词版本管理器初始化失败")

        record = self._prompt_version_manager.submit_change(
            module_name=module_name,
            new_version=new_version,
            template=template,
            variables=variables,
            reason=reason,
            author=author,
        )

        self._log(
            f"已提交提示词变更申请: {module_name}@{new_version}",
            {"record_id": record.id, "author": author, "reason": reason},
        )

        return record

    def approve_prompt_change(
        self,
        record_id: str,
        comment: str = "",
    ) -> VersionChangeRecord:
        """审批通过提示词变更

        参数：
            record_id: 变更记录ID
            comment: 审批意见

        返回：
            更新后的 VersionChangeRecord 对象
        """
        if not self._prompt_version_manager:
            raise ValueError("提示词版本管理器未初始化")

        result = self._prompt_version_manager.approve_change(
            record_id=record_id,
            approver="coordinator",  # 使用 coordinator 角色（已在 APPROVER_ROLES 中授权）
            comment=comment,
        )

        self._log(
            f"已审批提示词变更: {result.module_name}@{result.to_version}",
            {"record_id": record_id, "comment": comment},
        )

        return result

    def reject_prompt_change(
        self,
        record_id: str,
        reason: str,
    ) -> VersionChangeRecord:
        """拒绝提示词变更

        参数：
            record_id: 变更记录ID
            reason: 拒绝原因

        返回：
            更新后的 VersionChangeRecord 对象
        """
        if not self._prompt_version_manager:
            raise ValueError("提示词版本管理器未初始化")

        result = self._prompt_version_manager.reject_change(
            record_id=record_id,
            approver="coordinator",  # 使用 coordinator 角色
            reason=reason,
        )

        self._log(
            f"已拒绝提示词变更: {result.module_name}@{result.to_version}",
            {"record_id": record_id, "reason": reason},
            level="warning",
        )

        return result
