"""提示词版本管理系统单元测试 (TDD)

测试 Prompt 版本控制流程：
1. 版本命名规则（语义化版本）
2. 变更流程（新增→记录原因→审批）
3. Coordinator 加载指定版本
4. 回滚策略

测试日期：2025-12-07
"""

import pytest

# =============================================================================
# 第一部分：版本数据结构测试
# =============================================================================


class TestPromptVersion:
    """测试 PromptVersion 数据结构"""

    def test_prompt_version_has_required_fields(self) -> None:
        """测试：PromptVersion 应该包含必需字段"""
        from src.domain.services.prompt_version_manager import PromptVersion

        version = PromptVersion(
            version="1.0.0",
            module_name="role_definition",
            template="你是一个{agent_name}",
            variables=["agent_name"],
            changelog="初始版本",
            author="system",
        )

        assert version.version == "1.0.0"
        assert version.module_name == "role_definition"
        assert version.changelog == "初始版本"
        assert version.author == "system"
        assert version.created_at is not None

    def test_prompt_version_validates_semantic_version(self) -> None:
        """测试：版本号应该符合语义化版本规范"""
        from src.domain.services.prompt_version_manager import PromptVersion

        # 有效版本
        valid_version = PromptVersion(
            version="1.2.3",
            module_name="test",
            template="test",
            variables=[],
            changelog="test",
            author="test",
        )
        assert valid_version.is_valid_version() is True

        # 无效版本
        invalid_version = PromptVersion(
            version="1.2",  # 缺少 patch
            module_name="test",
            template="test",
            variables=[],
            changelog="test",
            author="test",
        )
        assert invalid_version.is_valid_version() is False

    def test_prompt_version_comparison(self) -> None:
        """测试：版本应该支持比较"""
        from src.domain.services.prompt_version_manager import PromptVersion

        v1 = PromptVersion(
            version="1.0.0",
            module_name="test",
            template="test",
            variables=[],
            changelog="test",
            author="test",
        )
        v2 = PromptVersion(
            version="1.1.0",
            module_name="test",
            template="test",
            variables=[],
            changelog="test",
            author="test",
        )
        v3 = PromptVersion(
            version="2.0.0",
            module_name="test",
            template="test",
            variables=[],
            changelog="test",
            author="test",
        )

        assert v1 < v2
        assert v2 < v3
        assert v1 < v3


# =============================================================================
# 第二部分：变更记录测试
# =============================================================================


class TestVersionChangeRecord:
    """测试版本变更记录"""

    def test_change_record_has_required_fields(self) -> None:
        """测试：变更记录应该包含必需字段"""
        from src.domain.services.prompt_version_manager import VersionChangeRecord

        record = VersionChangeRecord(
            from_version="1.0.0",
            to_version="1.1.0",
            module_name="role_definition",
            change_type="minor",
            reason="添加新变量支持",
            author="developer",
        )

        assert record.from_version == "1.0.0"
        assert record.to_version == "1.1.0"
        assert record.change_type == "minor"
        assert record.reason == "添加新变量支持"
        assert record.status == "pending"  # 默认待审批

    def test_change_record_types(self) -> None:
        """测试：变更类型应该符合规范"""
        from src.domain.services.prompt_version_manager import VersionChangeRecord

        # major: 不兼容变更
        major_change = VersionChangeRecord(
            from_version="1.0.0",
            to_version="2.0.0",
            module_name="test",
            change_type="major",
            reason="重构模板结构",
            author="developer",
        )
        assert major_change.change_type == "major"

        # minor: 新功能
        minor_change = VersionChangeRecord(
            from_version="1.0.0",
            to_version="1.1.0",
            module_name="test",
            change_type="minor",
            reason="添加新变量",
            author="developer",
        )
        assert minor_change.change_type == "minor"

        # patch: 修复
        patch_change = VersionChangeRecord(
            from_version="1.0.0",
            to_version="1.0.1",
            module_name="test",
            change_type="patch",
            reason="修复格式问题",
            author="developer",
        )
        assert patch_change.change_type == "patch"


# =============================================================================
# 第三部分：审批流程测试
# =============================================================================


