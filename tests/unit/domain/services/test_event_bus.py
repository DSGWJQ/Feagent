"""测试：事件总线 (EventBus)

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- EventBus 是多Agent协作系统的通信基础设施
- 对话Agent、工作流Agent、协调者Agent 通过事件进行解耦通信
- 这是 Phase 0 基础设施的核心组件

真实场景：
1. 对话Agent 做出决策 → 发布 DecisionMadeEvent
2. 协调者Agent 订阅该事件 → 验证决策合法性
3. 验证通过 → 发布 DecisionValidatedEvent
4. 工作流Agent 订阅该事件 → 执行决策创建节点
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime


class TestEventBusBasicPublishSubscribe:
    """测试事件总线基本发布订阅功能

    测试策略：
    1. 先测试最简单的发布订阅
    2. 再测试多订阅者场景
    3. 最后测试类型过滤
    """

    def test_subscribe_and_publish_event_should_deliver_to_handler(self):
        """测试：订阅事件后发布，处理器应该收到事件

        业务场景：
        - 协调者Agent订阅DecisionMadeEvent
        - 对话Agent发布决策事件
        - 协调者Agent的处理器应该被调用

        验收标准：
        - 处理器被调用一次
        - 处理器收到的事件与发布的事件相同
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        received_events: list[Event] = []

        async def handler(event: Event):
            received_events.append(event)

        # 创建一个测试事件
        @dataclass
        class TestEvent(Event):
            message: str = ""

        test_event = TestEvent(message="test decision")

        # Act
        event_bus.subscribe(TestEvent, handler)
        asyncio.run(event_bus.publish(test_event))

        # Assert
        assert len(received_events) == 1, "处理器应该被调用一次"
        assert received_events[0] == test_event, "收到的事件应该与发布的相同"
        assert received_events[0].message == "test decision"

    def test_multiple_subscribers_should_all_receive_event(self):
        """测试：多个订阅者都应该收到事件

        业务场景：
        - 协调者Agent和日志服务都订阅DecisionMadeEvent
        - 对话Agent发布决策事件
        - 两个订阅者都应该收到事件

        为什么需要这个测试？
        1. 真实场景中，一个事件可能有多个消费者
        2. 确保事件广播机制正确工作
        3. 各订阅者相互独立，互不影响

        验收标准：
        - 所有订阅者都收到事件
        - 收到的事件内容相同
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        receiver1_events: list[Event] = []
        receiver2_events: list[Event] = []

        async def handler1(event: Event):
            receiver1_events.append(event)

        async def handler2(event: Event):
            receiver2_events.append(event)

        @dataclass
        class TestEvent(Event):
            data: str = ""

        test_event = TestEvent(data="important data")

        # Act
        event_bus.subscribe(TestEvent, handler1)
        event_bus.subscribe(TestEvent, handler2)
        asyncio.run(event_bus.publish(test_event))

        # Assert
        assert len(receiver1_events) == 1, "第一个订阅者应该收到事件"
        assert len(receiver2_events) == 1, "第二个订阅者应该收到事件"
        assert receiver1_events[0] == receiver2_events[0], "两个订阅者收到的事件应该相同"

    def test_subscribe_specific_event_type_should_only_receive_that_type(self):
        """测试：订阅特定类型事件，只应该收到该类型

        业务场景：
        - 工作流Agent只订阅DecisionValidatedEvent
        - 系统发布DecisionMadeEvent和DecisionValidatedEvent
        - 工作流Agent只应该收到DecisionValidatedEvent

        为什么需要这个测试？
        1. 避免Agent收到不相关的事件
        2. 确保类型过滤机制正确工作
        3. 减少不必要的处理开销

        验收标准：
        - 只收到订阅类型的事件
        - 不收到其他类型的事件
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        received_events: list[Event] = []

        async def handler(event: Event):
            received_events.append(event)

        @dataclass
        class EventTypeA(Event):
            pass

        @dataclass
        class EventTypeB(Event):
            pass

        event_a = EventTypeA()
        event_b = EventTypeB()

        # Act - 只订阅 EventTypeA
        event_bus.subscribe(EventTypeA, handler)
        asyncio.run(event_bus.publish(event_a))
        asyncio.run(event_bus.publish(event_b))

        # Assert
        assert len(received_events) == 1, "只应该收到一个事件"
        assert isinstance(received_events[0], EventTypeA), "收到的应该是 EventTypeA"


