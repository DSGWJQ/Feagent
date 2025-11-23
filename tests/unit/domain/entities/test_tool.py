"""测试：Tool 实体

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- Tool 是工具的聚合根
- 支持工具的生命周期管理（DRAFT → TESTING → PUBLISHED → DEPRECATED）
- 支持多种工具分类和实现方式
- 追踪工具使用统计
"""

import pytest

from src.domain.entities.tool import Tool, ToolCategory, ToolParameter, ToolStatus
from src.domain.exceptions import DomainError


class TestToolCreation:
    """测试 Tool 创建"""

    def test_create_tool_with_valid_params_should_succeed(self):
        """测试：使用有效参数创建 Tool 应该成功

        验收标准：
        - Tool 必须有唯一 ID
        - name、description、category、author 必须被正确保存
        - 默认状态为 DRAFT
        - 默认版本为 "0.1.0"
        - 初始 usage_count 为 0
        - 记录创建时间
        """
        # Arrange
        # Act
        tool = Tool.create(
            name="HTTP 请求工具",
            description="发送 HTTP 请求",
            category=ToolCategory.HTTP,
            author="system",
        )

        # Assert
        assert tool.id is not None, "Tool 必须有唯一 ID"
        assert tool.id.startswith("tool_"), "Tool ID 应该以 tool_ 开头"
        assert tool.name == "HTTP 请求工具"
        assert tool.description == "发送 HTTP 请求"
        assert tool.category == ToolCategory.HTTP
        assert tool.author == "system"
        assert tool.status == ToolStatus.DRAFT
        assert tool.version == "0.1.0"
        assert tool.usage_count == 0
        assert tool.parameters == []
        assert tool.returns == {}
        assert tool.created_at is not None

    def test_create_tool_with_empty_name_should_raise_error(self):
        """测试：使用空名称创建 Tool 应该抛出错误"""
        # Act & Assert
        with pytest.raises(DomainError, match="工具名称不能为空"):
            Tool.create(
                name="",
                description="测试",
                category=ToolCategory.HTTP,
                author="system",
            )

    def test_create_tool_with_parameters(self):
        """测试：创建带参数的 Tool

        验收标准：
        - 可以添加工具参数
        - 参数包含名称、类型、描述等元数据
        """
        # Arrange
        params = [
            ToolParameter(
                name="url",
                type="string",
                description="请求URL",
                required=True,
            ),
            ToolParameter(
                name="method",
                type="string",
                description="HTTP方法",
                required=False,
                default="GET",
                enum=["GET", "POST", "PUT", "DELETE"],
            ),
        ]

        # Act
        tool = Tool.create(
            name="HTTP 请求工具",
            description="发送 HTTP 请求",
            category=ToolCategory.HTTP,
            author="system",
            parameters=params,
        )

        # Assert
        assert len(tool.parameters) == 2
        assert tool.parameters[0].name == "url"
        assert tool.parameters[0].required is True
        assert tool.parameters[1].enum == ["GET", "POST", "PUT", "DELETE"]


class TestToolLifecycle:
    """测试 Tool 生命周期"""

    def test_publish_tool_should_succeed(self):
        """测试：发布工具应该成功

        验收标准：
        - 只有 TESTING 状态的工具才能发布
        - 发布后状态变为 PUBLISHED
        - 记录发布时间
        """
        # Arrange
        tool = Tool.create(
            name="测试工具",
            description="描述",
            category=ToolCategory.HTTP,
            author="system",
        )
        tool.status = ToolStatus.TESTING  # 设置为测试状态

        # Act
        tool.publish()

        # Assert
        assert tool.status == ToolStatus.PUBLISHED
        assert tool.published_at is not None

    def test_publish_tool_in_draft_status_should_fail(self):
        """测试：发布草稿状态的工具应该失败

        业务规则：
        - 只有 TESTING 状态的工具才能发布
        """
        # Arrange
        tool = Tool.create(
            name="测试工具",
            description="描述",
            category=ToolCategory.HTTP,
            author="system",
        )
        # tool.status 默认为 DRAFT

        # Act & Assert
        with pytest.raises(DomainError, match="只有测试通过的工具才能发布"):
            tool.publish()

    def test_deprecate_tool_should_succeed(self):
        """测试：废弃工具应该成功

        验收标准：
        - 状态变为 DEPRECATED
        - 记录废弃原因
        - 更新时间戳
        """
        # Arrange
        tool = Tool.create(
            name="旧工具",
            description="描述",
            category=ToolCategory.HTTP,
            author="system",
        )
        reason = "已被新工具替代"

        # Act
        tool.deprecate(reason)

        # Assert
        assert tool.status == ToolStatus.DEPRECATED
        assert tool.implementation_config.get("deprecation_reason") == reason
        assert tool.updated_at is not None

    def test_increment_usage_should_succeed(self):
        """测试：增加使用计数应该成功

        验收标准：
        - usage_count 递增
        - 更新 last_used_at 时间
        """
        # Arrange
        tool = Tool.create(
            name="工具",
            description="描述",
            category=ToolCategory.HTTP,
            author="system",
        )
        initial_count = tool.usage_count

        # Act
        tool.increment_usage()
        tool.increment_usage()

        # Assert
        assert tool.usage_count == initial_count + 2
        assert tool.last_used_at is not None


class TestToolCategories:
    """测试 Tool 分类"""

    def test_http_tool_creation(self):
        """测试：创建 HTTP 工具"""
        tool = Tool.create(
            name="HTTP请求",
            description="发送HTTP请求",
            category=ToolCategory.HTTP,
            author="system",
            implementation_type="builtin",
            implementation_config={"timeout": 30},
        )

        assert tool.category == ToolCategory.HTTP
        assert tool.implementation_config["timeout"] == 30

    def test_database_tool_creation(self):
        """测试：创建数据库工具"""
        tool = Tool.create(
            name="数据库查询",
            description="执行数据库查询",
            category=ToolCategory.DATABASE,
            author="system",
        )

        assert tool.category == ToolCategory.DATABASE

    def test_file_tool_creation(self):
        """测试：创建文件处理工具"""
        tool = Tool.create(
            name="文件操作",
            description="读写文件",
            category=ToolCategory.FILE,
            author="system",
        )

        assert tool.category == ToolCategory.FILE

    def test_custom_tool_creation(self):
        """测试：创建自定义工具"""
        tool = Tool.create(
            name="自定义工具",
            description="用户自定义的工具",
            category=ToolCategory.CUSTOM,
            author="user123",
            implementation_type="javascript",
            implementation_config={"code": "return input * 2;"},
        )

        assert tool.category == ToolCategory.CUSTOM
        assert tool.implementation_type == "javascript"
