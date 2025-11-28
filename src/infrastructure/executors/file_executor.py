"""File Executor（文件执行器）

Infrastructure 层：实现文件处理节点执行器

支持的操作：
- 读取文件（read）
- 写入文件（write）
- 追加到文件（append）
- 删除文件（delete）
- 列出目录（list）
"""

import os
from pathlib import Path
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutor


class FileExecutor(NodeExecutor):
    """文件处理节点执行器

    配置参数：
        operation: 操作类型（read, write, append, delete, list）
        path: 文件或目录路径
        content: 文件内容（write/append 操作需要）
        encoding: 文件编码（默认 utf-8）
    """

    # 允许的操作类型
    ALLOWED_OPERATIONS = {"read", "write", "append", "delete", "list"}

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行文件处理节点

        参数：
            node: 节点实体
            inputs: 输入数据（来自前驱节点）
            context: 执行上下文

        返回：
            操作结果
        """
        # 获取配置
        operation = node.config.get("operation", "").lower()
        path = node.config.get("path", "")
        encoding = node.config.get("encoding", "utf-8")

        if not operation:
            raise DomainError("文件节点缺少 operation 配置")

        if operation not in self.ALLOWED_OPERATIONS:
            raise DomainError(
                f"不支持的文件操作: {operation}，"
                f"支持的操作: {', '.join(self.ALLOWED_OPERATIONS)}"
            )

        if not path:
            raise DomainError("文件节点缺少路径配置")

        try:
            file_path = Path(path)

            if operation == "read":
                return self._read_file(file_path, encoding)
            elif operation == "write":
                content = node.config.get("content", "")
                return self._write_file(file_path, content, encoding)
            elif operation == "append":
                content = node.config.get("content", "")
                return self._append_file(file_path, content, encoding)
            elif operation == "delete":
                return self._delete_file(file_path)
            elif operation == "list":
                return self._list_directory(file_path)

        except DomainError:
            raise
        except Exception as e:
            raise DomainError(f"文件操作失败: {str(e)}") from e

    @staticmethod
    def _read_file(file_path: Path, encoding: str) -> dict:
        """读取文件内容

        参数：
            file_path: 文件路径
            encoding: 文件编码

        返回：
            包含文件内容的字典
        """
        if not file_path.exists():
            raise DomainError(f"文件不存在: {file_path}")

        if not file_path.is_file():
            raise DomainError(f"路径不是文件: {file_path}")

        with open(file_path, encoding=encoding) as f:
            content = f.read()

        return {
            "path": str(file_path),
            "content": content,
            "size": len(content),
        }

    @staticmethod
    def _write_file(file_path: Path, content: str, encoding: str) -> dict:
        """写入文件内容（覆盖）

        参数：
            file_path: 文件路径
            content: 文件内容
            encoding: 文件编码

        返回：
            包含操作结果的字典
        """
        # 创建目录（如果不存在）
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)

        return {
            "path": str(file_path),
            "operation": "write",
            "bytes_written": len(content.encode(encoding)),
        }

    @staticmethod
    def _append_file(file_path: Path, content: str, encoding: str) -> dict:
        """追加内容到文件

        参数：
            file_path: 文件路径
            content: 追加的内容
            encoding: 文件编码

        返回：
            包含操作结果的字典
        """
        # 创建目录（如果不存在）
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 如果文件不存在，创建它
        if not file_path.exists():
            file_path.touch()

        with open(file_path, "a", encoding=encoding) as f:
            f.write(content)

        return {
            "path": str(file_path),
            "operation": "append",
            "bytes_written": len(content.encode(encoding)),
        }

    @staticmethod
    def _delete_file(file_path: Path) -> dict:
        """删除文件

        参数：
            file_path: 文件路径

        返回：
            包含操作结果的字典
        """
        if not file_path.exists():
            raise DomainError(f"文件不存在: {file_path}")

        if not file_path.is_file():
            raise DomainError(f"路径不是文件: {file_path}")

        os.remove(file_path)

        return {
            "path": str(file_path),
            "operation": "delete",
            "status": "success",
        }

    @staticmethod
    def _list_directory(dir_path: Path) -> dict:
        """列出目录内容

        参数：
            dir_path: 目录路径

        返回：
            包含目录内容的字典
        """
        if not dir_path.exists():
            raise DomainError(f"目录不存在: {dir_path}")

        if not dir_path.is_dir():
            raise DomainError(f"路径不是目录: {dir_path}")

        items = []
        for item in dir_path.iterdir():
            items.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "path": str(item),
                }
            )

        return {
            "path": str(dir_path),
            "operation": "list",
            "items": items,
            "count": len(items),
        }
