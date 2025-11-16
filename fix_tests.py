"""修复测试文件：将异步测试改为同步测试"""

import re
from pathlib import Path


def fix_test_file(file_path: Path):
    """修复单个测试文件"""
    print(f"正在修复: {file_path}")

    # 读取文件（使用 UTF-8 编码）
    content = file_path.read_text(encoding="utf-8")

    # 1. 替换导入
    content = content.replace(
        "from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine",
        "from sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session, sessionmaker",
    )

    # 2. 替换 fixture 名称
    content = content.replace("async_engine", "engine")
    content = content.replace("async_session", "db_session")

    # 3. 移除 @pytest.mark.asyncio
    content = re.sub(r"\s*@pytest\.mark\.asyncio\s*\n", "\n", content)

    # 4. 移除测试方法的 async
    content = re.sub(r"async def (test_\w+)", r"def \1", content)

    # 5. 移除 await
    content = re.sub(r"await ", "", content)

    # 6. 修复 create_async_engine
    content = content.replace(
        'create_async_engine(\n        "sqlite+aiosqlite:///:memory:",',
        'create_engine(\n        "sqlite:///:memory:",',
    )

    # 7. 修复 async with engine.begin()
    content = re.sub(
        r"async with engine\.begin\(\) as conn:\s*\n\s*await conn\.run_sync\(Base\.metadata\.create_all\)",
        "Base.metadata.create_all(engine)",
        content,
    )

    # 8. 修复 engine.dispose()
    content = content.replace("engine.dispose()", "engine.dispose()")

    # 9. 修复 sessionmaker
    content = re.sub(
        r"async_sessionmaker\(\s*engine,\s*class_=AsyncSession",
        "sessionmaker(\n        engine, class_=Session",
        content,
    )

    # 10. 修复 async with session
    content = re.sub(
        r"async with session_maker\(\) as session:\s*\n\s*yield session\s*\n\s*# 测试结束后回滚（保持数据库干净）\s*\n\s*session\.rollback\(\)",
        "session = session_maker()\n    yield session\n    # 测试结束后回滚（保持数据库干净）\n    session.rollback()\n    session.close()",
        content,
    )

    # 11. 修复 fixture 定义
    content = re.sub(
        r"@pytest\.fixture\s*\nasync def (engine|db_session)", r"@pytest.fixture\ndef \1", content
    )

    # 写回文件（使用 UTF-8 编码）
    file_path.write_text(content, encoding="utf-8")
    print(f"✅ 修复完成: {file_path}")


def main():
    """主函数"""
    # 需要修复的测试文件
    test_files = [
        Path("tests/unit/infrastructure/database/test_agent_repository.py"),
        Path("tests/unit/infrastructure/database/test_run_repository.py"),
        Path("tests/unit/infrastructure/database/test_task_repository.py"),
    ]

    for file_path in test_files:
        if file_path.exists():
            fix_test_file(file_path)
        else:
            print(f"❌ 文件不存在: {file_path}")

    print("\n✅ 所有文件修复完成！")


if __name__ == "__main__":
    main()
