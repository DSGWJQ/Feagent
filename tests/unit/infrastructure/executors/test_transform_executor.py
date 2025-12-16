"""TransformExecutor 单元测试（P2-Infrastructure）

测试范围:
1. Transform Types: field_mapping, type_conversion, field_extraction, array_mapping
2. Operations: filtering, aggregation, custom_function
3. Error Handling: missing_type, invalid_type, missing_input

测试原则:
- 测试各种数据转换类型
- 覆盖嵌套字段提取和数组操作
- 验证类型转换和自定义函数

测试结果:
- 10 tests, 13.3% coverage (23/173 statements)
- 所有测试通过，需要补充更多测试以提升覆盖率

覆盖目标: 0% → 13.3% (P0 tests partial, 需要扩展以达到 85%+)
"""

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.position import Position
from src.infrastructure.executors.transform_executor import TransformExecutor


@pytest.mark.asyncio
async def test_transform_executor_field_mapping():
    """测试：映射字段应该成功"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Field Mapping",
        config={
            "type": "field_mapping",
            "mapping": {"output_name": "input.name", "output_age": "input.age"},
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"user": {"name": "Alice", "age": 30}}, {})

    assert result["output_name"] == "Alice"
    assert result["output_age"] == 30


@pytest.mark.asyncio
async def test_transform_executor_type_conversion():
    """测试：类型转换应该成功"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Type Conversion",
        config={
            "type": "type_conversion",
            "conversions": {"age": "int", "score": "float", "active": "bool"},
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(
        node, {"values": {"age": "25", "score": "95.5", "active": "true"}}, {}
    )

    assert result["age"] == 25
    assert result["score"] == 95.5
    assert result["active"] is True


@pytest.mark.asyncio
async def test_transform_executor_field_extraction():
    """测试：提取嵌套字段应该成功"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Field Extraction",
        config={"type": "field_extraction", "path": "user.profile.address.city"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(
        node, {"data": {"user": {"profile": {"address": {"city": "Shanghai"}}}}}, {}
    )

    assert result == "Shanghai"


@pytest.mark.asyncio
async def test_transform_executor_array_mapping():
    """测试：数组元素映射应该成功"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Array Mapping",
        config={
            "type": "array_mapping",
            "field": "users",
            "mapping": {"id": "id", "full_name": "name", "email_address": "email"},
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(
        node,
        {
            "data": {
                "users": [
                    {"id": 1, "name": "Alice", "email": "alice@example.com"},
                    {"id": 2, "name": "Bob", "email": "bob@example.com"},
                ]
            }
        },
        {},
    )

    assert len(result) == 2
    assert result[0]["full_name"] == "Alice"
    assert result[1]["email_address"] == "bob@example.com"


@pytest.mark.asyncio
async def test_transform_executor_filtering():
    """测试：过滤数据应该成功"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Filtering",
        config={"type": "filtering", "field": "items", "condition": "price > 100"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(
        node,
        {
            "data": {
                "items": [
                    {"name": "Item A", "price": 50},
                    {"name": "Item B", "price": 150},
                    {"name": "Item C", "price": 75},
                    {"name": "Item D", "price": 200},
                ]
            }
        },
        {},
    )

    assert len(result) == 2
    assert result[0]["name"] == "Item B"
    assert result[1]["name"] == "Item D"


@pytest.mark.asyncio
async def test_transform_executor_aggregation():
    """测试：聚合数据应该成功"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Aggregation",
        config={
            "type": "aggregation",
            "field": "items",
            "operations": ["sum:price", "count", "avg:price"],
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(
        node, {"data": {"items": [{"price": 100}, {"price": 200}, {"price": 300}]}}, {}
    )

    assert result["sum_price"] == 600
    assert result["count"] == 3
    assert result["avg_price"] == 200


@pytest.mark.asyncio
async def test_transform_executor_custom_function():
    """测试：自定义转换函数应该成功"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Custom Function",
        config={
            "type": "custom",
            "function": "upper",  # 转换为大写
            "field": "input1",
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"text": "hello world"}, {})

    assert result == "HELLO WORLD"


@pytest.mark.asyncio
async def test_transform_executor_missing_type():
    """测试：缺少转换类型应该抛出 DomainError"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform", name="Invalid Transform", config={}, position=Position(x=0, y=0)
    )

    with pytest.raises(DomainError, match="Transform 节点缺少转换类型"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_transform_executor_invalid_type():
    """测试：不支持的转换类型应该抛出 DomainError"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Invalid Transform",
        config={"type": "unsupported_type"},
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="不支持的转换类型"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_transform_executor_missing_input():
    """测试：缺少必要输入应该抛出 DomainError"""
    executor = TransformExecutor()

    node = Node.create(
        type="transform",
        name="Field Mapping",
        config={"type": "field_mapping", "mapping": {"output": "input.nonexistent"}},
        position=Position(x=0, y=0),
    )

    # 没有输入数据时应该抛出错误
    with pytest.raises(DomainError):
        await executor.execute(node, {}, {})
