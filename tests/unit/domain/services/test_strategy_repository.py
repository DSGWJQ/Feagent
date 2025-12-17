"""StrategyRepository 单元测试

Phase: P0-7 Coverage Improvement (40% → 85%+)
Coverage targets:
- register: uuid generation, field persistence, defaults
- get: retrieval + missing cases
- list_all: return all strategies
- find_by_condition: enabled filtering, priority sorting
- delete: existing/missing strategies
"""

from datetime import datetime

import pytest

from src.domain.services.supervision.strategy_repo import StrategyRepository


@pytest.fixture
def repo():
    """创建空策略库"""
    return StrategyRepository()


# ==================== TestInit ====================


class TestInit:
    """测试初始化"""

    def test_init_starts_empty(self, repo):
        """测试策略库初始化为空"""
        assert repo.strategies == {}
        assert repo.list_all() == []


# ==================== TestRegisterAndGet ====================


class TestRegisterAndGet:
    """测试注册和获取策略"""

    def test_register_returns_prefixed_strategy_id(self, repo):
        """测试注册返回带前缀的策略 ID"""
        strategy_id = repo.register(
            name="test_strategy",
            trigger_conditions=["bias"],
            action="warn",
        )

        # 验证 ID 格式：strategy_<12位hex>
        assert strategy_id.startswith("strategy_")
        hex_part = strategy_id[len("strategy_") :]
        assert len(hex_part) == 12
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_register_persists_fields_and_defaults(self, repo):
        """测试注册持久化所有字段并使用默认值"""
        strategy_id = repo.register(
            name="bias_strategy",
            trigger_conditions=["bias", "harmful"],
            action="block",
            priority=5,
            action_params={"severity": "high"},
        )

        strategy = repo.get(strategy_id)
        assert strategy is not None

        # 验证所有字段
        assert strategy["id"] == strategy_id
        assert strategy["name"] == "bias_strategy"
        assert strategy["trigger_conditions"] == ["bias", "harmful"]
        assert strategy["action"] == "block"
        assert strategy["priority"] == 5
        assert strategy["action_params"] == {"severity": "high"}
        assert strategy["enabled"] is True

        # 验证 created_at 可解析
        assert "created_at" in strategy
        datetime.fromisoformat(strategy["created_at"])

    def test_register_action_params_defaults_to_empty_dict(self, repo):
        """测试 action_params 默认为空字典"""
        strategy_id = repo.register(
            name="simple_strategy",
            trigger_conditions=["test"],
            action="log",
        )

        strategy = repo.get(strategy_id)
        assert strategy["action_params"] == {}

    def test_register_priority_defaults_to_10(self, repo):
        """测试 priority 默认为 10"""
        strategy_id = repo.register(
            name="default_priority",
            trigger_conditions=["test"],
            action="warn",
        )

        strategy = repo.get(strategy_id)
        assert strategy["priority"] == 10

    def test_get_returns_strategy_or_none(self, repo):
        """测试 get 返回策略或 None"""
        strategy_id = repo.register(
            name="test",
            trigger_conditions=["test"],
            action="warn",
        )

        # 存在的策略
        strategy = repo.get(strategy_id)
        assert strategy is not None
        assert strategy["id"] == strategy_id

        # 不存在的策略
        missing = repo.get("nonexistent_id")
        assert missing is None


# ==================== TestListAll ====================


class TestListAll:
    """测试列出所有策略"""

    def test_list_all_returns_all_strategies(self, repo):
        """测试 list_all 返回所有策略（不保证顺序）"""
        id1 = repo.register("strategy1", ["bias"], "warn")
        id2 = repo.register("strategy2", ["harmful"], "block")
        id3 = repo.register("strategy3", ["test"], "log")

        strategies = repo.list_all()
        assert len(strategies) == 3

        # 验证所有 ID 都在列表中
        ids = {s["id"] for s in strategies}
        assert ids == {id1, id2, id3}


# ==================== TestFindByCondition ====================


