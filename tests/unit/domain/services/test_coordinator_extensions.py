"""测试：Coordinator 扩展模块

测试目标：
1. KnowledgeManager - 知识库 CRUD 操作
2. UnifiedLogCollector - 统一日志聚合
3. DynamicAlertRuleManager - 动态告警规则配置

TDD Red 阶段：定义所有测试用例
"""

from datetime import datetime, timedelta

import pytest

# ==================== 模块1：KnowledgeManager 测试 ====================


class TestKnowledgeManagerInit:
    """测试 KnowledgeManager 初始化"""

    def test_knowledge_manager_exists(self):
        """KnowledgeManager 类应存在"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        assert KnowledgeManager is not None

    def test_knowledge_manager_has_storage(self):
        """KnowledgeManager 应有存储"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()
        assert hasattr(manager, "entries")
        assert isinstance(manager.entries, dict)


class TestKnowledgeCreate:
    """测试知识条目创建"""

    def test_create_knowledge_entry(self):
        """可以创建知识条目"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        entry_id = manager.create(
            title="Python 异常处理",
            content="使用 try-except 块来捕获异常...",
            category="programming",
            tags=["python", "exception"],
        )

        assert entry_id is not None
        assert len(entry_id) > 0

    def test_created_entry_can_be_retrieved(self):
        """创建的条目可以被检索"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        entry_id = manager.create(
            title="Git 分支策略",
            content="主分支保持稳定，功能分支用于开发...",
            category="devops",
        )

        entry = manager.get(entry_id)

        assert entry is not None
        assert entry["title"] == "Git 分支策略"
        assert entry["category"] == "devops"

    def test_create_with_metadata(self):
        """创建时可以附加元数据"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        entry_id = manager.create(
            title="API 设计原则",
            content="RESTful API 应遵循...",
            category="architecture",
            metadata={"author": "system", "version": "1.0"},
        )

        entry = manager.get(entry_id)
        assert entry["metadata"]["author"] == "system"


class TestKnowledgeRead:
    """测试知识条目读取"""

    def test_get_nonexistent_entry_returns_none(self):
        """获取不存在的条目返回 None"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()
        entry = manager.get("nonexistent_id")

        assert entry is None

    def test_list_all_entries(self):
        """可以列出所有条目"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        manager.create(title="Entry 1", content="Content 1", category="cat1")
        manager.create(title="Entry 2", content="Content 2", category="cat2")

        entries = manager.list_all()

        assert len(entries) == 2

    def test_filter_by_category(self):
        """可以按类别过滤"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        manager.create(title="Python", content="...", category="programming")
        manager.create(title="Docker", content="...", category="devops")
        manager.create(title="Java", content="...", category="programming")

        entries = manager.filter_by_category("programming")

        assert len(entries) == 2

    def test_search_by_keyword(self):
        """可以按关键词搜索"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        manager.create(title="异常处理", content="Python 异常处理最佳实践", category="python")
        manager.create(title="日志记录", content="使用 logging 模块", category="python")

        results = manager.search("异常")

        assert len(results) >= 1
        assert any("异常" in r["title"] or "异常" in r["content"] for r in results)


class TestKnowledgeUpdate:
    """测试知识条目更新"""

    def test_update_entry_content(self):
        """可以更新条目内容"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        entry_id = manager.create(
            title="原标题",
            content="原内容",
            category="test",
        )

        success = manager.update(
            entry_id,
            title="新标题",
            content="新内容",
        )

        assert success is True

        entry = manager.get(entry_id)
        assert entry["title"] == "新标题"
        assert entry["content"] == "新内容"

    def test_update_nonexistent_returns_false(self):
        """更新不存在的条目返回 False"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()
        success = manager.update("nonexistent", title="New")

        assert success is False

    def test_update_preserves_unmodified_fields(self):
        """更新时保留未修改的字段"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        entry_id = manager.create(
            title="标题",
            content="内容",
            category="分类",
            tags=["tag1", "tag2"],
        )

        manager.update(entry_id, title="新标题")

        entry = manager.get(entry_id)
        assert entry["title"] == "新标题"
        assert entry["content"] == "内容"  # 未修改
        assert entry["category"] == "分类"  # 未修改


