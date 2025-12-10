"""PromptVersionFacade Unit Tests

测试提示词版本管理门面类（从 CoordinatorAgent 拆分）。

TDD: 先写测试，再实现功能。
"""

from unittest.mock import MagicMock

import pytest


class TestPromptVersionFacadeInit:
    """测试 Facade 初始化"""

    def test_facade_creates_with_default_config(self):
        """Facade 可以使用默认配置创建"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        assert facade is not None
        assert facade.is_initialized is False

    def test_facade_creates_with_custom_config(self):
        """Facade 可以使用自定义配置创建"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        config = {"module_a": "1.0.0", "module_b": "2.0.0"}
        facade = PromptVersionFacade(config=config)
        assert facade is not None

    def test_facade_accepts_log_collector(self):
        """Facade 接受可选的 log_collector"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        log_collector = MagicMock()
        facade = PromptVersionFacade(log_collector=log_collector)
        assert facade._log_collector is log_collector


class TestPromptVersionFacadeInitialization:
    """测试延迟初始化"""

    def test_initialize_creates_manager_and_loader(self):
        """initialize() 创建 PromptVersionManager 和 CoordinatorPromptLoader"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        facade.initialize()

        assert facade.is_initialized is True
        assert facade.prompt_version_manager is not None

    def test_initialize_with_config_applies_config(self):
        """带配置初始化会应用版本配置"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        config = {"test_module": "1.0.0"}
        facade = PromptVersionFacade(config=config)
        facade.initialize()

        assert facade.is_initialized is True

    def test_initialize_is_idempotent(self):
        """重复调用 initialize() 是幂等的"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        facade.initialize()
        manager1 = facade.prompt_version_manager

        facade.initialize()  # 再次调用
        manager2 = facade.prompt_version_manager

        assert manager1 is manager2  # 同一个实例


class TestPromptVersionFacadeRegistration:
    """测试版本注册功能"""

    @pytest.fixture
    def initialized_facade(self):
        """创建已初始化的 Facade"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        facade.initialize()
        return facade

    def test_register_prompt_version(self, initialized_facade):
        """注册新的提示词版本"""
        result = initialized_facade.register_prompt_version(
            module_name="test_module",
            version="1.0.0",
            template="Hello {{ name }}",
            variables=["name"],
            changelog="Initial version",
            author="test_author",
        )

        assert result is not None
        assert result.version == "1.0.0"
        assert result.module_name == "test_module"

    def test_register_auto_initializes(self):
        """未初始化时注册会自动初始化"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        assert facade.is_initialized is False

        result = facade.register_prompt_version(
            module_name="test_module",
            version="1.0.0",
            template="Test",
            variables=[],
            changelog="Test",
        )

        assert facade.is_initialized is True
        assert result is not None


class TestPromptVersionFacadeLoading:
    """测试模板加载功能"""

    @pytest.fixture
    def facade_with_version(self):
        """创建带有注册版本的 Facade"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        facade.initialize()
        facade.register_prompt_version(
            module_name="greeting",
            version="1.0.0",
            template="Hello {{ name }}!",
            variables=["name"],
            changelog="Initial",
        )
        return facade

    def test_load_prompt_template(self, facade_with_version):
        """加载已注册的模板"""
        template = facade_with_version.load_prompt_template(
            module_name="greeting",
            version="1.0.0",
        )

        assert "Hello" in template
        assert "{{ name }}" in template

    def test_load_active_version_when_no_version_specified(self, facade_with_version):
        """不指定版本时加载活跃版本"""
        # 设置活跃版本
        facade_with_version.switch_prompt_version("greeting", "1.0.0")

        template = facade_with_version.load_prompt_template(
            module_name="greeting",
        )

        assert template is not None


class TestPromptVersionFacadeSwitching:
    """测试版本切换功能"""

    @pytest.fixture
    def facade_with_versions(self):
        """创建带有多个版本的 Facade"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        facade.initialize()
        facade.register_prompt_version(
            module_name="greeting",
            version="1.0.0",
            template="Hello {{ name }}!",
            variables=["name"],
            changelog="Initial",
        )
        facade.register_prompt_version(
            module_name="greeting",
            version="2.0.0",
            template="Hi {{ name }}!",
            variables=["name"],
            changelog="Updated greeting",
        )
        return facade

    def test_switch_prompt_version(self, facade_with_versions):
        """切换提示词版本"""
        facade_with_versions.switch_prompt_version("greeting", "2.0.0")

        # 验证切换成功（通过加载活跃版本）
        template = facade_with_versions.load_prompt_template("greeting")
        assert "Hi" in template