class TestVersionApprovalWorkflow:
    """测试版本审批流程"""

    def test_submit_version_for_approval(self) -> None:
        """测试：提交版本变更应该进入待审批状态"""
        from src.domain.services.prompt_version_manager import (
            PromptVersionManager,
        )

        manager = PromptVersionManager()

        # 提交变更
        record = manager.submit_change(
            module_name="role_definition",
            new_version="1.1.0",
            template="新模板内容{agent_name}",
            variables=["agent_name"],
            reason="优化提示词表达",
            author="developer",
        )

        assert record.status == "pending"
        assert record.to_version == "1.1.0"

    def test_approve_version_change(self) -> None:
        """测试：审批通过应该激活新版本"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        # 提交变更
        record = manager.submit_change(
            module_name="role_definition",
            new_version="1.1.0",
            template="新模板{agent_name}",
            variables=["agent_name"],
            reason="优化",
            author="developer",
        )

        # 审批通过
        result = manager.approve_change(
            record_id=record.id,
            approver="coordinator",
            comment="审批通过",
        )

        assert result.status == "approved"
        assert result.approver == "coordinator"
        assert result.approved_at is not None

    def test_reject_version_change(self) -> None:
        """测试：审批拒绝应该记录原因"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        # 提交变更
        record = manager.submit_change(
            module_name="role_definition",
            new_version="1.1.0",
            template="新模板{agent_name}",
            variables=["agent_name"],
            reason="优化",
            author="developer",
        )

        # 审批拒绝
        result = manager.reject_change(
            record_id=record.id,
            approver="coordinator",
            reason="变更不符合规范",
        )

        assert result.status == "rejected"
        assert "不符合规范" in result.rejection_reason

    def test_only_coordinator_can_approve(self) -> None:
        """测试：只有 Coordinator 角色才能审批"""
        from src.domain.services.prompt_version_manager import (
            ApprovalError,
            PromptVersionManager,
        )

        manager = PromptVersionManager()

        record = manager.submit_change(
            module_name="role_definition",
            new_version="1.1.0",
            template="新模板{agent_name}",
            variables=["agent_name"],
            reason="优化",
            author="developer",
        )

        # 非 coordinator 尝试审批应该失败
        with pytest.raises(ApprovalError):
            manager.approve_change(
                record_id=record.id,
                approver="developer",  # 不是 coordinator
                comment="尝试审批",
            )


# =============================================================================
# 第四部分：版本管理器测试
# =============================================================================


class TestPromptVersionManager:
    """测试 PromptVersionManager"""

    def test_register_initial_version(self) -> None:
        """测试：注册初始版本"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        version = manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="你是一个{agent_name}",
            variables=["agent_name"],
            changelog="初始版本",
            author="system",
        )

        assert version.version == "1.0.0"
        assert manager.get_current_version("role_definition") == "1.0.0"

    def test_get_version_history(self) -> None:
        """测试：获取版本历史"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        # 注册多个版本
        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始版本",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1",
            variables=[],
            changelog="添加功能",
            author="system",
        )

        history = manager.get_version_history("role_definition")
        assert len(history) == 2
        assert history[0].version == "1.0.0"
        assert history[1].version == "1.1.0"

    def test_get_specific_version(self) -> None:
        """测试：获取指定版本"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1 template",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1 template",
            variables=[],
            changelog="更新",
            author="system",
        )

        v1 = manager.get_version("role_definition", "1.0.0")
        v1_1 = manager.get_version("role_definition", "1.1.0")

        assert v1.template == "v1 template"
        assert v1_1.template == "v1.1 template"

    def test_set_active_version(self) -> None:
        """测试：设置活跃版本"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1",
            variables=[],
            changelog="更新",
            author="system",
        )

        # 设置 1.0.0 为活跃版本
        manager.set_active_version("role_definition", "1.0.0")
        assert manager.get_active_version("role_definition").version == "1.0.0"

        # 切换到 1.1.0
        manager.set_active_version("role_definition", "1.1.0")
        assert manager.get_active_version("role_definition").version == "1.1.0"


# =============================================================================
# 第五部分：回滚策略测试
# =============================================================================