class TestEventBusEventLogging:
    """测试事件总线的事件日志功能

    业务背景：
    - 所有事件需要记录日志，用于审计和调试
    - 可以回放事件历史
    """

    def test_published_events_should_be_logged(self):
        """测试：发布的事件应该被记录到日志

        业务场景：
        - 系统需要审计所有Agent的决策
        - 通过事件日志可以追溯问题

        验收标准：
        - 发布的事件被记录到event_log
        - 可以查询历史事件
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()

        @dataclass
        class AuditEvent(Event):
            action: str = ""

        event1 = AuditEvent(action="create_node")
        event2 = AuditEvent(action="execute_workflow")

        # Act
        asyncio.run(event_bus.publish(event1))
        asyncio.run(event_bus.publish(event2))

        # Assert
        assert len(event_bus.event_log) == 2, "应该记录2个事件"
        assert event_bus.event_log[0] == event1
        assert event_bus.event_log[1] == event2

    def test_event_should_have_id_and_timestamp(self):
        """测试：事件应该有唯一ID和时间戳

        业务场景：
        - 需要追踪事件的因果关系
        - 需要按时间排序事件

        验收标准：
        - 事件有唯一ID
        - 事件有时间戳
        - 时间戳是创建时间
        """
        # Arrange
        from src.domain.services.event_bus import Event

        # Act
        event = Event()

        # Assert
        assert event.id is not None, "事件必须有ID"
        assert len(event.id) > 0, "ID不能为空"
        assert event.timestamp is not None, "事件必须有时间戳"
        assert isinstance(event.timestamp, datetime), "时间戳必须是datetime类型"


class TestEventBusMiddleware:
    """测试事件总线的中间件功能

    业务背景：
    - 协调者Agent需要拦截决策事件进行验证
    - 验证失败时需要阻止事件继续传播
    - 中间件是实现这个功能的核心机制
    """

    def test_middleware_should_process_event_before_handlers(self):
        """测试：中间件应该在处理器之前处理事件

        业务场景：
        - 协调者Agent作为中间件拦截DecisionMadeEvent
        - 先验证决策合法性
        - 验证通过后事件才传递给其他订阅者

        验收标准：
        - 中间件先于处理器执行
        - 中间件可以修改事件
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        execution_order: list[str] = []

        async def middleware(event: Event) -> Event:
            execution_order.append("middleware")
            return event

        async def handler(event: Event):
            execution_order.append("handler")

        @dataclass
        class TestEvent(Event):
            pass

        # Act
        event_bus.add_middleware(middleware)
        event_bus.subscribe(TestEvent, handler)
        asyncio.run(event_bus.publish(TestEvent()))

        # Assert
        assert execution_order == ["middleware", "handler"], "中间件应该先于处理器执行"

    def test_middleware_can_block_event_propagation(self):
        """测试：中间件可以阻止事件传播

        业务场景：
        - 协调者Agent验证决策
        - 如果决策违反规则，阻止事件传播
        - 工作流Agent不应该收到被拒绝的决策

        为什么需要这个测试？
        1. 这是协调者Agent纠偏的核心机制
        2. 确保非法决策不会被执行
        3. 保护系统安全

        验收标准：
        - 中间件返回None时，事件不传播
        - 处理器不会被调用
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        handler_called = False

        async def blocking_middleware(event: Event) -> Event | None:
            # 模拟验证失败，阻止事件传播
            return None

        async def handler(event: Event):
            nonlocal handler_called
            handler_called = True

        @dataclass
        class TestEvent(Event):
            pass

        # Act
        event_bus.add_middleware(blocking_middleware)
        event_bus.subscribe(TestEvent, handler)
        asyncio.run(event_bus.publish(TestEvent()))

        # Assert
        assert handler_called is False, "中间件阻止后，处理器不应该被调用"

    def test_multiple_middlewares_should_chain_in_order(self):
        """测试：多个中间件应该按顺序链式执行

        业务场景：
        - 先执行格式验证中间件
        - 再执行权限验证中间件
        - 最后执行日志中间件

        验收标准：
        - 中间件按添加顺序执行
        - 前一个中间件的输出是后一个的输入
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        execution_order: list[str] = []

        async def middleware1(event: Event) -> Event:
            execution_order.append("middleware1")
            return event

        async def middleware2(event: Event) -> Event:
            execution_order.append("middleware2")
            return event

        async def middleware3(event: Event) -> Event:
            execution_order.append("middleware3")
            return event

        @dataclass
        class TestEvent(Event):
            pass

        # Act
        event_bus.add_middleware(middleware1)
        event_bus.add_middleware(middleware2)
        event_bus.add_middleware(middleware3)
        asyncio.run(event_bus.publish(TestEvent()))

        # Assert
        assert execution_order == ["middleware1", "middleware2", "middleware3"]


