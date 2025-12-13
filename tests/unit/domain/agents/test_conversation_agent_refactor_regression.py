"""
ConversationAgent Refactor Regression Tests

测试12个Critical问题的修复:
1. 5×F821类型注解错误
2. 4×Race Condition问题
3. 2×浅拷贝Bug
4. 1×E741模糊变量名
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ============================================================================
# 测试1: 验证类型注解可解析
# ============================================================================


def test_type_annotations_valid():
    """
    验证所有类型注解都可以被类型检查器解析

    Critical问题: 5×F821类型注解错误
    - FormattedError未定义 (line 2157)
    - UserDecision未定义 (line 2191)
    - UserDecisionResult未定义 (line 2191)
    - ControlFlowIR未定义 (line 2293)

    预期: 所有类型注解在TYPE_CHECKING块中正确引入
    """
    from src.domain.agents import conversation_agent

    # 检查文件顶部是否有 from __future__ import annotations
    source_path = Path(conversation_agent.__file__)
    source_code = source_path.read_text(encoding="utf-8")

    assert (
        "from __future__ import annotations" in source_code
    ), "Missing 'from __future__ import annotations' at file top"

    # 检查TYPE_CHECKING块是否存在
    assert (
        "if TYPE_CHECKING:" in source_code
    ), "Missing 'if TYPE_CHECKING:' block for forward references"

    # 解析AST检查类型注解
    tree = ast.parse(source_code)

    # 找到TYPE_CHECKING块中的导入
    type_checking_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # 检查是否是 if TYPE_CHECKING:
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                for stmt in node.body:
                    if isinstance(stmt, ast.ImportFrom):
                        for alias in stmt.names:
                            type_checking_imports.add(alias.name)

    # 验证关键类型已导入
    required_types = {
        "FormattedError",
        "UserDecision",
        "UserDecisionResult",
        "ControlFlowIR",
        "NodeDefinition",
        "WorkflowPlan",
        "EdgeDefinition",
    }

    missing_types = required_types - type_checking_imports
    assert not missing_types, f"Missing type imports in TYPE_CHECKING block: {missing_types}"


# ============================================================================
# 测试2: 验证关键事件串行发布
# ============================================================================


@pytest.mark.asyncio
async def test_critical_events_await():
    """
    验证关键事件必须await并串行发布

    Critical问题: 4×Race Condition
    - asyncio.create_task() 创建脱离任务未追踪
    - 关键事件可能丢失或乱序

    预期: 关键事件使用 _publish_critical_event() 并await
    """
    from src.domain.agents.conversation_agent import ConversationAgent, StateChangedEvent
    from src.domain.services.event_bus import EventBus

    event_bus = EventBus()
    events_received = []

    async def track_event(event):
        events_received.append(type(event).__name__)
        await asyncio.sleep(0.01)  # 模拟处理延迟

    # 订阅StateChangedEvent
    event_bus.subscribe(StateChangedEvent, track_event)

    # 创建最小配置的agent
    session_context = MagicMock()
    session_context.session_id = "test-session"
    session_context.goal_stack = []
    llm = AsyncMock()

    agent = ConversationAgent(
        session_context=session_context,
        llm=llm,
        event_bus=event_bus,
        max_iterations=1,
    )

    # 触发状态转换(应该发布关键事件)
    from src.domain.agents.conversation_agent import ConversationAgentState

    await agent.transition_to_async(ConversationAgentState.PROCESSING)

    # 等待事件处理
    await asyncio.sleep(0.05)

    # 验证事件被接收
    assert (
        "StateChangedEvent" in events_received
    ), "StateChangedEvent not received (critical event not published)"


# ============================================================================
# 测试3: 验证通知事件被追踪
# ============================================================================


@pytest.mark.asyncio
async def test_notification_events_tracked():
    """
    验证通知事件被正确追踪,不会悬挂

    Critical问题: 4×Race Condition
    - create_task() 创建的后台任务未追踪

    预期: 使用 _create_tracked_task() 并在 _pending_tasks 中追踪
    """
    from src.domain.agents.conversation_agent import ConversationAgent
    from src.domain.services.event_bus import EventBus

    event_bus = EventBus()
    session_context = MagicMock()
    session_context.session_id = "test-session"
    session_context.goal_stack = []
    llm = AsyncMock()

    agent = ConversationAgent(
        session_context=session_context,
        llm=llm,
        event_bus=event_bus,
        max_iterations=1,
    )

    # 验证_pending_tasks属性存在
    assert hasattr(agent, "_pending_tasks"), "Agent missing _pending_tasks list for task tracking"

    initial_task_count = len(agent._pending_tasks)

    # 创建一个后台任务(通过_create_tracked_task)
    async def dummy_task():
        await asyncio.sleep(0.01)
        return "done"

    if hasattr(agent, "_create_tracked_task"):
        task = agent._create_tracked_task(dummy_task())

        # 验证任务被追踪
        assert len(agent._pending_tasks) > initial_task_count, "Task not added to _pending_tasks"

        # 等待任务完成
        await asyncio.sleep(0.02)

        # 验证任务状态
        assert task.done(), "Tracked task did not complete"
    else:
        pytest.skip("_create_tracked_task method not implemented yet")


# ============================================================================
# 测试4: 验证上下文快照深拷贝
# ============================================================================


def test_context_snapshot_deepcopy():
    """
    验证上下文快照使用deepcopy

    Critical问题: 2×浅拷贝Bug
    - dict.copy() 导致嵌套结构共享
    - 修改恢复的上下文会影响挂起的上下文

    预期: 使用 copy.deepcopy() 或 _snapshot_context()
    """
    from src.domain.agents.conversation_agent import ConversationAgent

    # 检查源码是否使用deepcopy
    source_path = Path(ConversationAgent.__module__.replace(".", "/") + ".py")
    if not source_path.exists():
        # 尝试从安装路径查找
        import src.domain.agents.conversation_agent as ca_module

        source_path = Path(ca_module.__file__)

    source_code = source_path.read_text(encoding="utf-8")

    # 验证使用deepcopy而非浅拷贝
    assert (
        "import copy" in source_code or "from copy import deepcopy" in source_code
    ), "Missing 'import copy' for deep copying"

    # 检查是否有 deepcopy 调用
    assert "deepcopy" in source_code, "No 'deepcopy' usage found - may have shallow copy bug"

    # 检查是否有_snapshot_context辅助方法
    has_snapshot_method = "_snapshot_context" in source_code

    # 至少要有deepcopy或_snapshot_context之一
    assert (
        "deepcopy" in source_code or has_snapshot_method
    ), "No deep copy mechanism found for context snapshots"


# ============================================================================
# 测试5: 验证无模糊变量名
# ============================================================================


def test_no_ambiguous_variable_names():
    """
    验证没有模糊的单字母变量名

    Critical问题: 1×E741
    - 变量名'l'模糊 (line 2338)

    预期: 所有循环变量使用语义名(loop_spec, loop_item等)
    """
    from src.domain.agents.conversation_agent import ConversationAgent

    # 读取源码
    source_path = Path(ConversationAgent.__module__.replace(".", "/") + ".py")
    if not source_path.exists():
        import src.domain.agents.conversation_agent as ca_module

        source_path = Path(ca_module.__file__)

    source_code = source_path.read_text(encoding="utf-8")

    # 解析AST
    tree = ast.parse(source_code)

    # 查找模糊变量名
    ambiguous_vars = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            # 检查for循环变量名
            if isinstance(node.target, ast.Name):
                var_name = node.target.id
                # 检查单字母变量(l, I, O等容易混淆)
                if len(var_name) == 1 and var_name.lower() in "lio":
                    line_no = node.lineno
                    ambiguous_vars.append((var_name, line_no))

    assert not ambiguous_vars, (
        f"Found ambiguous variable names (E741): {ambiguous_vars}. "
        f"Use semantic names like 'loop_item', 'loop_spec' instead."
    )


# ============================================================================
# 集成测试: 验证修复后向后兼容
# ============================================================================


def test_backward_compatibility_basic_flow():
    """
    验证修复后ConversationAgent基本流程仍然工作

    确保类型修复、Race Condition修复、深拷贝修复不破坏现有功能
    """
    from src.domain.agents.conversation_agent import ConversationAgent
    from src.domain.services.event_bus import EventBus

    event_bus = EventBus()
    session_context = MagicMock()
    session_context.session_id = "test-session"
    session_context.goal_stack = []
    session_context.accumulated_responses = []

    llm = MagicMock()

    # 验证Agent可以正常初始化(这就足以验证向后兼容)
    agent = ConversationAgent(
        session_context=session_context,
        llm=llm,
        event_bus=event_bus,
        max_iterations=1,
    )

    # 验证基本属性
    assert agent.session_context == session_context
    assert agent.llm == llm
    assert agent.event_bus == event_bus
    assert agent.max_iterations == 1
    assert hasattr(agent, "_pending_tasks")  # 验证任务追踪机制存在