class TestKnowledgeDelete:
    """测试知识条目删除"""

    def test_delete_entry(self):
        """可以删除条目"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()

        entry_id = manager.create(title="To Delete", content="...", category="test")

        success = manager.delete(entry_id)

        assert success is True
        assert manager.get(entry_id) is None

    def test_delete_nonexistent_returns_false(self):
        """删除不存在的条目返回 False"""
        from src.domain.services.knowledge_manager import KnowledgeManager

        manager = KnowledgeManager()
        success = manager.delete("nonexistent")

        assert success is False


class TestKnowledgeManagerIntegration:
    """测试 KnowledgeManager 与 Coordinator 集成"""

    def test_coordinator_has_knowledge_manager(self):
        """Coordinator 应有 KnowledgeManager"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "knowledge_manager")

    def test_coordinator_crud_operations(self):
        """Coordinator 可以执行 CRUD 操作"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # Create
        entry_id = coordinator.create_knowledge(
            title="测试条目",
            content="测试内容",
            category="test",
        )
        assert entry_id is not None

        # Read
        entry = coordinator.get_knowledge(entry_id)
        assert entry["title"] == "测试条目"

        # Update
        coordinator.update_knowledge(entry_id, content="更新后的内容")
        entry = coordinator.get_knowledge(entry_id)
        assert entry["content"] == "更新后的内容"

        # Delete
        success = coordinator.delete_knowledge(entry_id)
        assert success is True


# ==================== 模块2：UnifiedLogCollector 测试 ====================


class TestUnifiedLogCollectorInit:
    """测试 UnifiedLogCollector 初始化"""

    def test_log_collector_exists(self):
        """UnifiedLogCollector 类应存在"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        assert UnifiedLogCollector is not None

    def test_log_collector_has_logs_storage(self):
        """LogCollector 应有日志存储"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()
        assert hasattr(collector, "logs")
        assert isinstance(collector.logs, list)


class TestLogCollection:
    """测试日志收集"""

    def test_collect_log_entry(self):
        """可以收集日志条目"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.log(
            level="INFO",
            source="CoordinatorAgent",
            message="决策验证通过",
            context={"decision_id": "dec_001"},
        )

        assert len(collector.logs) == 1

    def test_log_has_timestamp(self):
        """日志应有时间戳"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.log(level="DEBUG", source="test", message="test message")

        log_entry = collector.logs[0]
        assert hasattr(log_entry, "timestamp")
        assert log_entry.timestamp is not None

    def test_log_levels(self):
        """支持多种日志级别"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.debug("test", "debug message")
        collector.info("test", "info message")
        collector.warning("test", "warning message")
        collector.error("test", "error message")

        assert len(collector.logs) == 4
        assert collector.logs[0].level == "DEBUG"
        assert collector.logs[1].level == "INFO"
        assert collector.logs[2].level == "WARNING"
        assert collector.logs[3].level == "ERROR"


class TestLogQuerying:
    """测试日志查询"""

    def test_filter_by_level(self):
        """可以按级别过滤"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.info("src1", "info 1")
        collector.error("src2", "error 1")
        collector.info("src3", "info 2")

        errors = collector.filter_by_level("ERROR")

        assert len(errors) == 1
        assert errors[0]["message"] == "error 1"

    def test_filter_by_source(self):
        """可以按来源过滤"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.info("CoordinatorAgent", "msg 1")
        collector.info("WorkflowAgent", "msg 2")
        collector.info("CoordinatorAgent", "msg 3")

        logs = collector.filter_by_source("CoordinatorAgent")

        assert len(logs) == 2

    def test_filter_by_time_range(self):
        """可以按时间范围过滤"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        # 添加日志
        collector.info("test", "message 1")
        collector.info("test", "message 2")

        # 查询最近1小时的日志
        since = datetime.now() - timedelta(hours=1)
        logs = collector.filter_by_time_range(since=since)

        assert len(logs) == 2

    def test_get_recent_logs(self):
        """可以获取最近N条日志"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        for i in range(10):
            collector.info("test", f"message {i}")

        recent = collector.get_recent(5)

        assert len(recent) == 5


