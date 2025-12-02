"""测试：Agent 实体

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- Agent 是系统的核心聚合根
- 用户通过"起点 + 目的"一句话创建 Agent
- 这是 P0 优先级功能
"""

from datetime import datetime

import pytest

from src.domain.entities.agent import Agent
from src.domain.exceptions import DomainError


class TestAgentCreation:
    """测试 Agent 创建

    测试策略：
    1. 先测试正常路径（Happy Path）
    2. 再测试异常路径（业务规则验证）
    3. 最后测试边界情况
    """

    def test_create_agent_with_valid_start_and_goal_should_succeed(self):
        """测试：使用有效的 start 和 goal 创建 Agent 应该成功

        业务需求：
        - 用户输入"起点 + 目的"，一句话创建 Agent
        - 这是系统的核心功能（P0 优先级）

        验收标准：
        - Agent 必须有唯一 ID
        - start 和 goal 必须被正确保存
        - 默认状态为 active
        - 自动生成名称（如果未提供）
        - 记录创建时间
        """
        # Arrange & Act
        agent = Agent.create(start="我有一个 CSV 文件", goal="分析销售数据并生成报告")

        # Assert
        assert agent.id is not None, "Agent 必须有唯一 ID"
        assert agent.start == "我有一个 CSV 文件", "start 必须被正确保存"
        assert agent.goal == "分析销售数据并生成报告", "goal 必须被正确保存"
        assert agent.status == "active", "默认状态应该是 active"
        assert agent.name is not None, "必须自动生成名称"
        assert agent.created_at is not None, "必须记录创建时间"
        assert isinstance(agent.created_at, datetime), "创建时间必须是 datetime 类型"

    def test_create_agent_with_empty_start_should_raise_error(self):
        """测试：使用空的 start 创建 Agent 应该抛出错误

        业务规则：
        - start（起点）是必需的，不能为空
        - 这是核心业务约束（不变式）

        为什么需要这个测试？
        1. 防止无效数据：空 start 的 Agent 没有业务意义
        2. 符合 DDD 规范：实体必须维护不变式
        3. 防止生产事故：避免用户误操作创建无效 Agent

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "start 不能为空"
        """
        # Act & Assert
        with pytest.raises(DomainError, match="start 不能为空"):
            Agent.create(start="", goal="分析数据")

    def test_create_agent_with_empty_goal_should_raise_error(self):
        """测试：使用空的 goal 创建 Agent 应该抛出错误

        业务规则：
        - goal（目的）是必需的，不能为空
        - 这是核心业务约束（不变式）

        为什么需要这个测试？
        1. 防止无效数据：空 goal 的 Agent 没有业务意义
        2. 符合 DDD 规范：实体必须维护不变式
        3. 防止生产事故：避免用户误操作创建无效 Agent

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "goal 不能为空"
        """
        # Act & Assert
        with pytest.raises(DomainError, match="goal 不能为空"):
            Agent.create(start="我有数据", goal="")

    def test_create_agent_with_whitespace_start_should_raise_error(self):
        """测试：使用纯空格的 start 创建 Agent 应该抛出错误

        业务规则：
        - start 不能是纯空格（通过 strip() 验证）
        - 防止用户输入无意义的空白字符绕过验证

        为什么需要这个测试？
        1. 边界情况：空字符串和纯空格都应该被拒绝
        2. 数据质量：确保 start 包含有效内容
        3. 用户体验：及时反馈输入错误

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "start 不能为空"
        """
        # Act & Assert
        with pytest.raises(DomainError, match="start 不能为空"):
            Agent.create(start="   ", goal="分析数据")

    def test_create_agent_with_whitespace_goal_should_raise_error(self):
        """测试：使用纯空格的 goal 创建 Agent 应该抛出错误

        业务规则：
        - goal 不能是纯空格（通过 strip() 验证）
        - 防止用户输入无意义的空白字符绕过验证

        为什么需要这个测试？
        1. 边界情况：空字符串和纯空格都应该被拒绝
        2. 数据质量：确保 goal 包含有效内容
        3. 用户体验：及时反馈输入错误

        验收标准：
        - 抛出 DomainError 异常
        - 错误消息包含 "goal 不能为空"
        """
        # Act & Assert
        with pytest.raises(DomainError, match="goal 不能为空"):
            Agent.create(start="我有数据", goal="   ")

    def test_create_agent_with_custom_name_should_use_provided_name(self):
        """测试：使用自定义名称创建 Agent 应该使用提供的名称

        业务需求：
        - 用户可以为 Agent 指定自定义名称
        - 自定义名称优先于自动生成的名称

        为什么需要这个测试？
        1. 功能验证：确保 name 参数正常工作
        2. 用户体验：用户可以使用有意义的名称
        3. 业务价值：便于识别和管理多个 Agent

        验收标准：
        - Agent 的 name 应该是用户提供的值
        - 不应该使用自动生成的格式
        """
        # Arrange
        custom_name = "销售数据分析助手"

        # Act
        agent = Agent.create(
            start="我有一个 CSV 文件", goal="分析销售数据并生成报告", name=custom_name
        )

        # Assert
        assert agent.name == custom_name, "应该使用用户提供的自定义名称"

    def test_create_agent_without_name_should_auto_generate_name(self):
        """测试：不提供名称创建 Agent 应该自动生成名称

        业务需求：
        - 如果用户不提供名称，系统自动生成
        - 自动生成的名称格式为 "Agent-YYYYMMDD-HHMMSS"

        为什么需要这个测试？
        1. 默认行为验证：确保自动生成逻辑正常工作
        2. 用户体验：降低使用门槛，name 是可选的
        3. 数据完整性：确保每个 Agent 都有名称

        验收标准：
        - Agent 的 name 不为空
        - name 格式符合 "Agent-YYYYMMDD-HHMMSS" 模式
        """
        # Act
        agent = Agent.create(start="我有一个 CSV 文件", goal="分析销售数据并生成报告")

        # Assert
        assert agent.name is not None, "必须自动生成名称"
        assert agent.name.startswith("Agent-"), "自动生成的名称应该以 'Agent-' 开头"
        assert len(agent.name) == len("Agent-20240101-123456"), (
            "名称格式应该是 'Agent-YYYYMMDD-HHMMSS'"
        )

    def test_create_multiple_agents_should_have_unique_ids(self):
        """测试：创建多个 Agent 应该有唯一的 ID

        业务规则：
        - 每个 Agent 必须有全局唯一的 ID
        - 使用 UUID 保证唯一性

        为什么需要这个测试？
        1. 核心约束：ID 唯一性是实体的基本要求
        2. 数据完整性：防止 ID 冲突导致的数据混乱
        3. 系统可靠性：确保 UUID 生成机制正常工作

        验收标准：
        - 多次创建的 Agent 应该有不同的 ID
        - ID 应该是有效的 UUID 格式
        """
        # Act
        agent1 = Agent.create(start="起点1", goal="目的1")
        agent2 = Agent.create(start="起点2", goal="目的2")
        agent3 = Agent.create(start="起点3", goal="目的3")

        # Assert
        assert agent1.id != agent2.id, "不同 Agent 的 ID 必须不同"
        assert agent1.id != agent3.id, "不同 Agent 的 ID 必须不同"
        assert agent2.id != agent3.id, "不同 Agent 的 ID 必须不同"

    def test_create_agent_should_trim_whitespace_from_start_and_goal(self):
        """测试：创建 Agent 应该去除 start 和 goal 的首尾空格

        业务规则：
        - 自动规范化用户输入，去除首尾空格
        - 提高数据质量和一致性

        为什么需要这个测试？
        1. 数据规范化：统一数据格式
        2. 用户体验：容错处理，用户不需要手动清理空格
        3. 业务逻辑：确保后续处理的数据是干净的

        验收标准：
        - 保存的 start 和 goal 不应该包含首尾空格
        - 中间的空格应该保留
        """
        # Act
        agent = Agent.create(start="  我有一个 CSV 文件  ", goal="  分析销售数据并生成报告  ")

        # Assert
        assert agent.start == "我有一个 CSV 文件", "start 应该去除首尾空格"
        assert agent.goal == "分析销售数据并生成报告", "goal 应该去除首尾空格"