class TestEventBusCorrelation:
    """测试事件关联功能

    业务背景：
    - 需要追踪事件的因果关系
    - DecisionValidatedEvent 应该关联到原始的 DecisionMadeEvent
    """

    def test_event_can_have_correlation_id(self):
        """测试：事件可以有关联ID

        业务场景：
        - DecisionMadeEvent 发布后生成ID
        - DecisionValidatedEvent 通过correlation_id关联到原始事件
        - 便于追踪决策的完整生命周期

        验收标准：
        - 事件可以设置correlation_id
        - 可以通过correlation_id查找相关事件
        """
        # Arrange
        from src.domain.services.event_bus import Event

        original_event = Event()
        original_id = original_event.id

        # Act - 创建关联事件
        correlated_event = Event(correlation_id=original_id)

        # Assert
        assert correlated_event.correlation_id == original_id


class TestEventBusRealWorldScenario:
    """测试真实业务场景

    这是最重要的测试类，验证事件总线在实际Agent协作中的工作方式
    """

    def test_decision_flow_from_conversation_to_workflow_agent(self):
        """测试：决策从对话Agent流转到工作流Agent的完整流程

        业务场景：
        1. 对话Agent做出决策，发布DecisionMadeEvent
        2. 协调者Agent（中间件）验证决策
        3. 验证通过，发布DecisionValidatedEvent
        4. 工作流Agent收到验证后的决策，执行操作

        这是多Agent协作系统的核心流程！

        验收标准：
        - 对话Agent可以发布决策事件
        - 协调者可以验证并转发
        - 工作流Agent可以收到验证后的事件
        - 整个流程异步、解耦
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()

        # 定义业务事件
        @dataclass
        class DecisionMadeEvent(Event):
            decision_type: str = ""
            payload: dict = field(default_factory=dict)

        @dataclass
        class DecisionValidatedEvent(Event):
            original_decision_id: str = ""
            is_valid: bool = True

        # 记录各Agent收到的事件
        coordinator_received: list[Event] = []
        workflow_agent_received: list[Event] = []

        # 协调者Agent作为中间件验证决策
        async def coordinator_middleware(event: Event) -> Event | None:
            if isinstance(event, DecisionMadeEvent):
                coordinator_received.append(event)
                # 模拟验证通过，发布验证事件
                validated_event = DecisionValidatedEvent(
                    original_decision_id=event.id, is_valid=True, correlation_id=event.id
                )
                await event_bus.publish(validated_event)
            return event  # 继续传播原始事件

        # 工作流Agent订阅验证后的决策
        async def workflow_agent_handler(event: DecisionValidatedEvent):
            workflow_agent_received.append(event)

        # Act
        event_bus.add_middleware(coordinator_middleware)
        event_bus.subscribe(DecisionValidatedEvent, workflow_agent_handler)

        # 对话Agent发布决策
        decision = DecisionMadeEvent(
            decision_type="create_node", payload={"node_type": "llm", "config": {"model": "gpt-4"}}
        )
        asyncio.run(event_bus.publish(decision))

        # Assert
        assert len(coordinator_received) == 1, "协调者应该收到决策事件"
        assert coordinator_received[0].decision_type == "create_node"

        assert len(workflow_agent_received) == 1, "工作流Agent应该收到验证事件"
        assert workflow_agent_received[0].is_valid is True
        assert workflow_agent_received[0].original_decision_id == decision.id

    def test_blocked_decision_should_not_reach_workflow_agent(self):
        """测试：被阻止的决策不应该到达工作流Agent

        业务场景：
        - 对话Agent做出了违规决策
        - 协调者Agent验证失败，阻止决策
        - 工作流Agent不应该收到任何事件

        这是协调者Agent纠偏功能的核心验证！

        验收标准：
        - 协调者收到原始决策
        - 决策被阻止，不发布验证事件
        - 工作流Agent不收到任何事件
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()

        @dataclass
        class DecisionMadeEvent(Event):
            decision_type: str = ""

        @dataclass
        class DecisionRejectedEvent(Event):
            original_decision_id: str = ""
            reason: str = ""

        coordinator_received: list[Event] = []
        rejection_received: list[Event] = []

        # 协调者拒绝决策
        async def coordinator_middleware(event: Event) -> Event | None:
            if isinstance(event, DecisionMadeEvent):
                coordinator_received.append(event)
                # 模拟验证失败，发布拒绝事件
                rejected_event = DecisionRejectedEvent(
                    original_decision_id=event.id,
                    reason="决策违反安全规则",
                    correlation_id=event.id,
                )
                await event_bus.publish(rejected_event)
                return None  # 阻止原始事件继续传播
            return event

        async def rejection_handler(event: DecisionRejectedEvent):
            rejection_received.append(event)

        # Act
        event_bus.add_middleware(coordinator_middleware)
        event_bus.subscribe(DecisionRejectedEvent, rejection_handler)

        decision = DecisionMadeEvent(decision_type="dangerous_action")
        asyncio.run(event_bus.publish(decision))

        # Assert
        assert len(coordinator_received) == 1, "协调者应该收到决策"
        assert len(rejection_received) == 1, "应该收到拒绝事件"
        assert rejection_received[0].reason == "决策违反安全规则"


