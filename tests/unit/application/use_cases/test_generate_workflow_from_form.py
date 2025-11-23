"""GenerateWorkflowFromFormUseCase 单元测试

TDD 第一步：先写测试，定义期望的行为
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.application.use_cases.generate_workflow_from_form import (
    GenerateWorkflowFromFormUseCase,
    GenerateWorkflowInput,
)
from src.domain.exceptions import DomainError
from src.domain.ports.workflow_repository import WorkflowRepository


@pytest.fixture
def mock_workflow_repository():
    """Mock workflow repository"""
    return Mock(spec=WorkflowRepository)


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for workflow generation"""
    client = Mock()
    client.generate_workflow = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_generate_simple_workflow_from_form(mock_workflow_repository, mock_llm_client):
    """测试：从简单表单描述生成工作流应该成功"""
    # 配置 mock LLM 返回值
    mock_llm_client.generate_workflow.return_value = {
        "name": "数据处理工作流",
        "description": "从API获取数据并处理",
        "nodes": [
            {
                "type": "start",
                "name": "开始",
                "config": {},
                "position": {"x": 100, "y": 100},
            },
            {
                "type": "httpRequest",
                "name": "获取数据",
                "config": {
                    "url": "https://api.example.com/data",
                    "method": "GET",
                },
                "position": {"x": 300, "y": 100},
            },
            {
                "type": "end",
                "name": "结束",
                "config": {},
                "position": {"x": 500, "y": 100},
            },
        ],
        "edges": [
            {"source": "node_1", "target": "node_2"},
            {"source": "node_2", "target": "node_3"},
        ],
    }

    use_case = GenerateWorkflowFromFormUseCase(
        workflow_repository=mock_workflow_repository,
        llm_client=mock_llm_client,
    )

    input_data = GenerateWorkflowInput(
        description="从API获取数据并处理",
        goal="获取外部数据并进行转换",
    )

    workflow = await use_case.execute(input_data)

    assert workflow is not None
    assert workflow.name == "数据处理工作流"
    assert workflow.description == "从API获取数据并处理"
    assert len(workflow.nodes) == 3
    assert len(workflow.edges) == 2
    assert workflow.source == "feagent"

    # 验证保存到了repository
    mock_workflow_repository.save.assert_called_once()


@pytest.mark.asyncio
async def test_generate_complex_workflow_with_conditional_logic(
    mock_workflow_repository, mock_llm_client
):
    """测试：生成包含条件分支的复杂工作流"""
    mock_llm_client.generate_workflow.return_value = {
        "name": "条件处理工作流",
        "description": "根据数据值进行不同处理",
        "nodes": [
            {
                "type": "start",
                "name": "开始",
                "config": {},
                "position": {"x": 100, "y": 100},
            },
            {
                "type": "httpRequest",
                "name": "获取数据",
                "config": {"url": "https://api.example.com/data", "method": "GET"},
                "position": {"x": 300, "y": 100},
            },
            {
                "type": "conditional",
                "name": "检查状态",
                "config": {"condition": "status === 'active'"},
                "position": {"x": 500, "y": 100},
            },
            {
                "type": "httpRequest",
                "name": "处理激活状态",
                "config": {"url": "https://api.example.com/active", "method": "POST"},
                "position": {"x": 700, "y": 50},
            },
            {
                "type": "httpRequest",
                "name": "处理非激活状态",
                "config": {"url": "https://api.example.com/inactive", "method": "POST"},
                "position": {"x": 700, "y": 150},
            },
            {
                "type": "end",
                "name": "结束",
                "config": {},
                "position": {"x": 900, "y": 100},
            },
        ],
        "edges": [
            {"source": "node_1", "target": "node_2"},
            {"source": "node_2", "target": "node_3"},
            {"source": "node_3", "target": "node_4", "condition": "true"},
            {"source": "node_3", "target": "node_5", "condition": "false"},
            {"source": "node_4", "target": "node_6"},
            {"source": "node_5", "target": "node_6"},
        ],
    }

    use_case = GenerateWorkflowFromFormUseCase(
        workflow_repository=mock_workflow_repository,
        llm_client=mock_llm_client,
    )

    input_data = GenerateWorkflowInput(
        description="根据数据状态进行不同处理",
        goal="处理不同状态的数据",
    )

    workflow = await use_case.execute(input_data)

    assert len(workflow.nodes) == 6
    assert len(workflow.edges) == 6
    # 验证有条件边
    conditional_edges = [e for e in workflow.edges if e.condition is not None]
    assert len(conditional_edges) == 2


