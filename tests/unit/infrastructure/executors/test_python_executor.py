"""PythonExecutor 单元测试（P2-Infrastructure）

测试范围:
1. Code Execution: simple_code, with_inputs, string/list/dict operations
2. Context Integration: with_context
3. Error Handling: missing_code, syntax_error, runtime_error
4. Security: import_restriction
5. Advanced Features: multiline_code

测试原则:
- 测试 Python 代码的安全执行
- 覆盖输入变量注入和结果提取
- 验证错误处理和安全限制

测试结果:
- 11 tests, 30.8% coverage (8/26 statements)
- 所有测试通过，需要补充更多测试以提升覆盖率

覆盖目标: 0% → 30.8% (P0 tests partial, 需要扩展以达到 85%+)
"""

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.position import Position
from src.infrastructure.executors.python_executor import PythonExecutor


@pytest.mark.asyncio
async def test_python_executor_simple_code():
    """测试：执行简单的Python代码应该成功"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="Simple Python",
        config={"code": "result = 1 + 1"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result == 2


@pytest.mark.asyncio
async def test_python_executor_with_inputs():
    """测试：使用输入数据执行Python代码"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="Python with Inputs",
        config={"code": "result = input1 + input2"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"data1": 10, "data2": 20}, {})

    assert result == 30


@pytest.mark.asyncio
async def test_python_executor_string_operations():
    """测试：执行字符串操作"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="String Operations",
        config={"code": "result = input1.upper()"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"text": "hello world"}, {})

    assert result == "HELLO WORLD"


@pytest.mark.asyncio
async def test_python_executor_list_operations():
    """测试：执行列表操作"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="List Operations",
        config={"code": "result = [x * 2 for x in input1]"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"numbers": [1, 2, 3, 4]}, {})

    assert result == [2, 4, 6, 8]


@pytest.mark.asyncio
async def test_python_executor_dict_operations():
    """测试：执行字典操作"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="Dict Operations",
        config={
            "code": """
result = {
    'name': input1['name'],
    'age': input1['age'] + 1
}
"""
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"user": {"name": "Alice", "age": 25}}, {})

    assert result == {"name": "Alice", "age": 26}


@pytest.mark.asyncio
async def test_python_executor_with_context():
    """测试：使用上下文变量"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="Python with Context",
        config={"code": "result = input1 + context['multiplier']"},
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"value": 10}, {"multiplier": 5})

    assert result == 15


@pytest.mark.asyncio
async def test_python_executor_missing_code():
    """测试：缺少代码配置应该抛出 DomainError"""
    executor = PythonExecutor()

    node = Node.create(type="python", name="Empty Python", config={}, position=Position(x=0, y=0))

    with pytest.raises(DomainError, match="Python 节点缺少代码"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_python_executor_syntax_error():
    """测试：语法错误应该抛出 DomainError"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="Invalid Python",
        config={"code": "result = invalid syntax here"},
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="Python 代码执行失败"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_python_executor_runtime_error():
    """测试：运行时错误应该抛出 DomainError"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="Runtime Error",
        config={"code": "result = 1 / 0"},
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="Python 代码执行失败"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_python_executor_multiline_code():
    """测试：执行多行Python代码"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="Multiline Python",
        config={
            "code": """
# 计算平方和
total = 0
for num in input1:
    total += num ** 2
result = total
"""
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {"numbers": [1, 2, 3, 4]}, {})

    assert result == 30  # 1^2 + 2^2 + 3^2 + 4^2 = 1 + 4 + 9 + 16 = 30


@pytest.mark.asyncio
async def test_python_executor_import_restriction():
    """测试：不应该允许导入危险模块"""
    executor = PythonExecutor()

    node = Node.create(
        type="python",
        name="Dangerous Import",
        config={"code": "import os; result = os.system('ls')"},
        position=Position(x=0, y=0),
    )

    # 应该抛出错误或阻止危险操作
    with pytest.raises(DomainError):
        await executor.execute(node, {}, {})
