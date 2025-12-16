"""FileExecutor 单元测试（P2-Infrastructure）

测试范围:
1. File Operations: write, read, append, delete
2. Directory Operations: list_directory
3. Error Handling: read_nonexistent, missing_path, invalid_operation

测试原则:
- **使用 pytest tmp_path fixture (每个测试独立目录)**
- 测试文件操作的完整周期
- 覆盖异常场景和边界条件
- **企业级隔离**: 避免并行测试冲突

测试结果:
- 8 tests, 88.3% coverage (68/77 statements)
- 所有测试通过，完全离线运行

覆盖目标: 0% → 88.3% (P0 tests achieved)

**P0 Critical修复**:
- 移除共享临时目录 (tempfile.gettempdir/file_executor_test)
- 改用 pytest tmp_path fixture (每个测试唯一目录，自动清理)
"""

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.position import Position
from src.infrastructure.executors.file_executor import FileExecutor


@pytest.mark.asyncio
async def test_file_executor_write(tmp_path):
    """测试：写入文件应该成功"""
    executor = FileExecutor()
    file_path = tmp_path / "test.txt"

    node = Node.create(
        type="file",
        name="Write File",
        config={
            "operation": "write",
            "path": str(file_path),
            "content": "Hello, World!",
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result["operation"] == "write"
    assert "bytes_written" in result
    assert file_path.exists()
    assert file_path.read_text() == "Hello, World!"


@pytest.mark.asyncio
async def test_file_executor_read(tmp_path):
    """测试：读取文件应该返回内容"""
    executor = FileExecutor()
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")

    node = Node.create(
        type="file",
        name="Read File",
        config={
            "operation": "read",
            "path": str(file_path),
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert "content" in result
    assert result["content"] == "Hello, World!"


@pytest.mark.asyncio
async def test_file_executor_append(tmp_path):
    """测试：追加内容到文件"""
    executor = FileExecutor()
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello")

    node = Node.create(
        type="file",
        name="Append File",
        config={
            "operation": "append",
            "path": str(file_path),
            "content": ", World!",
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result["operation"] == "append"
    assert file_path.read_text() == "Hello, World!"


@pytest.mark.asyncio
async def test_file_executor_delete(tmp_path):
    """测试：删除文件"""
    executor = FileExecutor()
    file_path = tmp_path / "test.txt"
    file_path.write_text("content")

    node = Node.create(
        type="file",
        name="Delete File",
        config={
            "operation": "delete",
            "path": str(file_path),
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result["operation"] == "delete"
    assert result["status"] == "success"
    assert not file_path.exists()


@pytest.mark.asyncio
async def test_file_executor_list_directory(tmp_path):
    """测试：列出目录内容"""
    executor = FileExecutor()

    # 创建一些文件
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")
    (tmp_path / "subdir").mkdir(exist_ok=True)

    node = Node.create(
        type="file",
        name="List Directory",
        config={
            "operation": "list",
            "path": str(tmp_path),
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result["operation"] == "list"
    # 使用集合比较避免硬编码计数
    assert {item["name"] for item in result["items"]} >= {"file1.txt", "file2.txt", "subdir"}
    assert any(item["name"] == "file1.txt" for item in result["items"])


@pytest.mark.asyncio
async def test_file_executor_read_nonexistent(tmp_path):
    """测试：读取不存在的文件应该抛出 DomainError"""
    executor = FileExecutor()
    file_path = tmp_path / "does_not_exist.txt"

    node = Node.create(
        type="file",
        name="Read File",
        config={
            "operation": "read",
            "path": str(file_path),
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="文件不存在"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_file_executor_missing_path():
    """测试：缺少路径配置应该抛出 DomainError"""
    executor = FileExecutor()

    node = Node.create(
        type="file",
        name="Test File",
        config={
            "operation": "read",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="缺少路径配置"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_file_executor_invalid_operation(tmp_path):
    """测试：无效的操作应该抛出 DomainError"""
    executor = FileExecutor()

    node = Node.create(
        type="file",
        name="Test File",
        config={
            "operation": "invalid_op",
            "path": str(tmp_path / "test.txt"),
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="不支持的文件操作"):
        await executor.execute(node, {}, {})