class TestLogAggregation:
    """测试日志聚合"""

    def test_aggregate_by_source(self):
        """可以按来源聚合统计"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.info("CoordinatorAgent", "msg 1")
        collector.info("CoordinatorAgent", "msg 2")
        collector.info("WorkflowAgent", "msg 3")

        stats = collector.aggregate_by_source()

        assert stats["CoordinatorAgent"] == 2
        assert stats["WorkflowAgent"] == 1

    def test_aggregate_by_level(self):
        """可以按级别聚合统计"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.info("src", "msg")
        collector.info("src", "msg")
        collector.error("src", "msg")
        collector.warning("src", "msg")

        stats = collector.aggregate_by_level()

        assert stats["INFO"] == 2
        assert stats["ERROR"] == 1
        assert stats["WARNING"] == 1


class TestLogExport:
    """测试日志导出"""

    def test_export_to_json(self):
        """可以导出为 JSON"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.info("test", "test message")

        json_str = collector.export_json()

        assert json_str is not None
        assert "test message" in json_str

    def test_clear_logs(self):
        """可以清空日志"""
        from src.domain.services.unified_log_collector import UnifiedLogCollector

        collector = UnifiedLogCollector()

        collector.info("test", "msg 1")
        collector.info("test", "msg 2")

        collector.clear()

        assert len(collector.logs) == 0


class TestUnifiedLogIntegration:
    """测试 UnifiedLogCollector 与 Coordinator 集成"""

    def test_coordinator_has_log_collector(self):
        """Coordinator 应有 LogCollector"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "log_collector")

    def test_coordinator_logs_decision_validation(self):
        """Coordinator 验证决策时应记录日志"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 执行一次验证
        coordinator.validate_decision({"action_type": "test"})

        # 应有日志记录
        logs = coordinator.log_collector.filter_by_source("CoordinatorAgent")
        assert len(logs) >= 1


# ==================== 模块3：DynamicAlertRuleManager 测试 ====================


class TestAlertRuleManagerInit:
    """测试 DynamicAlertRuleManager 初始化"""

    def test_alert_rule_manager_exists(self):
        """DynamicAlertRuleManager 类应存在"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        assert DynamicAlertRuleManager is not None

    def test_alert_rule_manager_has_rules_storage(self):
        """AlertRuleManager 应有规则存储"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()
        assert hasattr(manager, "rules")
        assert isinstance(manager.rules, dict)


class TestAlertRuleCreation:
    """测试告警规则创建"""

    def test_create_threshold_rule(self):
        """可以创建阈值规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        rule_id = manager.create_rule(
            name="高拒绝率告警",
            rule_type="threshold",
            metric="rejection_rate",
            threshold=0.5,
            comparison=">=",
            severity="warning",
        )

        assert rule_id is not None

    def test_create_pattern_rule(self):
        """可以创建模式规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        rule_id = manager.create_rule(
            name="连续失败告警",
            rule_type="pattern",
            pattern="consecutive_failures",
            count=3,
            severity="critical",
        )

        assert rule_id is not None

    def test_create_rate_rule(self):
        """可以创建速率规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        rule_id = manager.create_rule(
            name="错误率激增告警",
            rule_type="rate",
            metric="error_count",
            rate_threshold=10,  # 每分钟超过10个
            time_window_minutes=1,
            severity="warning",
        )

        assert rule_id is not None