class TestFindByCondition:
    """测试按条件查找策略"""

    def test_find_by_condition_returns_only_enabled_and_matches_condition(self, repo):
        """测试 find_by_condition 仅返回启用且匹配的策略"""
        id1 = repo.register("enabled_match", ["bias"], "warn")
        id2 = repo.register("disabled_match", ["bias"], "block")
        id3 = repo.register("enabled_nomatch", ["harmful"], "log")

        # 禁用 id2
        repo.strategies[id2]["enabled"] = False

        matches = repo.find_by_condition("bias")

        # 应该只返回 id1（启用且匹配）
        assert len(matches) == 1
        assert matches[0]["id"] == id1

    def test_find_by_condition_sorts_by_priority_ascending(self, repo):
        """测试 find_by_condition 按优先级升序排序"""
        id1 = repo.register("p10", ["test"], "warn", priority=10)
        id2 = repo.register("p1", ["test"], "block", priority=1)
        id3 = repo.register("p5", ["test"], "log", priority=5)

        matches = repo.find_by_condition("test")

        # 验证返回顺序：priority 1, 5, 10
        priorities = [m["priority"] for m in matches]
        assert priorities == [1, 5, 10]

        # 验证 ID 对应
        ids = [m["id"] for m in matches]
        assert ids == [id2, id3, id1]

    def test_find_by_condition_empty_repo_returns_empty(self, repo):
        """测试空仓库时 find_by_condition 返回空列表"""
        matches = repo.find_by_condition("anything")
        assert matches == []

    def test_find_by_condition_no_match_returns_empty(self, repo):
        """测试没有匹配时返回空列表"""
        repo.register("test", ["bias"], "warn")

        matches = repo.find_by_condition("nonexistent_condition")
        assert matches == []


# ==================== TestDelete ====================


class TestDelete:
    """测试删除策略"""

    def test_delete_existing_returns_true_and_removes(self, repo):
        """测试删除存在的策略返回 True 并移除"""
        strategy_id = repo.register("test", ["test"], "warn")

        result = repo.delete(strategy_id)

        assert result is True
        assert repo.get(strategy_id) is None
        assert len(repo.list_all()) == 0

    def test_delete_missing_returns_false(self, repo):
        """测试删除不存在的策略返回 False"""
        result = repo.delete("nonexistent_id")
        assert result is False


# ==================== TestEdgeCases ====================


class TestEdgeCases:
    """测试边缘情况"""

    def test_find_by_condition_duplicate_conditions_in_one_strategy_still_single_match(
        self, repo
    ):
        """测试一个策略包含重复条件时仍只返回一次"""
        strategy_id = repo.register("dup", ["test", "test", "bias"], "warn")

        matches = repo.find_by_condition("test")

        # 应该只返回一次
        assert len(matches) == 1
        assert matches[0]["id"] == strategy_id

    def test_find_by_condition_condition_string_exact_match_only(self, repo):
        """测试 find_by_condition 使用精确匹配（子串不匹配）"""
        repo.register("test", ["test_condition"], "warn")

        # "test" 不应匹配 "test_condition"
        matches = repo.find_by_condition("test")
        assert matches == []

        # "test_condition" 应该匹配
        matches = repo.find_by_condition("test_condition")
        assert len(matches) == 1

    def test_register_accepts_action_params_and_persists(self, repo):
        """测试 register 接受并持久化 action_params"""
        custom_params = {"timeout": 30, "retry": True}
        strategy_id = repo.register(
            name="custom",
            trigger_conditions=["test"],
            action="warn",
            action_params=custom_params,
        )

        strategy = repo.get(strategy_id)
        assert strategy["action_params"] == custom_params

    def test_list_all_after_delete_reflects_removal(self, repo):
        """测试删除后 list_all 反映移除"""
        id1 = repo.register("s1", ["test"], "warn")
        id2 = repo.register("s2", ["test"], "block")

        repo.delete(id1)

        strategies = repo.list_all()
        assert len(strategies) == 1
        assert strategies[0]["id"] == id2