class TestEventBusErrorHandling:
    """测试错误处理

    业务背景：
    - 处理器可能抛出异常
    - 异常不应该影响其他处理器
    - 异常应该被记录
    """

    def test_handler_exception_should_not_affect_other_handlers(self):
        """测试：处理器异常不应该影响其他处理器

        业务场景：
        - 多个Agent订阅同一事件
        - 其中一个Agent处理出错
        - 其他Agent应该正常收到事件

        验收标准：
        - 一个处理器抛出异常
        - 其他处理器仍然被调用
        - 异常被捕获，不会导致程序崩溃
        """
        # Arrange
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        handler2_called = False

        async def failing_handler(event: Event):
            raise ValueError("模拟处理器错误")

        async def normal_handler(event: Event):
            nonlocal handler2_called
            handler2_called = True

        @dataclass
        class TestEvent(Event):
            pass

        # Act
        event_bus.subscribe(TestEvent, failing_handler)
        event_bus.subscribe(TestEvent, normal_handler)

        # 不应该抛出异常
        asyncio.run(event_bus.publish(TestEvent()))

        # Assert
        assert handler2_called is True, "正常处理器应该被调用"

    def test_unsubscribe_nonexistent_event_type_should_return_false(self):
        """测试：取消订阅不存在的事件类型应返回False

        覆盖 event_bus.py:154-155 (event_type not in _subscribers)
        """
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()

        @dataclass
        class UnsubscribedEvent(Event):
            pass

        async def handler(event: Event):
            pass

        # Act: 尝试取消订阅从未订阅的事件类型
        result = event_bus.unsubscribe(UnsubscribedEvent, handler)

        # Assert
        assert result is False, "取消订阅不存在的事件类型应返回False"

    def test_unsubscribe_existing_handler_should_return_true(self):
        """测试：取消订阅已存在的处理器应返回True

        覆盖 event_bus.py:157-163 (handler in handlers, remove and return True)
        """
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        handler_called = False

        @dataclass
        class TestEvent(Event):
            pass

        async def handler(event: Event):
            nonlocal handler_called
            handler_called = True

        # Arrange: 先订阅
        event_bus.subscribe(TestEvent, handler)

        # Act: 取消订阅
        result = event_bus.unsubscribe(TestEvent, handler)

        # Assert
        assert result is True, "取消订阅已存在的处理器应返回True"

        # 验证：发布事件后处理器不应被调用
        asyncio.run(event_bus.publish(TestEvent()))
        assert handler_called is False, "取消订阅后处理器不应被调用"

    def test_middleware_exception_should_block_event_propagation(self):
        """测试：中间件抛出异常应阻止事件传播

        覆盖 event_bus.py:244-247 (middleware exception handling)

        业务场景：
        - 协调者Agent的验证中间件抛出异常
        - 事件不应该被记录到日志
        - 订阅者不应该收到事件
        """
        from src.domain.services.event_bus import Event, EventBus

        event_bus = EventBus()
        handler_called = False

        async def failing_middleware(event: Event):
            raise RuntimeError("中间件验证失败")

        async def handler(event: Event):
            nonlocal handler_called
            handler_called = True

        @dataclass
        class TestEvent(Event):
            pass

        # Arrange
        event_bus.add_middleware(failing_middleware)
        event_bus.subscribe(TestEvent, handler)

        # Act
        asyncio.run(event_bus.publish(TestEvent()))

        # Assert
        assert handler_called is False, "中间件异常应阻止事件到达订阅者"
        assert len(event_bus.event_log) == 0, "中间件异常应阻止事件记录到日志"
