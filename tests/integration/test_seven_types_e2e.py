from unittest.mock import AsyncMock

import pytest

from src.domain.agents.coordinator_agent import ValidationResult
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.context_manager import GlobalContext, SessionContext, WorkflowContext
from src.domain.services.event_bus import EventBus
from src.domain.services.node_registry import NodeFactory, NodeRegistry

# ========= Fixtures =========


@pytest.fixture
def event_bus():
    """真实事件总线，用于验证事件发布流程。"""
    return EventBus()


@pytest.fixture
def mock_coordinator():
    """Mock CoordinatorAgent 的安全验证方法，默认全部放行。"""
    coordinator = AsyncMock()
    coordinator.validate_file_operation.return_value = ValidationResult(is_valid=True, errors=[])
    coordinator.validate_api_request.return_value = ValidationResult(is_valid=True, errors=[])
    coordinator.validate_human_interaction.return_value = ValidationResult(is_valid=True, errors=[])
    return coordinator


@pytest.fixture
def mock_node_executor():
    """Mock NodeExecutor.execute，根据节点配置返回不同结果。"""

    async def _execute(node_id, config, inputs):
        # FILE 节点
        if "operation" in config:
            op = config.get("operation")
            if op == "read":
                return {"status": "success", "path": config.get("path"), "content": "mock_content"}
            if op == "write":
                content = config.get("content", "")
                return {"status": "success", "bytes_written": len(content.encode("utf-8"))}
            if op == "list":
                return {"status": "success", "items": [], "count": 0}
            return {"status": "success"}

        # DATA_PROCESS 节点
        if config.get("type") == "field_mapping":
            return {"status": "success", "result": {"mapped": True}}

        # HUMAN 节点
        if config.get("prompt"):
            return {"status": "pending_human_input"}

        # 默认返回
        return {"status": "success"}

    executor = AsyncMock()
    executor.execute.side_effect = _execute
    return executor


@pytest.fixture
def workflow_agent(event_bus, mock_coordinator, mock_node_executor):
    """注入 mock 依赖的 WorkflowAgent。"""
    registry = NodeRegistry()
    factory = NodeFactory(registry)

    global_ctx = GlobalContext(user_id="user_001")
    session_ctx = SessionContext(session_id="sess_001", global_context=global_ctx)
    workflow_ctx = WorkflowContext(workflow_id="wf_001", session_context=session_ctx)

    agent = WorkflowAgent(
        workflow_context=workflow_ctx,
        node_factory=factory,
        node_executor=mock_node_executor,
        event_bus=event_bus,
        coordinator_agent=mock_coordinator,
    )
    return agent


# ========= Tests =========


@pytest.mark.asyncio
async def test_execute_plan_with_file_node(workflow_agent, tmp_path):
    """测试FILE节点执行：read操作。"""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world", encoding="utf-8")

    plan = {
        "name": "test_workflow",
        "goal": "read file",
        "nodes": [
            {
                "name": "file_read",
                "type": "file",
                "config": {"operation": "read", "path": str(file_path)},
            }
        ],
        "edges": [],
    }

    result = await workflow_agent.execute_plan_from_dict(plan)

    assert result["status"] == "completed"
    node_id = result["node_mapping"]["file_read"]
    assert "content" in result["results"][node_id]


@pytest.mark.asyncio
async def test_coordinator_blocks_insecure_file_operation(workflow_agent, mock_coordinator):
    """测试CoordinatorAgent拦截路径遍历攻击。"""
    mock_coordinator.validate_file_operation.return_value = ValidationResult(
        is_valid=False, errors=["path contains traversal"]
    )

    plan = {
        "name": "insecure_workflow",
        "goal": "read sensitive file",
        "nodes": [
            {
                "name": "file_attack",
                "type": "file",
                "config": {"operation": "read", "path": "../etc/passwd"},
            }
        ],
        "edges": [],
    }

    result = await workflow_agent.execute_plan_from_dict(plan)

    # 执行应失败，错误来自安全校验
    assert result["status"] == "failed"
    assert "path contains traversal" in result.get("error", "")

    mock_coordinator.validate_file_operation.assert_awaited()


@pytest.mark.asyncio
async def test_execute_plan_accepts_both_type_and_node_type_fields(workflow_agent, tmp_path):
    """测试execute_plan_from_dict接受type和node_type字段。"""
    file_path = tmp_path / "compat.txt"
    file_path.write_text("compat", encoding="utf-8")

    plan = {
        "name": "compat_workflow",
        "goal": "mixed type fields",
        "nodes": [
            {
                "name": "file_node",
                "type": "FILE",  # 大写 type
                "config": {"operation": "read", "path": str(file_path)},
            },
            {
                "name": "human_node",
                "node_type": "human",  # 使用 node_type 字段
                "config": {"prompt": "Approve?"},
            },
        ],
        "edges": [],
    }

    result = await workflow_agent.execute_plan_from_dict(plan)

    # human 节点会导致 pending，也接受 completed（如果 human 在后且未执行到）
    assert result["status"] in ["completed", "pending_human_input"]
    assert "file_node" in result["node_mapping"]
