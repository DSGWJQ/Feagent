"""LoopExecutor 单元测试

TDD 第一步：先写测试，定义期望的行为
"""

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.position import Position
from src.infrastructure.executors.loop_executor import LoopExecutor


@pytest.mark.asyncio
async def test_loop_executor_for_each():
    """测试：遍历数组的for循环应该成功"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="For Each Loop",
        config={
            "type": "for_each",
            "array": "items",
            "operation": "multiply",  # 每个元素乘以2
            "multiplier": 2,
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"data": {"items": [1, 2, 3, 4, 5]}}, {})

    assert len(result) == 5
    assert result == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_loop_executor_for_each_with_code():
    """测试：使用Python代码的for循环"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="For Each with Code",
        config={
            "type": "for_each",
            "array": "numbers",
            "code": "result = item * item",  # 计算平方
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"data": {"numbers": [1, 2, 3, 4]}}, {})

    assert result == [1, 4, 9, 16]


@pytest.mark.asyncio
async def test_loop_executor_for_each_with_index():
    """测试：带索引的for循环"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="For Each with Index",
        config={"type": "for_each", "array": "items", "code": "result = f'{index}: {item}'"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"data": {"items": ["a", "b", "c"]}}, {})

    assert result == ["0: a", "1: b", "2: c"]


@pytest.mark.asyncio
async def test_loop_executor_range():
    """测试：range循环应该成功"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="Range Loop",
        config={"type": "range", "start": 1, "end": 6, "step": 1, "code": "result = i * 2"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result == [2, 4, 6, 8, 10]


@pytest.mark.asyncio
async def test_loop_executor_range_with_step():
    """测试：带步长的range循环"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="Range with Step",
        config={"type": "range", "start": 0, "end": 10, "step": 2, "code": "result = i"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result == [0, 2, 4, 6, 8]


@pytest.mark.asyncio
async def test_loop_executor_while():
    """测试：while循环应该成功"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="While Loop",
        config={
            "type": "while",
            "condition": "counter < 5",
            "code": "counter = counter + 1; result = counter",
            "max_iterations": 10,
            "initial_vars": {"counter": 0},
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_loop_executor_while_max_iterations():
    """测试：while循环应该受最大迭代次数限制"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="While with Max",
        config={
            "type": "while",
            "condition": "True",  # 无限循环条件
            "code": "result = counter; counter = counter + 1",
            "max_iterations": 3,
            "initial_vars": {"counter": 0},
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    # 应该只执行3次
    assert len(result) == 3
    assert result == [0, 1, 2]


@pytest.mark.asyncio
async def test_loop_executor_for_each_with_filter():
    """测试：循环中过滤元素"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="For Each with Filter",
        config={
            "type": "for_each",
            "array": "numbers",
            "code": "result = item if item % 2 == 0 else None",
            "skip_none": True,  # 跳过None结果
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"data": {"numbers": [1, 2, 3, 4, 5, 6]}}, {})

    assert result == [2, 4, 6]


@pytest.mark.asyncio
async def test_loop_executor_nested_data():
    """测试：处理嵌套数据结构"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="Nested Data Loop",
        config={
            "type": "for_each",
            "array": "users",
            "code": "result = {'name': item['name'], 'age_next_year': item['age'] + 1}",
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(
        node, {"data": {"users": [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}]}}, {}
    )

    assert len(result) == 2
    assert result[0] == {"name": "Alice", "age_next_year": 26}
    assert result[1] == {"name": "Bob", "age_next_year": 31}


@pytest.mark.asyncio
async def test_loop_executor_missing_type():
    """测试：缺少循环类型应该抛出 DomainError"""
    executor = LoopExecutor()

    node = Node.create(type="loop", name="Invalid Loop", config={}, position=Position(x=0, y=0))

    with pytest.raises(DomainError, match="Loop 节点缺少循环类型"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_loop_executor_invalid_type():
    """测试：不支持的循环类型应该抛出 DomainError"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="Invalid Loop Type",
        config={"type": "unsupported_loop"},
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="不支持的循环类型"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_loop_executor_missing_array():
    """测试：for_each缺少数组应该抛出 DomainError"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop", name="Missing Array", config={"type": "for_each"}, position=Position(x=0, y=0)
    )

    with pytest.raises(DomainError, match="for_each 循环缺少 array 配置"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_loop_executor_code_error():
    """测试：循环代码执行错误应该抛出 DomainError"""
    executor = LoopExecutor()

    node = Node.create(
        type="loop",
        name="Code Error",
        config={"type": "for_each", "array": "items", "code": "result = undefined_variable"},
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError):
        await executor.execute(node, {"data": {"items": [1, 2, 3]}}, {})
