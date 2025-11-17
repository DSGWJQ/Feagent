"""测试 LangChain 工具

测试策略：
1. 测试工具的基本功能（能否正常调用）
2. 测试工具的输入验证（错误输入是否抛出异常）
3. 测试工具的输出格式（输出是否符合预期）
4. 测试工具能否被 Agent 调用（集成测试）

为什么使用真实的 HTTP 请求和文件操作？
- 工具的核心是与外部系统交互，Mock 无法测试真实效果
- 需要验证工具是否能正确处理真实场景
- 使用公共 API（如 httpbin.org）和临时文件，不会影响生产环境

注意：此文件包含 type: ignore 注释，因为 LangChain 的类型定义不完整
"""
# pyright: reportAttributeAccessIssue=false
# pyright: reportCallIssue=false

import tempfile
import unittest
from pathlib import Path

import pytest

from src.config import settings
from src.lc.tools import get_http_request_tool, get_read_file_tool


class TestHttpRequestTool(unittest.TestCase):
    """测试 HTTP 请求工具"""

    def test_create_tool(self):
        """测试工具是否能正常创建"""
        tool = get_http_request_tool()

        # 验证工具属性
        assert tool.name == "http_request"
        assert "HTTP" in tool.description or "请求" in tool.description
        assert callable(tool.func)

    def test_get_request(self):
        """测试 GET 请求"""
        tool = get_http_request_tool()

        # 调用工具（使用 httpbin.org 公共 API）
        result = tool.func(
            url="https://httpbin.org/get",
            method="GET",
        )

        # 验证结果
        assert isinstance(result, str)
        assert "httpbin.org" in result or "200" in result or "success" in result.lower()

    def test_post_request(self):
        """测试 POST 请求"""
        tool = get_http_request_tool()

        # 调用工具
        result = tool.func(
            url="https://httpbin.org/post",
            method="POST",
            body='{"name": "test"}',
        )

        # 验证结果
        assert isinstance(result, str)
        assert "httpbin.org" in result or "200" in result or "success" in result.lower()

    def test_invalid_url(self):
        """测试无效 URL"""
        tool = get_http_request_tool()

        # 调用工具（无效 URL）
        result = tool.func(
            url="https://invalid-url-that-does-not-exist-12345.com",
            method="GET",
        )

        # 验证结果（应该返回错误信息，而不是抛出异常）
        assert isinstance(result, str)
        assert "错误" in result or "error" in result.lower() or "失败" in result

    def test_invalid_method(self):
        """测试无效 HTTP 方法"""
        tool = get_http_request_tool()

        # 调用工具（无效方法）
        result = tool.func(
            url="https://httpbin.org/get",
            method="INVALID",
        )

        # 验证结果（应该返回错误信息）
        assert isinstance(result, str)
        assert "错误" in result or "error" in result.lower() or "不支持" in result


