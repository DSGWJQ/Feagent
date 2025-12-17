"""文件操作工具

这个工具允许 Agent 读取文件内容。

为什么需要这个工具？
- Agent 需要读取配置文件、数据文件等
- 分析文件内容、提取信息等

设计原则：
1. 安全：限制文件大小、只读不写
2. 容错：捕获所有异常，返回错误信息
3. 编码处理：自动检测文件编码
4. 清晰的描述：让 LLM 知道如何使用这个工具

为什么只实现读取，不实现写入？
- 安全考虑：避免 Agent 误删除或修改重要文件
- 简单原则：先实现最基本的功能
- 未来扩展：可以添加写入工具，但需要更严格的权限控制

为什么使用 @tool 装饰器？
- 简单：自动生成工具的 schema
- 类型安全：支持类型注解
- 文档友好：自动从 docstring 生成描述
"""

from pathlib import Path

from langchain_core.tools import tool


@tool
def read_file(file_path: str) -> str:
    """读取文件内容并返回

    这个工具可以读取文本文件的内容。支持常见的文本文件格式（txt、json、csv、md 等）。

    参数：
        file_path: 文件路径（绝对路径或相对路径）

    返回：
        文件内容（字符串）或错误信息

    示例：
        # 读取文本文件
        read_file(file_path="/path/to/file.txt")

        # 读取 JSON 文件
        read_file(file_path="/path/to/data.json")

        # 读取 CSV 文件
        read_file(file_path="/path/to/data.csv")
    """
    try:
        # 转换为 Path 对象
        path = Path(file_path)

        # 检查文件是否存在
        if not path.exists():
            return f"错误：文件不存在\n路径：{file_path}"

        # 检查是否是文件（不是目录）
        if not path.is_file():
            return f"错误：路径不是文件（可能是目录）\n路径：{file_path}"

        # 检查文件大小
        # 为什么限制文件大小？
        # - 避免读取太大的文件（内存限制）
        # - LLM 有 token 限制
        # - 提高性能
        max_size = 1024 * 1024  # 1 MB
        file_size = path.stat().st_size

        if file_size > max_size:
            return (
                f"错误：文件太大（{file_size / 1024 / 1024:.2f} MB）\n"
                f"最大支持：{max_size / 1024 / 1024:.2f} MB\n"
                f"路径：{file_path}"
            )

        # 读取文件内容
        # 为什么尝试多种编码？
        # - 文件可能使用不同的编码（UTF-8、GBK 等）
        # - 自动检测编码，提高兼容性
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
        content = None
        used_encoding = None

        for encoding in encodings:
            try:
                content = path.read_text(encoding=encoding)
                used_encoding = encoding
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return (
                f"错误：无法读取文件（编码不支持）\n"
                f"尝试的编码：{', '.join(encodings)}\n"
                f"路径：{file_path}"
            )

        # 返回文件内容
        # 为什么限制长度？
        # - 避免返回太大的内容（LLM 有 token 限制）
        # - 提高性能
        max_length = 50000  # 最多返回 50000 个字符
        if len(content) > max_length:
            return (
                f"文件内容（已截断，原始长度：{len(content)} 字符，编码：{used_encoding}）：\n"
                f"{content[:max_length]}\n"
                f"...\n"
                f"（内容太长，已截断）"
            )

        return f"文件内容（编码：{used_encoding}）：\n\n{content}"

    except PermissionError:
        return f"错误：没有权限读取文件\n路径：{file_path}"

    except Exception as e:
        return f"错误：读取文件失败\n路径：{file_path}\n详细信息：{str(e)}"


def get_read_file_tool():
    """获取文件读取工具

    为什么使用工厂函数？
    - 统一入口：所有工具都通过工厂函数获取
    - 便于测试：可以在测试中 Mock
    - 便于管理：可以在应用启动时创建工具列表

    返回：
        Tool: 文件读取工具

    示例：
    >>> tool = get_read_file_tool()
    >>> result = tool.func(file_path="/path/to/file.txt")
    >>> print(result)
    """
    return read_file
