"""测试 TaskExecutorAgent

【遗留问题】此测试文件依赖真实 LLM 调用，在没有配置 OPENAI_API_KEY 的环境下会失败。
这些测试应当在有 LLM 环境的情况下运行，或者改为使用 Mock LLM。

测试策略：
1. 测试 Agent 的基本功能（能否正常创建和执行）
2. 测试 Agent 的工具调用（能否正确使用工具）
3. 测试 Agent 的错误处理（错误输入是否正确处理）
4. 测试 Agent 的输出格式（输出是否符合预期）

为什么需要测试 Agent？
- Agent 是核心组件，负责执行任务
- 需要验证 Agent 能否正确理解任务并调用工具
- 需要验证 Agent 的容错性

测试方法：
- 使用真实的 LLM（如果配置了）或 Mock LLM
- 使用真实的工具（HTTP、文件读取）
- 验证 Agent 的输出格式和内容
"""

import unittest

import pytest

from src.config import settings


class TestTaskExecutorAgent(unittest.TestCase):
    """测试 TaskExecutorAgent"""

    def test_create_agent(self):
        """测试 Agent 是否能正常创建"""
        from src.lc.agents.task_executor import create_task_executor_agent

        # 创建 Agent
        agent = create_task_executor_agent()

        # 验证 Agent 不为空
        assert agent is not None

    def test_execute_simple_task(self):
        """测试执行简单任务（不需要工具）"""
        from src.lc.agents.task_executor import execute_task

        # 执行简单任务
        task_name = "计算 1 + 1"
        task_description = "计算 1 加 1 的结果"

        result = execute_task(
            task_name=task_name,
            task_description=task_description,
        )

        # 验证结果
        assert isinstance(result, str)
        assert len(result) > 0
        # 结果应该包含 "2" 或 "二"
        assert "2" in result or "二" in result

    def test_execute_task_with_http_tool(self):
        """测试执行需要 HTTP 工具的任务"""
        from src.lc.agents.task_executor import execute_task

        # 执行需要 HTTP 工具的任务
        task_name = "获取 httpbin.org 的 IP 信息"
        task_description = "使用 HTTP GET 请求访问 https://httpbin.org/ip 获取 IP 信息"

        result = execute_task(
            task_name=task_name,
            task_description=task_description,
        )

        # 验证结果
        assert isinstance(result, str)
        assert len(result) > 0
        # 结果应该包含 "origin" 或 "ip" 或 "httpbin"
        assert "origin" in result.lower() or "ip" in result.lower() or "httpbin" in result.lower()

    def test_execute_task_with_file_tool(self):
        """测试执行需要文件读取工具的任务"""
        import tempfile
        from pathlib import Path

        from src.lc.agents.task_executor import execute_task

        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt", encoding="utf-8"
        ) as f:
            f.write("这是一个测试文件。\n")
            f.write("内容：LangChain Agent 测试\n")
            temp_file_path = f.name

        try:
            # 执行需要文件读取工具的任务
            task_name = "读取文件内容"
            task_description = f"读取文件 {temp_file_path} 的内容"

            result = execute_task(
                task_name=task_name,
                task_description=task_description,
            )

            # 验证结果
            assert isinstance(result, str)
            assert len(result) > 0
            # 结果应该包含文件内容
            assert "测试文件" in result or "LangChain" in result or "Agent" in result

        finally:
            # 清理临时文件
            Path(temp_file_path).unlink(missing_ok=True)

    def test_execute_task_with_error(self):
        """测试执行错误任务（任务描述不清晰）"""
        from src.lc.agents.task_executor import execute_task

        # 执行错误任务
        task_name = "未知任务"
        task_description = ""  # 空描述

        result = execute_task(
            task_name=task_name,
            task_description=task_description,
        )

        # 验证结果
        assert isinstance(result, str)
        # 应该返回错误信息或提示
        assert len(result) > 0

    def test_execute_task_with_invalid_http_request(self):
        """测试执行无效的 HTTP 请求任务"""
        from src.lc.agents.task_executor import execute_task

        # 执行无效的 HTTP 请求任务
        task_name = "访问无效的 URL"
        task_description = "使用 HTTP GET 请求访问 http://invalid-url-that-does-not-exist-12345.com"

        result = execute_task(
            task_name=task_name,
            task_description=task_description,
        )

        # 验证结果
        assert isinstance(result, str)
        assert len(result) > 0
        # 结果应该包含错误信息
        assert (
            "错误" in result
            or "失败" in result
            or "error" in result.lower()
            or "fail" in result.lower()
        )

    def test_execute_task_with_nonexistent_file(self):
        """测试执行读取不存在的文件任务"""
        from src.lc.agents.task_executor import execute_task

        # 执行读取不存在的文件任务
        task_name = "读取不存在的文件"
        task_description = "读取文件 /path/to/nonexistent/file.txt 的内容"

        result = execute_task(
            task_name=task_name,
            task_description=task_description,
        )

        # 验证结果
        assert isinstance(result, str)
        assert len(result) > 0
        # 结果应该包含错误信息
        assert (
            "错误" in result
            or "不存在" in result
            or "error" in result.lower()
            or "not found" in result.lower()
        )

    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "",
        reason="需要配置真实的 OpenAI API Key 才能运行此测试",
    )
    def test_execute_task_with_real_llm(self):
        """测试使用真实 LLM 执行任务"""
        from src.lc.agents.task_executor import execute_task

        # 执行任务
        task_name = "获取当前时间"
        task_description = "告诉我现在是几点（不需要使用工具，直接回答即可）"

        result = execute_task(
            task_name=task_name,
            task_description=task_description,
        )

        # 验证结果
        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\n任务执行结果：\n{result}")


class TestTaskExecutorIntegration(unittest.TestCase):
    """测试 TaskExecutorAgent 集成"""

    def test_agent_with_all_tools(self):
        """测试 Agent 能否访问所有工具"""
        from src.lc.agents.task_executor import create_task_executor_agent
        from src.lc.tools import get_all_tools

        # 创建 Agent
        _ = create_task_executor_agent()

        # 获取所有工具
        tools = get_all_tools()

        # 验证工具数量
        assert len(tools) >= 2  # 至少有 HTTP 和文件读取工具

        # 验证工具名称
        tool_names = [tool.name for tool in tools]
        assert "http_request" in tool_names
        assert "read_file" in tool_names

    def test_execute_task_function_signature(self):
        """测试 execute_task 函数签名"""
        # 验证函数签名
        import inspect

        from src.lc.agents.task_executor import execute_task

        sig = inspect.signature(execute_task)
        params = list(sig.parameters.keys())

        # 应该有 task_name 和 task_description 参数
        assert "task_name" in params
        assert "task_description" in params


if __name__ == "__main__":
    unittest.main()