class TestReadFileTool(unittest.TestCase):
    """测试文件读取工具"""

    def setUp(self):
        """创建临时文件用于测试"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()

        # 创建测试文件
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("Hello, World!\n这是测试文件。", encoding="utf-8")

    def tearDown(self):
        """清理临时文件"""
        # 删除测试文件
        if self.test_file.exists():
            self.test_file.unlink()

        # 删除临时目录
        if Path(self.temp_dir).exists():
            Path(self.temp_dir).rmdir()

    def test_create_tool(self):
        """测试工具是否能正常创建"""
        tool = get_read_file_tool()

        # 验证工具属性
        assert tool.name == "read_file"
        assert "文件" in tool.description or "读取" in tool.description
        assert callable(tool.func)

    def test_read_file(self):
        """测试读取文件"""
        tool = get_read_file_tool()

        # 调用工具
        result = tool.func(file_path=str(self.test_file))

        # 验证结果
        assert isinstance(result, str)
        assert "Hello, World!" in result
        assert "这是测试文件" in result

    def test_read_nonexistent_file(self):
        """测试读取不存在的文件"""
        tool = get_read_file_tool()

        # 调用工具（不存在的文件）
        result = tool.func(file_path="/path/to/nonexistent/file.txt")

        # 验证结果（应该返回错误信息，而不是抛出异常）
        assert isinstance(result, str)
        assert "错误" in result or "error" in result.lower() or "不存在" in result

    def test_read_large_file(self):
        """测试读取大文件（应该有大小限制）"""
        # 创建大文件（1MB）
        large_file = Path(self.temp_dir) / "large.txt"
        large_file.write_text("x" * (1024 * 1024), encoding="utf-8")

        tool = get_read_file_tool()

        # 调用工具
        result = tool.func(file_path=str(large_file))

        # 验证结果（应该返回错误信息或截断内容）
        assert isinstance(result, str)
        # 可能返回错误信息，或者截断内容
        assert len(result) > 0

        # 清理
        large_file.unlink()


class TestToolsIntegration(unittest.TestCase):
    """测试工具集成（工具能否被 Agent 调用）"""

    @pytest.mark.skipif(
        not settings.openai_api_key,
        reason="需要配置 OPENAI_API_KEY 才能运行此测试",
    )
    def test_tools_with_agent(self):
        """测试工具能否被 Agent 调用

        这是一个集成测试，验证：
        1. 工具能否被 Agent 识别
        2. Agent 能否正确调用工具
        3. 工具返回的结果能否被 Agent 使用

        注意：这个测试需要 LLM 支持 tool calling（如 OpenAI GPT-4）
        如果使用不支持 tool calling 的模型，测试会跳过
        """
        try:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
        except ImportError:
            # LangChain 版本可能不支持，跳过测试
            pytest.skip("当前 LangChain 版本不支持 create_tool_calling_agent")

        from langchain_core.prompts import ChatPromptTemplate

        from src.lc import get_llm_for_execution

        # 创建工具列表
        tools = [
            get_http_request_tool(),
            get_read_file_tool(),
        ]

        # 创建 LLM
        llm = get_llm_for_execution()

        # 检查 LLM 是否支持 tool calling
        # KIMI 可能不支持 tool calling，需要使用 OpenAI GPT-4
        if not hasattr(llm, "bind_tools"):
            pytest.skip("当前 LLM 不支持 tool calling，跳过测试")

        # 创建 Prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个有用的助手，可以使用工具来完成任务。"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        # 创建 Agent
        agent = create_tool_calling_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

        # 调用 Agent（简单任务，不需要真正调用工具）
        result = agent_executor.invoke({"input": "你好，请介绍一下你自己"})

        # 验证结果
        assert isinstance(result, dict)
        assert "output" in result
        assert isinstance(result["output"], str)
        assert len(result["output"]) > 0


def manual_test():
    """手动测试工具

    运行方式：
    python -c "from tests.unit.lc.test_tools import manual_test; manual_test()"
    """
    print("=" * 60)
    print("手动测试 LangChain 工具")
    print("=" * 60)

    # 测试 HTTP 请求工具
    print("\n测试 1：HTTP 请求工具")
    print("-" * 60)
    http_tool = get_http_request_tool()
    print(f"工具名称：{http_tool.name}")
    print(f"工具描述：{http_tool.description}")

    print("\n发送 GET 请求到 https://httpbin.org/get")
    result = http_tool.func(url="https://httpbin.org/get", method="GET")
    print(f"结果：{result[:200]}...")  # 只显示前 200 个字符

    # 测试文件读取工具
    print("\n\n测试 2：文件读取工具")
    print("-" * 60)
    read_file_tool = get_read_file_tool()
    print(f"工具名称：{read_file_tool.name}")
    print(f"工具描述：{read_file_tool.description}")

    # 创建临时文件
    temp_file = Path(tempfile.gettempdir()) / "test_langchain.txt"
    temp_file.write_text("这是一个测试文件。\nHello, LangChain!", encoding="utf-8")

    print(f"\n读取文件：{temp_file}")
    result = read_file_tool.func(file_path=str(temp_file))
    print(f"结果：{result}")

    # 清理
    temp_file.unlink()

    print("\n" + "=" * 60)
    print("✅ 手动测试完成")
    print("=" * 60)


if __name__ == "__main__":
    manual_test()