class TestVersionRollback:
    """测试版本回滚"""

    def test_rollback_to_previous_version(self) -> None:
        """测试：回滚到上一个版本"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1",
            variables=[],
            changelog="更新",
            author="system",
        )

        # 设置 1.1.0 为活跃版本
        manager.set_active_version("role_definition", "1.1.0")
        assert manager.get_active_version("role_definition").version == "1.1.0"

        # 回滚
        rollback_result = manager.rollback("role_definition", reason="发现问题")

        assert rollback_result.success is True
        assert rollback_result.from_version == "1.1.0"
        assert rollback_result.to_version == "1.0.0"
        assert manager.get_active_version("role_definition").version == "1.0.0"

    def test_rollback_to_specific_version(self) -> None:
        """测试：回滚到指定版本"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1",
            variables=[],
            changelog="更新1",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.2.0",
            template="v1.2",
            variables=[],
            changelog="更新2",
            author="system",
        )

        manager.set_active_version("role_definition", "1.2.0")

        # 回滚到 1.0.0
        rollback_result = manager.rollback(
            "role_definition",
            target_version="1.0.0",
            reason="需要稳定版本",
        )

        assert rollback_result.success is True
        assert rollback_result.to_version == "1.0.0"
        assert manager.get_active_version("role_definition").version == "1.0.0"

    def test_rollback_records_history(self) -> None:
        """测试：回滚应该记录历史"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1",
            variables=[],
            changelog="更新",
            author="system",
        )

        manager.set_active_version("role_definition", "1.1.0")
        manager.rollback("role_definition", reason="测试回滚")

        # 检查回滚历史
        rollback_history = manager.get_rollback_history("role_definition")
        assert len(rollback_history) == 1
        assert rollback_history[0].reason == "测试回滚"


# =============================================================================
# 第六部分：Coordinator 集成测试
# =============================================================================


class TestCoordinatorPromptVersionIntegration:
    """测试 Coordinator 与版本管理的集成"""

    def test_coordinator_loads_specific_version(self) -> None:
        """测试：Coordinator 应该能加载指定版本"""
        from src.domain.services.prompt_version_manager import (
            CoordinatorPromptLoader,
            PromptVersionManager,
        )

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="你是一个{agent_name}（v1）",
            variables=["agent_name"],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="你是一个{agent_name}（v1.1）",
            variables=["agent_name"],
            changelog="更新",
            author="system",
        )

        loader = CoordinatorPromptLoader(manager)

        # 加载特定版本
        template = loader.load_template(
            module_name="role_definition",
            version="1.0.0",
        )

        assert "v1" in template
        assert "v1.1" not in template

    def test_coordinator_logs_version_loading(self) -> None:
        """测试：Coordinator 应该记录版本加载日志"""
        from src.domain.services.prompt_version_manager import (
            CoordinatorPromptLoader,
            PromptVersionManager,
        )

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="test",
            variables=[],
            changelog="初始",
            author="system",
        )

        loader = CoordinatorPromptLoader(manager)
        loader.load_template("role_definition", "1.0.0")

        # 检查日志
        logs = loader.get_loading_logs()
        assert len(logs) >= 1
        assert logs[-1].module_name == "role_definition"
        assert logs[-1].version == "1.0.0"

    def test_coordinator_switches_version_at_runtime(self) -> None:
        """测试：Coordinator 应该能在运行时切换版本"""
        from src.domain.services.prompt_version_manager import (
            CoordinatorPromptLoader,
            PromptVersionManager,
        )

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1 template",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1 template",
            variables=[],
            changelog="更新",
            author="system",
        )

        loader = CoordinatorPromptLoader(manager)

        # 加载 v1.0.0
        t1 = loader.load_template("role_definition", "1.0.0")
        assert "v1 template" in t1

        # 切换到 v1.1.0
        t2 = loader.load_template("role_definition", "1.1.0")
        assert "v1.1 template" in t2

    def test_coordinator_uses_active_version_by_default(self) -> None:
        """测试：Coordinator 默认使用活跃版本"""
        from src.domain.services.prompt_version_manager import (
            CoordinatorPromptLoader,
            PromptVersionManager,
        )

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1",
            variables=[],
            changelog="更新",
            author="system",
        )

        manager.set_active_version("role_definition", "1.1.0")

        loader = CoordinatorPromptLoader(manager)

        # 不指定版本，应该使用活跃版本
        template = loader.load_template("role_definition")
        assert "v1.1" in template


# =============================================================================
# 第七部分：配置驱动测试
# =============================================================================


class TestConfigDrivenVersionControl:
    """测试配置驱动的版本控制"""

    def test_load_version_config_from_dict(self) -> None:
        """测试：从配置字典加载版本配置"""
        from src.domain.services.prompt_version_manager import (
            VersionConfig,
        )

        config = VersionConfig.from_dict(
            {
                "role_definition": "1.0.0",
                "behavior_guidelines": "1.1.0",
                "tool_usage": "latest",
                "output_format": "1.0.0",
            }
        )

        assert config.get_version("role_definition") == "1.0.0"
        assert config.get_version("behavior_guidelines") == "1.1.0"
        assert config.get_version("tool_usage") == "latest"

    def test_coordinator_applies_version_config(self) -> None:
        """测试：Coordinator 应用版本配置"""
        from src.domain.services.prompt_version_manager import (
            CoordinatorPromptLoader,
            PromptVersionManager,
            VersionConfig,
        )

        manager = PromptVersionManager()

        # 注册多个模块的多个版本
        for module in ["role_definition", "behavior_guidelines"]:
            manager.register_version(
                module_name=module,
                version="1.0.0",
                template=f"{module} v1",
                variables=[],
                changelog="初始",
                author="system",
            )
            manager.register_version(
                module_name=module,
                version="1.1.0",
                template=f"{module} v1.1",
                variables=[],
                changelog="更新",
                author="system",
            )

        # 配置指定版本
        config = VersionConfig.from_dict(
            {
                "role_definition": "1.0.0",
                "behavior_guidelines": "1.1.0",
            }
        )

        loader = CoordinatorPromptLoader(manager)
        loader.apply_config(config)

        # 验证配置生效
        t1 = loader.load_template("role_definition")
        t2 = loader.load_template("behavior_guidelines")

        assert "v1" in t1 and "v1.1" not in t1
        assert "v1.1" in t2


# =============================================================================
# 第八部分：审计日志测试
# =============================================================================


class TestVersionAuditLog:
    """测试版本审计日志"""

    def test_version_change_logged(self) -> None:
        """测试：版本变更应该被记录"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )

        audit_logs = manager.get_audit_logs("role_definition")
        assert len(audit_logs) >= 1
        assert audit_logs[-1].action == "register"
        assert audit_logs[-1].version == "1.0.0"

    def test_version_activation_logged(self) -> None:
        """测试：版本激活应该被记录"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1",
            variables=[],
            changelog="更新",
            author="system",
        )

        manager.set_active_version("role_definition", "1.1.0")

        audit_logs = manager.get_audit_logs("role_definition")
        activation_log = [log for log in audit_logs if log.action == "activate"]
        assert len(activation_log) >= 1
        assert activation_log[-1].version == "1.1.0"

    def test_rollback_logged(self) -> None:
        """测试：回滚应该被记录"""
        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )
        manager.register_version(
            module_name="role_definition",
            version="1.1.0",
            template="v1.1",
            variables=[],
            changelog="更新",
            author="system",
        )

        manager.set_active_version("role_definition", "1.1.0")
        manager.rollback("role_definition", reason="测试")

        audit_logs = manager.get_audit_logs("role_definition")
        rollback_log = [log for log in audit_logs if log.action == "rollback"]
        assert len(rollback_log) >= 1


# =============================================================================
# 第九部分：并发安全测试
# =============================================================================


class TestConcurrencySafety:
    """测试并发安全性"""

    def test_concurrent_version_access(self) -> None:
        """测试：并发访问版本应该安全"""
        import threading

        from src.domain.services.prompt_version_manager import PromptVersionManager

        manager = PromptVersionManager()

        manager.register_version(
            module_name="role_definition",
            version="1.0.0",
            template="v1",
            variables=[],
            changelog="初始",
            author="system",
        )

        results = []
        errors = []

        def access_version() -> None:
            try:
                for _ in range(100):
                    v = manager.get_version("role_definition", "1.0.0")
                    results.append(v.version)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=access_version) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(r == "1.0.0" for r in results)
