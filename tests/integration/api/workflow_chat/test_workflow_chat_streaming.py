"""测试：工作流对话流式支持 - ReAct 步骤实时流式传输

TDD RED 阶段：定义流式对话的期望行为
- 支持异步流式处理 ReAct 步骤
- 每个步骤完成后立即产生事件
- 事件顺序保证：processing_started → react_step(x N) → modifications_preview → workflow_updated
- 支持流式 cancellation
"""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.application.use_cases.update_workflow_by_chat import (
    UpdateWorkflowByChatInput,
    UpdateWorkflowByChatUseCase,
)
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_chat_service_enhanced import (
    EnhancedWorkflowChatService,
    ModificationResult,
)
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.database.base import Base
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)


@pytest.fixture(scope="function")
def test_engine():
    """创建测试数据库引擎"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(test_engine):
    """创建测试数据库 Session"""
    TestingSessionLocal = sessionmaker(bind=test_engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def workflow_repository(test_db: Session):
    """创建工作流仓储"""
    return SQLAlchemyWorkflowRepository(test_db)


@pytest.fixture
def sample_workflow(workflow_repository: SQLAlchemyWorkflowRepository):
    """创建示例工作流"""
    start_node = Node.create(
        type=NodeType.START,
        name="开始",
        config={},
        position=Position(x=100, y=100),
    )

    workflow = Workflow.create(
        name="测试工作流",
        description="用于测试流式支持",
        nodes=[start_node],
        edges=[],
    )

    workflow_repository.save(workflow)
    return workflow


class TestWorkflowChatStreaming:
    """测试工作流对话流式支持"""

    @pytest.mark.asyncio
    async def test_execute_streaming_method_exists(
        self,
        workflow_repository: SQLAlchemyWorkflowRepository,
        sample_workflow: Workflow,
    ):
        """测试：execute_streaming() 方法存在

        RED 阶段：方法还不存在，此测试应失败
        """
        mock_chat_service = AsyncMock(spec=EnhancedWorkflowChatService)

        use_case = UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=mock_chat_service,
            save_validator=Mock(),
        )

        # 红色：方法应该存在
        assert hasattr(use_case, "execute_streaming"), "execute_streaming 方法不存在"
        assert callable(use_case.execute_streaming), "execute_streaming 应该是可调用的"

    @pytest.mark.asyncio
    async def test_execute_streaming_yields_events(
        self,
        workflow_repository: SQLAlchemyWorkflowRepository,
        sample_workflow: Workflow,
    ):
        """测试：execute_streaming() 返回异步生成器，按顺序产生事件

        RED 阶段：测试流式事件序列
        - processing_started 事件
        - 多个 react_step 事件
        - modifications_preview 事件
        - workflow_updated 事件
        """
        mock_chat_service = AsyncMock(spec=EnhancedWorkflowChatService)

        # Mock 返回包含 react_steps 的修改结果
        mock_result = ModificationResult(
            success=True,
            ai_message="已添加节点",
            intent="add_node",
            confidence=0.95,
            modifications_count=2,
            modified_workflow=sample_workflow,
            react_steps=[
                {
                    "step": 1,
                    "thought": "需要添加数据处理节点",
                    "action": {"type": "add_node", "node": {"name": "process"}},
                    "observation": "节点已添加",
                },
                {
                    "step": 2,
                    "thought": "需要添加验证节点",
                    "action": {"type": "add_node", "node": {"name": "validate"}},
                    "observation": "验证节点已添加",
                },
            ],
        )
        mock_chat_service.process_message.return_value = mock_result

        use_case = UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=mock_chat_service,
            save_validator=Mock(),
        )

        input_data = UpdateWorkflowByChatInput(
            workflow_id=sample_workflow.id,
            user_message="添加处理和验证节点",
        )

        # 红色：execute_streaming 应该返回异步生成器
        result = use_case.execute_streaming(input_data)
        assert hasattr(result, "__aiter__"), "execute_streaming 应该返回异步迭代器"
        assert hasattr(result, "__anext__"), "返回值应该支持 async for"

        # 收集所有事件
        events = []
        async for event in result:
            events.append(event)

        # 红色：验证事件序列
        assert len(events) > 0, "应该产生至少一个事件"

        # 验证事件类型顺序
        event_types = [e.get("type") for e in events]
        assert event_types[0] == "processing_started", "第一个事件应该是 processing_started"
        assert "react_step" in event_types, "应该包含 react_step 类型的事件"
        assert event_types[-1] == "workflow_updated", "最后一个事件应该是 workflow_updated"

    @pytest.mark.asyncio
    async def test_react_step_event_structure(
        self,
        workflow_repository: SQLAlchemyWorkflowRepository,
        sample_workflow: Workflow,
    ):
        """测试：react_step 事件包含正确的字段

        RED 阶段：每个 react_step 事件应该包含：
        - type: "react_step"
        - step_number: 步骤编号
        - thought: 思考内容
        - action: 行动内容
        - observation: 观察结果
        - timestamp: 时间戳
        """
        mock_chat_service = AsyncMock(spec=EnhancedWorkflowChatService)

        react_steps = [
            {
                "step": 1,
                "thought": "第一步思考",
                "action": {"type": "add_node"},
                "observation": "第一步观察",
            }
        ]

        mock_result = ModificationResult(
            success=True,
            ai_message="完成",
            modified_workflow=sample_workflow,
            react_steps=react_steps,
        )
        mock_chat_service.process_message.return_value = mock_result

        use_case = UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=mock_chat_service,
            save_validator=Mock(),
        )

        input_data = UpdateWorkflowByChatInput(
            workflow_id=sample_workflow.id,
            user_message="测试",
        )

        events = []
        async for event in use_case.execute_streaming(input_data):
            events.append(event)

        # 找到 react_step 事件
        react_events = [e for e in events if e.get("type") == "react_step"]
        assert len(react_events) > 0, "应该至少有一个 react_step 事件"

        # 验证 react_step 事件结构
        react_event = react_events[0]
        assert "type" in react_event, "事件应该有 type 字段"
        assert "step_number" in react_event, "事件应该有 step_number 字段"
        assert "thought" in react_event, "事件应该有 thought 字段"
        assert "action" in react_event, "事件应该有 action 字段"
        assert "observation" in react_event, "事件应该有 observation 字段"
        assert "timestamp" in react_event, "事件应该有 timestamp 字段"

    @pytest.mark.asyncio
    async def test_event_sequence_order_preserved(
        self,
        workflow_repository: SQLAlchemyWorkflowRepository,
        sample_workflow: Workflow,
    ):
        """测试：事件顺序保证

        RED 阶段：事件应该按以下顺序产生：
        1. processing_started
        2. react_step (可能有多个)
        3. modifications_preview
        4. workflow_updated
        """
        mock_chat_service = AsyncMock(spec=EnhancedWorkflowChatService)

        # 创建 3 个 react_steps
        react_steps = [
            {
                "step": i,
                "thought": f"步骤{i}思考",
                "action": {"type": "add_node"},
                "observation": f"步骤{i}观察",
            }
            for i in range(1, 4)
        ]

        mock_result = ModificationResult(
            success=True,
            ai_message="完成",
            modifications_count=3,
            modified_workflow=sample_workflow,
            react_steps=react_steps,
        )
        mock_chat_service.process_message.return_value = mock_result

        use_case = UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=mock_chat_service,
            save_validator=Mock(),
        )

        input_data = UpdateWorkflowByChatInput(
            workflow_id=sample_workflow.id,
            user_message="测试",
        )

        events = []
        async for event in use_case.execute_streaming(input_data):
            events.append(event)

        # 红色：验证事件顺序
        event_types = [e.get("type") for e in events]

        # 找到关键事件的索引
        started_idx = None
        first_react_idx = None
        last_react_idx = None
        preview_idx = None
        updated_idx = None

        for i, event_type in enumerate(event_types):
            if event_type == "processing_started":
                started_idx = i
            elif event_type == "react_step":
                if first_react_idx is None:
                    first_react_idx = i
                last_react_idx = i
            elif event_type == "modifications_preview":
                preview_idx = i
            elif event_type == "workflow_updated":
                updated_idx = i

        # 验证事件顺序
        assert started_idx is not None, "应该有 processing_started 事件"
        assert first_react_idx is not None, "应该有 react_step 事件"
        assert preview_idx is not None, "应该有 modifications_preview 事件"
        assert updated_idx is not None, "应该有 workflow_updated 事件"

        # 验证顺序
        assert started_idx < first_react_idx, "processing_started 应该在 react_step 之前"
        assert last_react_idx < preview_idx, "最后的 react_step 应该在 modifications_preview 之前"
        assert preview_idx < updated_idx, "modifications_preview 应该在 workflow_updated 之前"

    @pytest.mark.asyncio
    async def test_modifications_preview_event_format(
        self,
        workflow_repository: SQLAlchemyWorkflowRepository,
        sample_workflow: Workflow,
    ):
        """测试：modifications_preview 事件格式

        RED 阶段：modifications_preview 应该包含：
        - type: "modifications_preview"
        - modifications_count: 修改数量
        - intent: 用户意图
        - confidence: 信心度
        """
        mock_chat_service = AsyncMock(spec=EnhancedWorkflowChatService)

        mock_result = ModificationResult(
            success=True,
            ai_message="完成",
            intent="add_node",
            confidence=0.92,
            modifications_count=2,
            modified_workflow=sample_workflow,
            react_steps=[],
        )
        mock_chat_service.process_message.return_value = mock_result

        use_case = UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=mock_chat_service,
            save_validator=Mock(),
        )

        input_data = UpdateWorkflowByChatInput(
            workflow_id=sample_workflow.id,
            user_message="测试",
        )

        events = []
        async for event in use_case.execute_streaming(input_data):
            events.append(event)

        # 找到 modifications_preview 事件
        preview_events = [e for e in events if e.get("type") == "modifications_preview"]
        assert len(preview_events) > 0, "应该有 modifications_preview 事件"

        preview_event = preview_events[0]
        assert "type" in preview_event
        assert "modifications_count" in preview_event
        assert "intent" in preview_event
        assert "confidence" in preview_event
        assert preview_event["modifications_count"] == 2, "modifications_count 应该正确"
        assert preview_event["intent"] == "add_node", "intent 应该正确"
        assert preview_event["confidence"] == 0.92, "confidence 应该正确"

    @pytest.mark.asyncio
    async def test_workflow_updated_event_contains_final_state(
        self,
        workflow_repository: SQLAlchemyWorkflowRepository,
        sample_workflow: Workflow,
    ):
        """测试：workflow_updated 事件包含最终工作流状态

        RED 阶段：workflow_updated 事件应该包含：
        - type: "workflow_updated"
        - workflow: 完整的工作流数据
        - ai_message: AI 回复消息
        """
        mock_chat_service = AsyncMock(spec=EnhancedWorkflowChatService)

        mock_result = ModificationResult(
            success=True,
            ai_message="已完成流程配置",
            modified_workflow=sample_workflow,
            react_steps=[],
        )
        mock_chat_service.process_message.return_value = mock_result

        use_case = UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=mock_chat_service,
            save_validator=Mock(),
        )

        input_data = UpdateWorkflowByChatInput(
            workflow_id=sample_workflow.id,
            user_message="测试",
        )

        events = []
        async for event in use_case.execute_streaming(input_data):
            events.append(event)

        # 找到 workflow_updated 事件
        updated_events = [e for e in events if e.get("type") == "workflow_updated"]
        assert len(updated_events) > 0, "应该有 workflow_updated 事件"

        updated_event = updated_events[0]
        assert "type" in updated_event
        assert "workflow" in updated_event
        assert "ai_message" in updated_event
        assert updated_event["ai_message"] == "已完成流程配置"
        assert "id" in updated_event["workflow"], "workflow 应该包含 id"
        assert "nodes" in updated_event["workflow"], "workflow 应该包含 nodes"

    @pytest.mark.asyncio
    async def test_execute_streaming_with_multiple_react_steps(
        self,
        workflow_repository: SQLAlchemyWorkflowRepository,
        sample_workflow: Workflow,
    ):
        """测试：流式处理包含多个 ReAct 步骤的复杂场景

        RED 阶段：完整的多步骤流式工作流
        """
        mock_chat_service = AsyncMock(spec=EnhancedWorkflowChatService)

        # 创建 5 个不同的 react_steps
        react_steps = [
            {
                "step": 1,
                "thought": "分析需求：需要处理用户输入",
                "action": {"type": "add_node", "node": {"name": "input"}},
                "observation": "输入节点已添加",
            },
            {
                "step": 2,
                "thought": "需要数据验证",
                "action": {"type": "add_node", "node": {"name": "validate"}},
                "observation": "验证节点已添加",
            },
            {
                "step": 3,
                "thought": "需要处理逻辑",
                "action": {"type": "add_node", "node": {"name": "process"}},
                "observation": "处理节点已添加",
            },
            {
                "step": 4,
                "thought": "需要错误处理",
                "action": {"type": "add_node", "node": {"name": "error_handler"}},
                "observation": "错误处理节点已添加",
            },
            {
                "step": 5,
                "thought": "需要输出",
                "action": {"type": "add_node", "node": {"name": "output"}},
                "observation": "输出节点已添加",
            },
        ]

        mock_result = ModificationResult(
            success=True,
            ai_message="已完成完整工作流设计",
            intent="add_node",
            confidence=0.95,
            modifications_count=5,
            modified_workflow=sample_workflow,
            react_steps=react_steps,
        )
        mock_chat_service.process_message.return_value = mock_result

        use_case = UpdateWorkflowByChatUseCase(
            workflow_repository=workflow_repository,
            chat_service=mock_chat_service,
            save_validator=Mock(),
        )

        input_data = UpdateWorkflowByChatInput(
            workflow_id=sample_workflow.id,
            user_message="设计一个完整的数据处理流程",
        )

        events = []
        async for event in use_case.execute_streaming(input_data):
            events.append(event)

        # 验证 react_step 事件数量
        react_events = [e for e in events if e.get("type") == "react_step"]
        assert len(react_events) == 5, "应该有 5 个 react_step 事件"

        # 验证每个 react_step 的内容和顺序
        for i, react_event in enumerate(react_events, 1):
            assert react_event["step_number"] == i, f"步骤 {i} 的 step_number 应该正确"
            assert react_event["thought"], f"步骤 {i} 的 thought 不应该为空"
            assert react_event["observation"], f"步骤 {i} 的 observation 不应该为空"