class TestAlertRuleManagement:
    """测试告警规则管理"""

    def test_get_rule(self):
        """可以获取规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        rule_id = manager.create_rule(
            name="Test Rule",
            rule_type="threshold",
            metric="test",
            threshold=1.0,
            severity="info",
        )

        rule = manager.get_rule(rule_id)

        assert rule is not None
        assert rule["name"] == "Test Rule"

    def test_list_all_rules(self):
        """可以列出所有规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        manager.create_rule(
            name="Rule 1", rule_type="threshold", metric="m1", threshold=1, severity="info"
        )
        manager.create_rule(
            name="Rule 2", rule_type="threshold", metric="m2", threshold=2, severity="info"
        )

        rules = manager.list_rules()

        assert len(rules) == 2

    def test_update_rule(self):
        """可以更新规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        rule_id = manager.create_rule(
            name="Original",
            rule_type="threshold",
            metric="test",
            threshold=0.5,
            severity="info",
        )

        success = manager.update_rule(rule_id, threshold=0.8, severity="warning")

        assert success is True

        rule = manager.get_rule(rule_id)
        assert rule["threshold"] == 0.8
        assert rule["severity"] == "warning"

    def test_delete_rule(self):
        """可以删除规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        rule_id = manager.create_rule(
            name="To Delete",
            rule_type="threshold",
            metric="test",
            threshold=1,
            severity="info",
        )

        success = manager.delete_rule(rule_id)

        assert success is True
        assert manager.get_rule(rule_id) is None

    def test_enable_disable_rule(self):
        """可以启用/禁用规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        rule_id = manager.create_rule(
            name="Toggleable",
            rule_type="threshold",
            metric="test",
            threshold=1,
            severity="info",
        )

        # 默认启用
        rule = manager.get_rule(rule_id)
        assert rule["enabled"] is True

        # 禁用
        manager.disable_rule(rule_id)
        rule = manager.get_rule(rule_id)
        assert rule["enabled"] is False

        # 重新启用
        manager.enable_rule(rule_id)
        rule = manager.get_rule(rule_id)
        assert rule["enabled"] is True


class TestAlertEvaluation:
    """测试告警规则评估"""

    def test_evaluate_threshold_rule_triggered(self):
        """阈值规则应正确触发"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        manager.create_rule(
            name="High Rejection",
            rule_type="threshold",
            metric="rejection_rate",
            threshold=0.5,
            comparison=">=",
            severity="warning",
        )

        # 评估指标
        alerts = manager.evaluate({"rejection_rate": 0.6})

        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"

    def test_evaluate_threshold_rule_not_triggered(self):
        """阈值未达到时不应触发"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        manager.create_rule(
            name="High Rejection",
            rule_type="threshold",
            metric="rejection_rate",
            threshold=0.5,
            comparison=">=",
            severity="warning",
        )

        alerts = manager.evaluate({"rejection_rate": 0.3})

        assert len(alerts) == 0

    def test_evaluate_disabled_rule_skipped(self):
        """禁用的规则应被跳过"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        rule_id = manager.create_rule(
            name="Disabled Rule",
            rule_type="threshold",
            metric="test",
            threshold=0.1,
            comparison=">=",
            severity="warning",
        )

        manager.disable_rule(rule_id)

        alerts = manager.evaluate({"test": 0.9})

        assert len(alerts) == 0

    def test_evaluate_multiple_rules(self):
        """可以同时评估多个规则"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        manager.create_rule(
            name="Rule 1",
            rule_type="threshold",
            metric="metric_a",
            threshold=0.5,
            comparison=">=",
            severity="warning",
        )

        manager.create_rule(
            name="Rule 2",
            rule_type="threshold",
            metric="metric_b",
            threshold=100,
            comparison=">",
            severity="critical",
        )

        alerts = manager.evaluate({"metric_a": 0.8, "metric_b": 150})

        assert len(alerts) == 2


class TestAlertHistory:
    """测试告警历史"""

    def test_alerts_are_recorded(self):
        """触发的告警应被记录"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        manager.create_rule(
            name="Test Rule",
            rule_type="threshold",
            metric="test",
            threshold=0.5,
            comparison=">=",
            severity="warning",
        )

        manager.evaluate({"test": 0.8})

        history = manager.get_alert_history()

        assert len(history) == 1

    def test_get_alerts_by_severity(self):
        """可以按严重性查询告警历史"""
        from src.domain.services.dynamic_alert_rule_manager import (
            DynamicAlertRuleManager,
        )

        manager = DynamicAlertRuleManager()

        manager.create_rule(
            name="Warning Rule",
            rule_type="threshold",
            metric="m1",
            threshold=0.5,
            severity="warning",
        )
        manager.create_rule(
            name="Critical Rule",
            rule_type="threshold",
            metric="m2",
            threshold=0.5,
            severity="critical",
        )

        manager.evaluate({"m1": 0.8, "m2": 0.8})

        critical_alerts = manager.get_alerts_by_severity("critical")

        assert len(critical_alerts) == 1


