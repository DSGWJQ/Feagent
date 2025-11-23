"""FileExecutor 单元测试"""

import tempfile
from pathlib import Path

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.position import Position
from src.infrastructure.executors.file_executor import FileExecutor


@pytest.fixture
def temp_dir():
    """创建临时目录用于测试"""
    temp_dir = Path(tempfile.gettempdir()) / "file_executor_test"
    temp_dir.mkdir(exist_ok=True)

    yield temp_dir

    # 清理
    import shutil

    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_file_executor_write(temp_dir):
    """测试：写入文件应该成功"""
    executor = FileExecutor()
    file_path = temp_dir / "test.txt"

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
async def test_file_executor_read(temp_dir):
    """测试：读取文件应该返回内容"""
    executor = FileExecutor()
    file_path = temp_dir / "test.txt"
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
async def test_file_executor_append(temp_dir):
    """测试：追加内容到文件"""
    executor = FileExecutor()
    file_path = temp_dir / "test.txt"
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
async def test_file_executor_delete(temp_dir):
    """测试：删除文件"""
    executor = FileExecutor()
    file_path = temp_dir / "test.txt"
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
async def test_file_executor_list_directory(temp_dir):
    """测试：列出目录内容"""
    executor = FileExecutor()

    # 创建一些文件
    (temp_dir / "file1.txt").write_text("content1")
    (temp_dir / "file2.txt").write_text("content2")
    (temp_dir / "subdir").mkdir(exist_ok=True)

    node = Node.create(
        type="file",
        name="List Directory",
        config={
            "operation": "list",
            "path": str(temp_dir),
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result["operation"] == "list"
    assert result["count"] == 3
    assert any(item["name"] == "file1.txt" for item in result["items"])


@pytest.mark.asyncio
async def test_file_executor_read_nonexistent():
    """测试：读取不存在的文件应该抛出 DomainError"""
    executor = FileExecutor()

    node = Node.create(
        type="file",
        name="Read File",
        config={
            "operation": "read",
            "path": "/nonexistent/path/file.txt",
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
async def test_file_executor_invalid_operation():
    """测试：无效的操作应该抛出 DomainError"""
    executor = FileExecutor()

    node = Node.create(
        type="file",
        name="Test File",
        config={
            "operation": "invalid_op",
            "path": "/tmp/test.txt",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="不支持的文件操作"):
        await executor.execute(node, {}, {})