class TestPromptVersionFacadeRollback:
    """测试版本回滚功能"""

    @pytest.fixture
    def facade_with_versions(self):
        """创建带有多个版本的 Facade"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        facade.initialize()
        facade.register_prompt_version(
            module_name="greeting",
            version="1.0.0",
            template="Hello {{ name }}!",
            variables=["name"],
            changelog="Initial",
        )
        facade.register_prompt_version(
            module_name="greeting",
            version="2.0.0",
            template="Hi {{ name }}!",
            variables=["name"],
            changelog="Updated",
        )
        facade.switch_prompt_version("greeting", "2.0.0")
        return facade

    def test_rollback_prompt_version(self, facade_with_versions):
        """回滚到指定版本"""
        result = facade_with_versions.rollback_prompt_version(
            module_name="greeting",
            target_version="1.0.0",
            reason="Testing rollback",
        )

        assert result is not None
        assert result.success is True
        assert result.to_version == "1.0.0"

    def test_rollback_without_target_rolls_back_one_version(self, facade_with_versions):
        """不指定目标版本时回滚一个版本"""
        result = facade_with_versions.rollback_prompt_version(
            module_name="greeting",
            reason="Testing auto rollback",
        )

        assert result is not None


class TestPromptVersionFacadeAudit:
    """测试审计日志功能"""

    @pytest.fixture
    def facade_with_activity(self):
        """创建有活动记录的 Facade"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        facade.initialize()
        facade.register_prompt_version(
            module_name="test_module",
            version="1.0.0",
            template="Test",
            variables=[],
            changelog="Initial",
        )
        return facade

    def test_get_prompt_audit_logs(self, facade_with_activity):
        """获取审计日志"""
        logs = facade_with_activity.get_prompt_audit_logs("test_module")
        assert isinstance(logs, list)

    def test_get_prompt_version_history(self, facade_with_activity):
        """获取版本历史"""
        history = facade_with_activity.get_prompt_version_history("test_module")
        assert isinstance(history, list)

    def test_get_prompt_loading_logs(self, facade_with_activity):
        """获取加载日志"""
        logs = facade_with_activity.get_prompt_loading_logs()
        assert isinstance(logs, list)


class TestPromptVersionFacadeChangeManagement:
    """测试变更管理功能"""

    @pytest.fixture
    def initialized_facade(self):
        """创建已初始化的 Facade"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()
        facade.initialize()
        return facade

    def test_submit_prompt_change(self, initialized_facade):
        """提交变更申请"""
        # 先注册一个初始版本
        initialized_facade.register_prompt_version(
            module_name="test_module",
            version="1.0.0",
            template="Original",
            variables=[],
            changelog="Initial",
        )

        record = initialized_facade.submit_prompt_change(
            module_name="test_module",
            new_version="2.0.0",
            template="Updated",
            variables=[],
            reason="Testing change management",
            author="test_author",
        )

        assert record is not None
        assert record.id is not None

    def test_approve_prompt_change(self, initialized_facade):
        """审批通过变更"""
        # 先注册初始版本并提交变更
        initialized_facade.register_prompt_version(
            module_name="test_module",
            version="1.0.0",
            template="Original",
            variables=[],
            changelog="Initial",
        )
        record = initialized_facade.submit_prompt_change(
            module_name="test_module",
            new_version="2.0.0",
            template="Updated",
            variables=[],
            reason="Testing",
            author="test_author",
        )

        result = initialized_facade.approve_prompt_change(
            record_id=record.id,
            comment="Approved for testing",
        )

        assert result is not None

    def test_reject_prompt_change(self, initialized_facade):
        """拒绝变更"""
        # 先注册初始版本并提交变更
        initialized_facade.register_prompt_version(
            module_name="test_module",
            version="1.0.0",
            template="Original",
            variables=[],
            changelog="Initial",
        )
        record = initialized_facade.submit_prompt_change(
            module_name="test_module",
            new_version="2.0.0",
            template="Updated",
            variables=[],
            reason="Testing",
            author="test_author",
        )

        result = initialized_facade.reject_prompt_change(
            record_id=record.id,
            reason="Rejected for testing",
        )

        assert result is not None


class TestPromptVersionFacadeEdgeCases:
    """测试边界情况"""

    def test_operations_before_init_auto_initialize(self):
        """操作前未初始化会自动初始化"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()

        # 调用需要初始化的方法
        logs = facade.get_prompt_audit_logs("nonexistent")

        # 验证没有抛出异常
        assert isinstance(logs, list)

    def test_rollback_uninitialized_raises_error(self):
        """回滚未初始化的 Facade 抛出错误"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()

        with pytest.raises(ValueError, match="未初始化"):
            facade.rollback_prompt_version("test", reason="test")

    def test_approve_change_uninitialized_raises_error(self):
        """审批未初始化的 Facade 抛出错误"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()

        with pytest.raises(ValueError, match="未初始化"):
            facade.approve_prompt_change("fake_id")

    def test_reject_change_uninitialized_raises_error(self):
        """拒绝未初始化的 Facade 抛出错误"""
        from src.domain.services.prompt_version_facade import PromptVersionFacade

        facade = PromptVersionFacade()

        with pytest.raises(ValueError, match="未初始化"):
            facade.reject_prompt_change("fake_id", reason="test")