@pytest.mark.asyncio
async def test_generate_workflow_with_loop_processing(mock_workflow_repository, mock_llm_client):
    """测试：生成包含循环处理的工作流"""
    mock_llm_client.generate_workflow.return_value = {
        "name": "批量处理工作流",
        "description": "批量处理数据列表",
        "nodes": [
            {
                "type": "start",
                "name": "开始",
                "config": {},
                "position": {"x": 100, "y": 100},
            },
            {
                "type": "httpRequest",
                "name": "获取数据列表",
                "config": {"url": "https://api.example.com/items", "method": "GET"},
                "position": {"x": 300, "y": 100},
            },
            {
                "type": "loop",
                "name": "遍历处理",
                "config": {
                    "type": "for_each",
                    "array": "items",
                    "code": "result = item * 2",
                },
                "position": {"x": 500, "y": 100},
            },
            {
                "type": "end",
                "name": "结束",
                "config": {},
                "position": {"x": 700, "y": 100},
            },
        ],
        "edges": [
            {"source": "node_1", "target": "node_2"},
            {"source": "node_2", "target": "node_3"},
            {"source": "node_3", "target": "node_4"},
        ],
    }

    use_case = GenerateWorkflowFromFormUseCase(
        workflow_repository=mock_workflow_repository,
        llm_client=mock_llm_client,
    )

    input_data = GenerateWorkflowInput(
        description="批量处理数据列表",
        goal="对每个数据项进行转换",
    )

    workflow = await use_case.execute(input_data)

    assert len(workflow.nodes) == 4
    # 验证有loop节点
    loop_nodes = [n for n in workflow.nodes if n.type.value == "loop"]
    assert len(loop_nodes) == 1
    assert loop_nodes[0].config["type"] == "for_each"


@pytest.mark.asyncio
async def test_generate_workflow_missing_description(mock_workflow_repository, mock_llm_client):
    """测试：缺少描述应该抛出 DomainError"""
    use_case = GenerateWorkflowFromFormUseCase(
        workflow_repository=mock_workflow_repository,
        llm_client=mock_llm_client,
    )

    input_data = GenerateWorkflowInput(
        description="",
        goal="目标",
    )

    with pytest.raises(DomainError, match="description不能为空"):
        await use_case.execute(input_data)


@pytest.mark.asyncio
async def test_generate_workflow_llm_generation_failure(mock_workflow_repository, mock_llm_client):
    """测试：LLM生成失败应该抛出异常"""
    # 配置 mock LLM 抛出异常
    mock_llm_client.generate_workflow.side_effect = Exception("LLM API 调用失败")

    use_case = GenerateWorkflowFromFormUseCase(
        workflow_repository=mock_workflow_repository,
        llm_client=mock_llm_client,
    )

    input_data = GenerateWorkflowInput(
        description="测试工作流",
        goal="测试目标",
    )

    with pytest.raises(Exception, match="LLM API 调用失败"):
        await use_case.execute(input_data)


@pytest.mark.asyncio
async def test_generate_workflow_invalid_llm_response(mock_workflow_repository, mock_llm_client):
    """测试：LLM返回无效数据应该抛出 DomainError"""
    # 配置 mock LLM 返回无效数据（缺少nodes）
    mock_llm_client.generate_workflow.return_value = {
        "name": "测试工作流",
        "description": "描述",
        "nodes": [],  # 空节点列表
        "edges": [],
    }

    use_case = GenerateWorkflowFromFormUseCase(
        workflow_repository=mock_workflow_repository,
        llm_client=mock_llm_client,
    )

    input_data = GenerateWorkflowInput(
        description="测试工作流",
        goal="测试目标",
    )

    with pytest.raises(DomainError, match="至少需要一个节点"):
        await use_case.execute(input_data)
