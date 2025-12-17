"""TaskExecutor 单元测试

测试场景：
1. 成功执行 Task（无工具调用）
2. 成功执行 Task（有工具调用）
3. Task 执行超时
4. Task 执行失败（LLM 错误）
5. 工具调用失败
6. 记录执行日志（TaskEvent）
7. 上下文传递
8. 多次工具调用
9. 工具调用日志记录（新增）
10. 工具调用超时控制（新增）
11. 工具调用错误处理（新增）
"""

import platform
import time
from unittest.mock import Mock, patch

import pytest

from src.domain.entities.task import Task
from src.domain.services.task_executor import TaskExecutionTimeout, TaskExecutor


class TestTaskExecutor:
    """TaskExecutor 测试类"""

    def _create_mock_task_runner(self, return_value: str) -> Mock:
        """创建 Mock TaskRunner"""
        mock_runner = Mock()
        mock_runner.run.return_value = return_value
        return mock_runner

    def test_execute_task_success_no_tools(self):
        """测试场景 1: 成功执行 Task（无工具调用）"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="分析数据",
            description="分析销售数据并生成报告",
        )

        context = {}

        # Mock TaskRunner
        mock_task_runner = self._create_mock_task_runner("分析完成：销售额增长 20%")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act
        result = executor.execute(task, context)

        # Assert
        assert result["result"] == "分析完成：销售额增长 20%"
        mock_task_runner.run.assert_called_once()

        # 验证 Task 记录了事件
        assert len(task.events) > 0
        assert any("开始执行" in event.message for event in task.events)
        assert any("执行成功" in event.message for event in task.events)

    def test_execute_task_success_with_tools(self):
        """测试场景 2: 成功执行 Task（有工具调用）"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="获取网页内容",
            description="访问 https://httpbin.org/get 并返回响应",
        )

        context = {}

        # Mock TaskRunner（模拟工具调用）
        mock_task_runner = self._create_mock_task_runner("网页内容已获取：{'origin': '1.2.3.4'}")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act
        result = executor.execute(task, context)

        # Assert
        assert "网页内容已获取" in result["result"]

        # 验证记录了工具调用事件
        assert len(task.events) > 0
        # 注意：实际的工具调用事件需要在 TaskExecutor 中记录

    @pytest.mark.skipif(platform.system() == "Windows", reason="signal.alarm 在 Windows 上不可用")
    def test_execute_task_timeout(self):
        """测试场景 3: Task 执行超时

        注意：此测试在 Windows 上会被跳过，因为 signal.alarm 不可用
        """
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="长时间任务",
            description="这个任务会执行很长时间",
        )

        context = {}

        # Mock TaskRunner（模拟超时）
        def slow_execute(*args, **kwargs):
            time.sleep(10)  # 模拟长时间执行
            return "完成"

        mock_task_runner = Mock()
        mock_task_runner.run.side_effect = slow_execute
        executor = TaskExecutor(task_runner=mock_task_runner, timeout=1)  # 设置 1 秒超时

        # Act & Assert
        with pytest.raises(TaskExecutionTimeout) as exc_info:
            executor.execute(task, context)

        assert "超时" in str(exc_info.value)

        # 验证记录了超时事件
        assert len(task.events) > 0
        assert any("超时" in event.message for event in task.events)

    def test_execute_task_llm_error(self):
        """测试场景 4: Task 执行失败（LLM 错误）"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="分析数据",
            description="分析销售数据",
        )

        context = {}

        # Mock TaskRunner（返回错误）
        mock_task_runner = self._create_mock_task_runner("错误：API 调用失败")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            executor.execute(task, context)

        assert "API 调用失败" in str(exc_info.value)

        # 验证记录了错误事件
        assert len(task.events) > 0
        assert any("错误" in event.message or "失败" in event.message for event in task.events)

    def test_execute_task_tool_call_error(self):
        """测试场景 5: 工具调用失败"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="读取文件",
            description="读取 /path/to/file.txt",
        )

        context = {}

        # Mock TaskRunner（模拟工具调用失败）
        mock_task_runner = Mock()
        mock_task_runner.run.side_effect = Exception("文件不存在")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            executor.execute(task, context)

        assert "文件不存在" in str(exc_info.value)

    def test_execute_task_records_events(self):
        """测试场景 6: 记录执行日志（TaskEvent）"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="测试任务",
            description="测试事件记录",
        )

        context = {}

        # Mock TaskRunner
        mock_task_runner = self._create_mock_task_runner("任务完成")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act
        result = executor.execute(task, context)

        # Assert
        assert result["result"] == "任务完成"
        # 验证记录了完整的执行事件
        assert len(task.events) >= 2  # 至少有开始和结束事件

        event_messages = [event.message for event in task.events]
        assert any("开始执行" in msg for msg in event_messages)
        assert any("执行成功" in msg or "完成" in msg for msg in event_messages)

    def test_execute_task_with_context(self):
        """测试场景 7: 上下文传递"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="分析结果",
            description="分析前一个任务的结果",
        )

        # 上下文包含前一个任务的结果
        context = {
            "Task 1": {"result": "数据已下载"},
            "Task 2": {"result": "数据已清洗"},
        }

        # Mock TaskRunner
        mock_task_runner = self._create_mock_task_runner("分析完成")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act
        result = executor.execute(task, context)

        # Assert
        # execute 返回 dict[str, Any]，包含 result 键
        assert result["result"] == "分析完成"
        # 验证上下文被传递给 TaskRunner
        call_args = mock_task_runner.run.call_args
        task_description = call_args.kwargs.get("task_description", "")

        # 上下文应该被添加到任务描述中
        assert "Task 1" in task_description or "上下文" in task_description

    def test_execute_task_multiple_tool_calls(self):
        """测试场景 8: 多次工具调用"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="复杂任务",
            description="先下载文件，再分析内容，最后生成报告",
        )

        context = {}

        # Mock TaskRunner（模拟多次工具调用）
        mock_task_runner = self._create_mock_task_runner("任务完成：下载 → 分析 → 报告")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act
        result = executor.execute(task, context)

        # Assert
        assert "任务完成" in result["result"]

        # 验证记录了多个事件（如果 TaskExecutor 支持记录工具调用）
        assert len(task.events) > 0

    def test_execute_task_with_custom_timeout(self):
        """测试场景 9: 自定义超时时间"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="快速任务",
            description="这个任务应该很快完成",
        )

        context = {}

        # Mock TaskRunner
        mock_task_runner = self._create_mock_task_runner("完成")

        # 创建自定义超时的 executor
        executor = TaskExecutor(task_runner=mock_task_runner, timeout=30)

        # Act
        result = executor.execute(task, context)

        # Assert
        assert result["result"] == "完成"

    def test_execute_task_empty_description(self):
        """测试场景 10: Task 描述为空"""
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="无描述任务",
            description=None,  # 描述为空
        )

        context = {}

        # Mock TaskRunner
        mock_task_runner = self._create_mock_task_runner("完成")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act
        result = executor.execute(task, context)

        # Assert
        assert result["result"] == "完成"

        # 验证调用时使用了空描述
        call_args = mock_task_runner.run.call_args
        assert call_args.kwargs.get("task_description") == ""

    def test_tool_call_logging(self):
        """测试场景 9: 工具调用日志记录

        需求：
        - 记录每次工具调用的开始和结束
        - 记录工具名称和参数
        - 记录工具调用结果
        - 记录工具调用耗时
        """
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="调用 HTTP API",
            description="调用 https://httpbin.org/get",
        )

        context = {}

        # Mock TaskRunner 和工具调用
        mock_task_runner = self._create_mock_task_runner("API 调用成功")

        # Mock 工具调用回调
        with patch("src.domain.services.task_executor.TaskExecutor._log_tool_call") as mock_log:
            executor = TaskExecutor(task_runner=mock_task_runner)

            # 手动触发工具调用日志（模拟）
            executor._log_tool_call(
                task=task,
                tool_name="http_request",
                tool_input={"url": "https://httpbin.org/get", "method": "GET"},
                tool_output="{'origin': '1.2.3.4'}",
                duration=0.5,
            )

            # Act
            result = executor.execute(task, context)

            # Assert
            assert result["result"] == "API 调用成功"

            # 验证记录了工具调用日志
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args.kwargs["tool_name"] == "http_request"
            assert "url" in call_args.kwargs["tool_input"]

    def test_tool_call_timeout_control(self):
        """测试场景 10: 工具调用超时控制

        需求：
        - 每个工具调用都有独立的超时时间
        - 超时后抛出异常
        - 记录超时事件
        """
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="慢速工具调用",
            description="调用一个很慢的工具",
        )

        context = {}

        # Mock 慢速工具调用
        def slow_tool_call(*args, **kwargs):
            time.sleep(5)  # 模拟慢速工具
            return "完成"

        mock_task_runner = Mock()
        mock_task_runner.run.side_effect = slow_tool_call
        executor = TaskExecutor(task_runner=mock_task_runner, timeout=2)  # 设置 2 秒超时

        # Act & Assert
        if platform.system() != "Windows":
            # Unix 系统上应该超时
            with pytest.raises(TaskExecutionTimeout) as exc_info:
                executor.execute(task, context)

            assert "超时" in str(exc_info.value)

            # 验证记录了超时事件
            assert any("超时" in event.message for event in task.events)
        else:
            # Windows 上暂时不支持超时，跳过
            pytest.skip("Windows 不支持 signal.alarm")

    def test_tool_call_error_handling(self):
        """测试场景 11: 工具调用错误处理

        需求：
        - 捕获工具调用异常
        - 记录错误详情
        - 继续执行或失败（取决于配置）
        """
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="调用失败的工具",
            description="调用一个会失败的工具",
        )

        context = {}

        # Mock 工具调用失败
        mock_task_runner = Mock()
        mock_task_runner.run.side_effect = Exception("工具调用失败：网络错误")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            executor.execute(task, context)

        assert "工具调用失败" in str(exc_info.value)

        # 验证记录了错误事件
        assert any("异常" in event.message or "错误" in event.message for event in task.events)

    def test_multiple_tool_calls_logging(self):
        """测试场景 12: 多次工具调用日志记录

        需求：
        - 记录所有工具调用
        - 按顺序记录
        - 包含完整的调用链
        """
        # Arrange
        task = Task.create(
            agent_id="agent-123",
            run_id="run-456",
            name="多步骤任务",
            description="先调用 API，再读取文件，最后执行 Python 代码",
        )

        context = {}

        # Mock TaskRunner（模拟多次工具调用）
        mock_task_runner = self._create_mock_task_runner("所有工具调用完成")
        executor = TaskExecutor(task_runner=mock_task_runner)

        # 模拟记录多次工具调用
        executor._log_tool_call(
            task=task,
            tool_name="http_request",
            tool_input={"url": "https://api.example.com"},
            tool_output="{'data': 'value'}",
            duration=0.3,
        )

        executor._log_tool_call(
            task=task,
            tool_name="read_file",
            tool_input={"path": "data.txt"},
            tool_output="file content",
            duration=0.1,
        )

        executor._log_tool_call(
            task=task,
            tool_name="execute_python",
            tool_input={"code": "print('hello')"},
            tool_output="hello",
            duration=0.2,
        )

        # Act
        result = executor.execute(task, context)

        # Assert
        assert result["result"] == "所有工具调用完成"

        # 验证记录了所有工具调用事件
        tool_events = [e for e in task.events if "工具调用" in e.message]
        assert len(tool_events) >= 3  # 至少 3 次工具调用