class TestAlertRuleManagerIntegration:
    """测试 DynamicAlertRuleManager 与 Coordinator 集成"""

    def test_coordinator_has_alert_rule_manager(self):
        """Coordinator 应有 AlertRuleManager"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "alert_rule_manager")

    def test_coordinator_can_add_alert_rule(self):
        """Coordinator 可以添加告警规则"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        rule_id = coordinator.add_alert_rule(
            name="Test Alert",
            rule_type="threshold",
            metric="rejection_rate",
            threshold=0.5,
            severity="warning",
        )

        assert rule_id is not None

    def test_coordinator_evaluates_alerts_on_statistics(self):
        """Coordinator 获取统计时应评估告警"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 添加告警规则
        coordinator.add_alert_rule(
            name="High Rejection Rate",
            rule_type="threshold",
            metric="rejection_rate",
            threshold=0.3,
            comparison=">=",
            severity="warning",
        )

        # 触发一些拒绝
        for _ in range(5):
            coordinator._statistics["total"] += 1
            coordinator._statistics["rejected"] += 1

        # 获取带告警的统计
        status = coordinator.get_system_status_with_alerts()

        assert "alerts" in status
        assert len(status["alerts"]) >= 1


# ==================== 端到端集成测试 ====================


class TestFullIntegration:
    """端到端集成测试"""

    @pytest.mark.asyncio
    async def test_coordinator_full_workflow_with_extensions(self):
        """完整工作流测试（知识库+日志+告警）"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 1. 添加知识条目
        knowledge_id = coordinator.create_knowledge(
            title="验证规则说明",
            content="所有决策必须通过验证...",
            category="rules",
        )
        assert knowledge_id is not None

        # 2. 添加告警规则
        alert_rule_id = coordinator.add_alert_rule(
            name="高拒绝率",
            rule_type="threshold",
            metric="rejection_rate",
            threshold=0.3,
            severity="warning",
        )
        assert alert_rule_id is not None

        # 3. 执行一些操作（触发日志）
        coordinator.validate_decision({"action_type": "test_action"})

        # 4. 检查日志
        logs = coordinator.log_collector.filter_by_source("CoordinatorAgent")
        assert len(logs) >= 1

        # 5. 检查统计和告警
        status = coordinator.get_system_status_with_alerts()
        assert "total_workflows" in status
        assert "alerts" in status

    def test_knowledge_search_for_error_handling(self):
        """测试：根据错误搜索知识库"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 添加错误处理知识
        coordinator.create_knowledge(
            title="TypeError 处理",
            content="当遇到 TypeError 时，检查参数类型是否正确...",
            category="error_handling",
            tags=["python", "error", "TypeError"],
        )

        coordinator.create_knowledge(
            title="ValueError 处理",
            content="当遇到 ValueError 时，检查参数值是否在有效范围...",
            category="error_handling",
            tags=["python", "error", "ValueError"],
        )

        # 搜索相关知识
        results = coordinator.search_knowledge("TypeError")

        assert len(results) >= 1
        assert any("TypeError" in r["title"] or "TypeError" in r["content"] for r in results)
