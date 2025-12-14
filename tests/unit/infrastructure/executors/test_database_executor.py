"""DatabaseExecutor 单元测试"""

import os
import sqlite3
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.position import Position
from src.infrastructure.executors.database_executor import DatabaseExecutor


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试

    使用UUID生成唯一的数据库文件名，避免并行测试时的数据库锁冲突。
    每个测试实例使用独立的数据库文件，确保测试隔离。
    """
    temp_dir = tempfile.gettempdir()
    # 使用UUID生成唯一的数据库文件名，避免并行冲突
    db_path = Path(temp_dir) / f"test_database_executor_{uuid4().hex}.db"

    # 创建数据库和测试表
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        )
    """)
    cursor.execute("INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')")
    cursor.execute("INSERT INTO users (id, name, email) VALUES (2, 'Bob', 'bob@example.com')")
    conn.commit()
    conn.close()

    yield f"sqlite:///{db_path}"

    # 清理：使用重试机制处理Windows文件锁问题
    # 等待数据库连接完全关闭后再删除文件
    if db_path.exists():
        for attempt in range(3):
            try:
                time.sleep(0.1)  # 短暂延迟确保连接关闭
                os.remove(db_path)
                break
            except PermissionError:
                if attempt == 2:
                    # 最后一次尝试失败，忽略错误（临时文件会在系统重启时清理）
                    pass
                time.sleep(0.2)


@pytest.mark.asyncio
async def test_database_executor_select_query(temp_db):
    """测试：SELECT 查询应该返回结果列表"""
    executor = DatabaseExecutor()
    node = Node.create(
        type="database",
        name="Query User",
        config={
            "database_url": temp_db,
            "sql": "SELECT * FROM users WHERE id = ?",
            "params": [1],
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["name"] == "Alice"
    assert result[0]["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_database_executor_select_all(temp_db):
    """测试：SELECT 查询所有记录"""
    executor = DatabaseExecutor()
    node = Node.create(
        type="database",
        name="Query All Users",
        config={
            "database_url": temp_db,
            "sql": "SELECT * FROM users",
            "params": [],
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_database_executor_insert(temp_db):
    """测试：INSERT 操作应该返回影响的行数"""
    executor = DatabaseExecutor()
    node = Node.create(
        type="database",
        name="Insert User",
        config={
            "database_url": temp_db,
            "sql": "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            "params": [3, "Charlie", "charlie@example.com"],
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result["rows_affected"] == 1


@pytest.mark.asyncio
async def test_database_executor_update(temp_db):
    """测试：UPDATE 操作应该返回影响的行数"""
    executor = DatabaseExecutor()
    node = Node.create(
        type="database",
        name="Update User",
        config={
            "database_url": temp_db,
            "sql": "UPDATE users SET email = ? WHERE id = ?",
            "params": ["newemail@example.com", 1],
        },
        position=Position(x=0, y=0),
    )

    result = await executor.execute(node, {}, {})

    assert result["rows_affected"] == 1


@pytest.mark.asyncio
async def test_database_executor_missing_sql():
    """测试：缺少 SQL 配置应该抛出 DomainError"""
    executor = DatabaseExecutor()
    node = Node.create(
        type="database",
        name="Test Node",
        config={
            "database_url": "sqlite:///test.db",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="数据库节点缺少 SQL 语句"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_database_executor_unsupported_database():
    """测试：不支持的数据库类型应该抛出 DomainError"""
    executor = DatabaseExecutor()
    node = Node.create(
        type="database",
        name="Test Node",
        config={
            "database_url": "postgresql://localhost/test",
            "sql": "SELECT 1",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="不支持的数据库类型"):
        await executor.execute(node, {}, {})


@pytest.mark.asyncio
async def test_database_executor_invalid_sql(temp_db):
    """测试：无效的 SQL 应该抛出 DomainError"""
    executor = DatabaseExecutor()
    node = Node.create(
        type="database",
        name="Test Node",
        config={
            "database_url": temp_db,
            "sql": "INVALID SQL STATEMENT",
        },
        position=Position(x=0, y=0),
    )

    with pytest.raises(DomainError, match="数据库查询失败"):
        await executor.execute(node, {}, {})
