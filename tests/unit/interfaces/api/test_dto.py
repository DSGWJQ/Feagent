"""DTO（Data Transfer Objects）单元测试

测试目标：
1. 验证 Pydantic 模型的数据验证逻辑
2. 验证必填字段、可选字段
3. 验证数据类型转换
4. 验证字段验证器（如：去除空格、非空验证）

为什么先写测试？
- TDD 原则：先定义预期行为，再实现功能
- DTO 是 API 的契约，必须严格验证
- Pydantic 的验证逻辑需要测试覆盖

测试策略：
- 测试成功场景：正常数据能通过验证
- 测试失败场景：非法数据抛出 ValidationError
- 测试边界条件：空字符串、纯空格、None
"""

import pytest
from pydantic import ValidationError


class TestCreateAgentRequest:
    """测试 CreateAgentRequest DTO

    业务场景：用户通过 API 创建 Agent

    必填字段：
    - start: 任务起点描述
    - goal: 任务目的描述

    可选字段：
    - name: Agent 名称（不提供时自动生成）
    """

    def test_create_agent_request_with_all_fields(self):
        """测试：提供所有字段时，应该成功创建"""
        from src.interfaces.api.dto import CreateAgentRequest

        data = {
            "start": "我有一个 CSV 文件，包含销售数据",
            "goal": "分析销售数据并生成报告",
            "name": "销售数据分析 Agent",
        }
        request = CreateAgentRequest(**data)

        assert request.start == "我有一个 CSV 文件，包含销售数据"
        assert request.goal == "分析销售数据并生成报告"
        assert request.name == "销售数据分析 Agent"

    def test_create_agent_request_without_name(self):
        """测试：不提供 name 时，应该成功创建（name 是可选的）"""
        from src.interfaces.api.dto import CreateAgentRequest

        data = {
            "start": "我有一个 CSV 文件",
            "goal": "分析销售数据并生成报告",
        }
        request = CreateAgentRequest(**data)

        assert request.start == "我有一个 CSV 文件"
        assert request.goal == "分析销售数据并生成报告"
        assert request.name is None

    def test_create_agent_request_with_empty_start(self):
        """测试：start 为空字符串时，应该抛出 ValidationError"""
        from src.interfaces.api.dto import CreateAgentRequest

        data = {
            "start": "",
            "goal": "分析销售数据并生成报告",
        }

        with pytest.raises(ValidationError) as exc_info:
            CreateAgentRequest(**data)

        # 验证错误信息
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("start",)
        assert "不能为空" in errors[0]["msg"] or "empty" in errors[0]["msg"].lower()

    def test_create_agent_request_with_empty_goal(self):
        """测试：goal 为空字符串时，应该抛出 ValidationError"""
        from src.interfaces.api.dto import CreateAgentRequest

        data = {
            "start": "我有一个 CSV 文件",
            "goal": "",
        }

        with pytest.raises(ValidationError) as exc_info:
            CreateAgentRequest(**data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("goal",)

    def test_create_agent_request_with_whitespace_start(self):
        """测试：start 为纯空格时，应该抛出 ValidationError"""
        from src.interfaces.api.dto import CreateAgentRequest

        data = {
            "start": "   ",
            "goal": "分析销售数据并生成报告",
        }

        with pytest.raises(ValidationError) as exc_info:
            CreateAgentRequest(**data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("start",)

    def test_create_agent_request_trims_whitespace(self):
        """测试：应该自动去除首尾空格"""
        from src.interfaces.api.dto import CreateAgentRequest

        data = {
            "start": "  我有一个 CSV 文件  ",
            "goal": "  分析销售数据并生成报告  ",
            "name": "  测试 Agent  ",
        }
        request = CreateAgentRequest(**data)

        assert request.start == "我有一个 CSV 文件"
        assert request.goal == "分析销售数据并生成报告"
        assert request.name == "测试 Agent"


class TestTaskResponse:
    """测试 TaskResponse DTO

    业务场景：API 返回 Task 信息给前端

    字段：
    - id: Task ID
    - agent_id: 关联的 Agent ID
    - name: 任务名称
    - description: 任务描述（可选）
    - status: 任务状态
    - created_at: 创建时间
    """

    def test_task_response_with_all_fields(self):
        """测试：提供所有字段时，应该成功创建"""
        from datetime import datetime

        from src.interfaces.api.dto import TaskResponse

        data = {
            "id": "task-123",
            "agent_id": "agent-456",
            "name": "读取 CSV 文件",
            "description": "使用 pandas 读取 CSV 文件到 DataFrame",
            "status": "pending",
            "created_at": datetime.now(),
        }
        response = TaskResponse(**data)

        assert response.id == "task-123"
        assert response.agent_id == "agent-456"
        assert response.name == "读取 CSV 文件"
        assert response.description == "使用 pandas 读取 CSV 文件到 DataFrame"
        assert response.status == "pending"
        assert isinstance(response.created_at, datetime)

    def test_task_response_without_description(self):
        """测试：description 是可选字段"""
        from datetime import datetime

        from src.interfaces.api.dto import TaskResponse

        data = {
            "id": "task-123",
            "agent_id": "agent-456",
            "name": "读取 CSV 文件",
            "description": None,
            "status": "pending",
            "created_at": datetime.now(),
        }
        response = TaskResponse(**data)

        assert response.id == "task-123"
        assert response.description is None

    def test_task_response_serialization(self):
        """测试：应该能序列化为 JSON"""
        from datetime import datetime

        from src.interfaces.api.dto import TaskResponse

        data = {
            "id": "task-123",
            "agent_id": "agent-456",
            "name": "读取 CSV 文件",
            "description": "使用 pandas 读取 CSV 文件到 DataFrame",
            "status": "pending",
            "created_at": datetime.now(),
        }
        response = TaskResponse(**data)

        # 测试序列化
        json_data = response.model_dump()
        assert json_data["id"] == "task-123"
        assert json_data["agent_id"] == "agent-456"
        assert json_data["name"] == "读取 CSV 文件"


class TestAgentResponse:
    """测试 AgentResponse DTO

    业务场景：API 返回 Agent 信息给前端

    字段：
    - id: Agent ID
    - start: 任务起点描述
    - goal: 任务目的描述
    - name: Agent 名称
    - status: Agent 状态
    - created_at: 创建时间
    - tasks: 关联的 Tasks（可选）
    """

    def test_agent_response_with_all_fields(self):
        """测试：提供所有字段时，应该成功创建"""
        from datetime import datetime

        from src.interfaces.api.dto import AgentResponse

        data = {
            "id": "agent-123",
            "start": "我有一个 CSV 文件",
            "goal": "分析数据",
            "name": "测试 Agent",
            "status": "active",
            "created_at": datetime.now(),
            "tasks": [],  # 新增：tasks 字段
        }
        response = AgentResponse(**data)

        assert response.id == "agent-123"
        assert response.start == "我有一个 CSV 文件"
        assert response.goal == "分析数据"
        assert response.name == "测试 Agent"
        assert response.status == "active"
        assert isinstance(response.created_at, datetime)
        assert response.tasks == []  # 新增：验证 tasks 字段

    def test_agent_response_with_tasks(self):
        """测试：AgentResponse 应该包含 Tasks"""
        from datetime import datetime

        from src.interfaces.api.dto import AgentResponse, TaskResponse

        task_data = {
            "id": "task-123",
            "agent_id": "agent-123",
            "name": "读取 CSV 文件",
            "description": "使用 pandas 读取 CSV 文件到 DataFrame",
            "status": "pending",
            "created_at": datetime.now(),
        }
        task = TaskResponse(**task_data)

        data = {
            "id": "agent-123",
            "start": "我有一个 CSV 文件",
            "goal": "分析数据",
            "name": "测试 Agent",
            "status": "active",
            "created_at": datetime.now(),
            "tasks": [task],
        }
        response = AgentResponse(**data)

        assert len(response.tasks) == 1
        assert response.tasks[0].id == "task-123"
        assert response.tasks[0].name == "读取 CSV 文件"

    def test_agent_response_serialization(self):
        """测试：应该能序列化为 JSON"""
        from datetime import datetime

        from src.interfaces.api.dto import AgentResponse

        data = {
            "id": "agent-123",
            "start": "我有一个 CSV 文件",
            "goal": "分析数据",
            "name": "测试 Agent",
            "status": "active",
            "created_at": datetime.now(),
        }
        response = AgentResponse(**data)

        # Pydantic v2 使用 model_dump() 而不是 dict()
        json_data = response.model_dump()

        assert json_data["id"] == "agent-123"
        assert json_data["start"] == "我有一个 CSV 文件"
        assert "created_at" in json_data


class TestExecuteRunRequest:
    """测试 ExecuteRunRequest DTO

    业务场景：用户通过 API 触发 Agent 执行

    字段：
    - agent_id: Agent ID（从 URL 路径参数获取，不在请求体中）

    注意：当前简化实现，请求体为空
    未来可能添加：input_data（运行时输入）
    """

    def test_execute_run_request_empty_body(self):
        """测试：请求体为空时，应该成功创建"""
        from src.interfaces.api.dto import ExecuteRunRequest

        request = ExecuteRunRequest()
        assert request is not None


class TestRunResponse:
    """测试 RunResponse DTO

    业务场景：API 返回 Run 信息给前端

    字段：
    - id: Run ID
    - agent_id: Agent ID
    - status: Run 状态
    - created_at: 创建时间
    - started_at: 启动时间（可选）
    - finished_at: 完成时间（可选）
    - error: 错误信息（可选）
    """

    def test_run_response_with_all_fields(self):
        """测试：提供所有字段时，应该成功创建"""
        from datetime import datetime

        from src.interfaces.api.dto import RunResponse

        data = {
            "id": "run-123",
            "agent_id": "agent-123",
            "status": "succeeded",
            "created_at": datetime.now(),
            "started_at": datetime.now(),
            "finished_at": datetime.now(),
            "error": None,
        }
        response = RunResponse(**data)

        assert response.id == "run-123"
        assert response.agent_id == "agent-123"
        assert response.status == "succeeded"
        assert isinstance(response.created_at, datetime)

    def test_run_response_with_optional_fields_none(self):
        """测试：可选字段为 None 时，应该成功创建"""
        from datetime import datetime

        from src.interfaces.api.dto import RunResponse

        data = {
            "id": "run-123",
            "agent_id": "agent-123",
            "status": "pending",
            "created_at": datetime.now(),
            "started_at": None,
            "finished_at": None,
            "error": None,
        }
        response = RunResponse(**data)

        assert response.started_at is None
        assert response.finished_at is None
        assert response.error is None
